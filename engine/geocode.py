#!/usr/bin/env python3
"""Geocode place queries with Nominatim (OpenStreetMap), politely.

Usage:
  python3 geocode.py "query one" "query two" ...
      -> prints TSV: query, lat, lng, display_name   (NOT FOUND / RATE LIMITED otherwise)
  python3 geocode.py --batch <itinerary.json> [--country <iso2>] [--write]
      -> for every place in the itinerary missing lat/lng, resolve "<name>, <address>"
         and fill it in. Prints a TSV report; with --write, saves the file back.
         Places that cannot be resolved are left untouched (never guess a coord).

Nominatim allows about one request per second per client. Several analysts run
in parallel, so this script waits 1.1 s between its own requests, retries a
429 / 5xx answer with a growing pause (up to 4 attempts), falls back to Photon
(komoot's OpenStreetMap geocoder) when Nominatim keeps refusing, and caches every
answer in ``<desk root>/.geocode-cache.json`` so the same place is asked once.
Exit status: 0 when every query was answered (found or not found), 2 when both
services kept rate-limiting.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deskpaths  # noqa: E402

UA = "travel-desk/1.0 (KiroCrew app; trip planning; https://github.com/chenmingwei23/kirocrew-travel-desk)"
_PAUSE = 1.1
_RETRIES = 4


class RateLimited(Exception):
    """Nominatim answered 429 (or kept failing) after every retry."""


def _cache_path() -> Path:
    return deskpaths.desk_root() / ".geocode-cache.json"


def _load_cache() -> dict:
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict) -> None:
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def geocode(q: str, countrycodes: str | None = None, cache: dict | None = None):
    """Return ``(lat, lng, display_name)``, ``None`` when unknown. Raises RateLimited."""
    key = f"{countrycodes or ''}|{q.strip().lower()}"
    if cache is not None and key in cache:
        hit = cache[key]
        return tuple(hit) if hit else None
    url = ("https://nominatim.openstreetmap.org/search?format=json&limit=1&addressdetails=0"
           + (f"&countrycodes={countrycodes}" if countrycodes else "")
           + "&q=" + urllib.parse.quote(q))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    delay = 2.0
    for attempt in range(_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                hits = json.loads(r.read())
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 or exc.code >= 500:
                if attempt == _RETRIES - 1:
                    raise RateLimited(f"HTTP {exc.code} after {_RETRIES} attempts") from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    delay = max(delay, float(retry_after)) if retry_after else delay
                except ValueError:
                    pass
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == _RETRIES - 1:
                raise RateLimited(str(exc)) from exc
            time.sleep(delay)
            delay *= 2
    result = None
    if hits:
        h = hits[0]
        result = (float(h["lat"]), float(h["lon"]), h.get("display_name", ""))
    if cache is not None:
        cache[key] = list(result) if result else None
        _save_cache(cache)
    return result


def _photon(q: str, countrycodes: str | None = None):
    """Photon (komoot) fallback: same OSM data, separate rate limit. None when unknown."""
    url = ("https://photon.komoot.io/api/?limit=1&q=" + urllib.parse.quote(q))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    feats = data.get("features") or []
    if countrycodes:
        wanted = {c.strip().lower() for c in countrycodes.split(",") if c.strip()}
        feats = [f for f in feats
                 if str((f.get("properties") or {}).get("countrycode", "")).lower() in wanted] or feats
    if not feats:
        return None
    f = feats[0]
    lng, lat = f["geometry"]["coordinates"][:2]
    props = f.get("properties") or {}
    label = ", ".join(str(props[k]) for k in ("name", "city", "state", "country") if props.get(k))
    return (float(lat), float(lng), label)


def lookup(q: str, countrycodes: str | None = None, cache: dict | None = None):
    """Nominatim first, Photon when Nominatim is rate-limited. Raises RateLimited when both fail."""
    try:
        return geocode(q, countrycodes, cache)
    except RateLimited as first:
        try:
            result = _photon(q, countrycodes)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
            raise RateLimited(f"{first}; photon: {exc}") from exc
        if cache is not None:
            key = f"{countrycodes or ''}|{q.strip().lower()}"
            cache[key] = list(result) if result else None
            _save_cache(cache)
        return result


def batch(path: str, countrycodes: str | None = None, write: bool = False) -> int:
    with open(path, encoding="utf-8") as fh:
        itin = json.load(fh)
    missing = []
    for day in itin.get("days", []):
        for p in day.get("places", []):
            if p.get("lat") is None or p.get("lng") is None:
                missing.append(p)
    for s in itin.get("stays", []):
        if s.get("lat") is None or s.get("lng") is None:
            missing.append(s)

    cache = _load_cache()
    filled = 0
    limited = 0
    for i, p in enumerate(missing):
        if i:
            time.sleep(_PAUSE)
        q = ", ".join(x for x in (p.get("name"), p.get("address")) if x)
        try:
            hit = lookup(q, countrycodes, cache)
        except RateLimited as exc:
            limited += 1
            print(f"{p.get('name')}\tRATE LIMITED\t({exc}; left untouched, try again later)")
            continue
        if hit:
            p["lat"], p["lng"] = round(hit[0], 5), round(hit[1], 5)
            filled += 1
            print(f"{p.get('name')}\t{p['lat']:.5f}\t{p['lng']:.5f}\t{hit[2][:80]}")
        else:
            print(f"{p.get('name')}\tNOT FOUND\t(left untouched)")

    if write and filled:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(itin, fh, ensure_ascii=False, indent=2)
        print(f"# wrote {filled} coords back to {path}")
    else:
        print(f"# resolved {filled}/{len(missing)} missing "
              f"(pass --write to save)")
    return 2 if limited else 0


def main(args: list[str]) -> int:
    if args and args[0] == "--batch":
        if len(args) < 2:
            print(__doc__)
            return 1
        path = args[1]
        country = None
        if "--country" in args:
            country = args[args.index("--country") + 1]
        return batch(path, country, write=("--write" in args))
    if not args:
        print(__doc__)
        return 1
    cache = _load_cache()
    limited = 0
    for i, q in enumerate(args):
        if i:
            time.sleep(_PAUSE)
        try:
            hit = lookup(q, None, cache)
        except RateLimited as exc:
            limited += 1
            print(f"{q}\tRATE LIMITED\t({exc}; try again in a minute)")
            continue
        if hit:
            print(f"{q}\t{hit[0]:.5f}\t{hit[1]:.5f}\t{hit[2][:90]}")
        else:
            print(f"{q}\tNOT FOUND")
    return 2 if limited else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
