"""Photo resolution + cache for the Travel Desk (API.md §GET /photos, §GET /photo).

Per place, in order (API.md):
  1. TREK ``place.image_url`` — download it.
  2. Wikipedia (EN) search on the Latin part of the name -> first page with a
     thumbnail that is plausibly this place (coordinates within 30 km, or every
     query word in the title when the page has no coordinates).
  3. Wikipedia geosearch around lat/lng (1.5 km, then 6 km) -> first page with a thumbnail.
  4. nothing -> record a miss (not retried for 24h). Throttling (429), 5xx or a
     network error is NOT a miss: the place stays pending for the next call.

Lookups run one place at a time with a short pause; Wikipedia answers parallel
clients with 429.

Cache lives under ``<data_dir>/photos/`` with an index ``<data_dir>/photos.json``.
Every outbound HTTP request carries the required User-Agent. The network is
confined to two functions — ``_http_get_json`` and ``_http_get_bytes`` — so tests
mock those and never touch the wire.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("kirocrew.app.travel-desk")

USER_AGENT = "travel-desk/0.2 (KiroCrew app)"
_WIKI_API = "https://en.wikipedia.org/w/api.php"
_BUDGET_SECS = 12.0
_MISS_TTL_SECS = 24 * 3600
_THUMB_SIZE = 1200
_HTTP_TIMEOUT = 6.0

_PHOTO_URL_PREFIX = "/api/apps/travel-desk/photo"

# extension <- content-type / url suffix
_EXT_BY_CT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
_CONTENT_TYPE_BY_EXT = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


# ---------------------------------------------------------------------------
# paths + index
# ---------------------------------------------------------------------------


def photos_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "photos"


def index_path(data_dir: Path) -> Path:
    return Path(data_dir) / "photos.json"


def photo_url(place_id: int) -> str:
    return f"{_PHOTO_URL_PREFIX}/{place_id}"


def _load_index(data_dir: Path) -> dict[str, Any]:
    try:
        raw = index_path(data_dir).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _save_index(data_dir: Path, index: dict[str, Any]) -> None:
    photos_dir(data_dir).mkdir(parents=True, exist_ok=True)
    tmp = index_path(data_dir).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")
    tmp.replace(index_path(data_dir))


def place_key(place: dict) -> str:
    """sha1 of ``name|lat|lng`` — changes when a place is renamed or moved."""
    name = str(place.get("name") or "")
    lat = place.get("lat")
    lng = place.get("lng")
    basis = f"{name}|{lat}|{lng}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def cached_photo_path(data_dir: Path, place_id: int) -> Path | None:
    """Filesystem path of a place's cached image, or None (miss / not resolved).

    A recorded miss returns None. A stale entry (its file vanished) also None.
    """
    index = _load_index(data_dir)
    entry = index.get(str(place_id))
    if not isinstance(entry, dict) or entry.get("miss"):
        return None
    fname = entry.get("file")
    if not fname:
        return None
    path = photos_dir(data_dir) / str(fname)
    return path if path.is_file() else None


def photo_url_for(data_dir: Path, place_id: int) -> str | None:
    """The public ``/photo/<id>`` URL when a cached image exists, else None."""
    return photo_url(place_id) if cached_photo_path(data_dir, place_id) is not None else None


def is_confirmed_miss(data_dir: Path, place_id: int) -> bool:
    """True when the index records this place as a resolved miss (no photo found)."""
    entry = _load_index(data_dir).get(str(place_id))
    return isinstance(entry, dict) and bool(entry.get("miss"))


# ---------------------------------------------------------------------------
# network (mock these two in tests)
# ---------------------------------------------------------------------------


def _http_get_json(url: str, params: dict[str, Any]) -> Any:
    """GET a JSON endpoint with the required User-Agent. Returns parsed JSON."""
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _http_get_bytes(url: str) -> tuple[bytes, str]:
    """GET raw bytes + content-type with the required User-Agent."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        ct = resp.headers.get("Content-Type", "") or ""
        return resp.read(), ct.split(";")[0].strip().lower()


# ---------------------------------------------------------------------------
# resolution
# ---------------------------------------------------------------------------


class TransientLookupError(Exception):
    """Wikipedia said come back later (429 / 5xx / network). Not a miss."""

    def __init__(self, msg: str, retry_after: float | None = None):
        super().__init__(msg)
        self.retry_after = retry_after


def _latin_part(name: str) -> str:
    """The Latin-script portion of a place name (drops CJK and its brackets)."""
    kept = []
    depth = 0
    for ch in name:
        if ch in "（(":
            depth += 1
            continue
        if ch in "）)":
            depth = max(0, depth - 1)
            continue
        if depth:
            continue
        if "\u4e00" <= ch <= "\u9fff" or ch in "·、":
            kept.append(" ")
            continue
        kept.append(ch)
    return " ".join("".join(kept).split())


def _ext_from(ct: str, url: str) -> str:
    ext = _EXT_BY_CT.get(ct)
    if ext:
        return ext
    low = url.lower().split("?")[0]
    for cand in ("jpg", "jpeg", "png", "webp"):
        if low.endswith("." + cand):
            return "jpg" if cand == "jpeg" else cand
    return "jpg"


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km."""
    from math import asin, cos, radians, sin, sqrt

    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(a))


_NEAR_KM = 30.0
_PAUSE_SECS = 0.6
_THROTTLE_DEFAULT_SECS = 120.0
_META_KEY = "_meta"


def _throttled_until(index: dict[str, Any]) -> float:
    meta = index.get(_META_KEY)
    val = meta.get("throttled_until") if isinstance(meta, dict) else None
    return float(val) if isinstance(val, (int, float)) else 0.0


def _remember_throttle(index: dict[str, Any], until: float) -> None:
    meta = index.get(_META_KEY)
    if not isinstance(meta, dict):
        meta = {}
    meta["throttled_until"] = until
    index[_META_KEY] = meta


def _query(params: dict[str, Any]) -> list[dict]:
    """One Wikipedia query; returns the page dicts. 429/5xx/network -> TransientLookupError."""
    import urllib.error

    base = {"action": "query", "format": "json", "prop": "pageimages|coordinates",
            "piprop": "thumbnail", "pithumbsize": _THUMB_SIZE, "colimit": 1, "redirects": 1}
    base.update(params)
    try:
        data = _http_get_json(_WIKI_API, base)
    except urllib.error.HTTPError as exc:
        if exc.code == 429 or exc.code >= 500:
            retry = None
            try:
                hdr = exc.headers.get("Retry-After") if exc.headers is not None else None
                retry = float(hdr) if hdr else None
            except (TypeError, ValueError):
                retry = None
            raise TransientLookupError(f"HTTP {exc.code}", retry) from exc
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TransientLookupError(str(exc)) from exc
    pages = (((data or {}).get("query") or {}).get("pages") or {})
    out = [pg for pg in pages.values() if isinstance(pg, dict)]
    out.sort(key=lambda pg: pg.get("index", 0))
    return out


def _pick(pages: list[dict], lat: Any, lng: Any, words: list[str]) -> tuple[str | None, str | None]:
    """First page with a thumbnail that is plausibly THIS place.

    Plausible = its coordinates are within ``_NEAR_KM`` of the place, or, when
    the page carries no coordinates, its title IS the query (ignoring case and
    a trailing ", Region" / "(qualifier)"). That keeps "Twelve Apostles" from
    returning the Last Supper and "Lorne" from returning Lorne Michaels.
    """
    have_geo = isinstance(lat, (int, float)) and isinstance(lng, (int, float))
    query = " ".join(words)
    for pg in pages:
        thumb = (pg.get("thumbnail") or {}).get("source")
        if not thumb:
            continue
        title = str(pg.get("title") or "")
        coords = pg.get("coordinates") or []
        if coords and have_geo:
            c = coords[0] or {}
            try:
                if _km(float(lat), float(lng), float(c.get("lat")), float(c.get("lon"))) <= _NEAR_KM:
                    return thumb, title
            except (TypeError, ValueError):
                pass
            continue
        if query and _title_core(title) == query:
            return thumb, title
    return None, None


def _title_core(title: str) -> str:
    """'Lorne, Victoria' / 'Gibson Steps (Victoria)' -> 'lorne' / 'gibson steps'."""
    core = title.split(",")[0]
    core = core.split("(")[0]
    return " ".join(core.lower().split())


def _resolve_one(place: dict) -> tuple[str | None, str | None]:
    """Resolve a single place to (image_url, page_title) or (None, None).

    Raises TransientLookupError when Wikipedia is throttling; the caller then
    leaves the place unresolved (not a miss) for the next call.
    """
    src = place.get("image_url")
    if isinstance(src, str) and src.strip():
        return src.strip(), None

    name = str(place.get("name") or "")
    lat = place.get("lat")
    lng = place.get("lng")
    query = _latin_part(name)
    words = query.lower().split()

    if query:
        pages = _query({"generator": "search", "gsrsearch": query, "gsrlimit": 4, "gsrnamespace": 0})
        img, page = _pick(pages, lat, lng, words)
        if img:
            return img, page
        time.sleep(_PAUSE_SECS)

    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        for radius in (1500, 6000):
            pages = _query({"generator": "geosearch", "ggscoord": f"{lat}|{lng}", "ggsradius": radius, "ggslimit": 6})
            img, page = _pick(pages, lat, lng, [])
            if img:
                return img, page
            time.sleep(_PAUSE_SECS)
    return None, None


def _needs_resolve(entry: Any, key: str, now: float) -> bool:
    """True when a place has no usable cache entry for this key."""
    if not isinstance(entry, dict):
        return True
    if entry.get("key") != key:
        return True
    if entry.get("miss"):
        ts = entry.get("fetched_at_ts")
        return not isinstance(ts, (int, float)) or (now - float(ts)) >= _MISS_TTL_SECS
    return not entry.get("file")


def resolve_photos(
    data_dir: Path,
    places: list[dict],
    *,
    now: float | None = None,
    budget_secs: float = _BUDGET_SECS,
    concurrency: int = 1,
) -> dict[str, Any]:
    """Resolve missing photos for ``places``; write cache + index.

    Sequential and polite (Wikipedia throttles parallel clients with 429): one
    place at a time with a short pause, inside a total ``budget_secs``. A miss is
    recorded only when the lookups SUCCEEDED and found nothing; throttling or a
    network error leaves the place unresolved for the next call. ``concurrency``
    is accepted for compatibility and ignored.

    Returns ``{"photos": {id: url|null}, "resolved": n, "missing": m, "pending": k}``
    covering every place passed in.
    """
    now = time.time() if now is None else now
    index = _load_index(data_dir)
    photos_dir(data_dir).mkdir(parents=True, exist_ok=True)

    todo = [p for p in places if isinstance(p, dict) and isinstance(p.get("id"), int)
            and _needs_resolve(index.get(str(p["id"])), place_key(p), now)]
    if now < _throttled_until(index):
        todo = []  # Wikipedia asked us to wait; report current state, touch nothing
    deadline = time.monotonic() + budget_secs
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

    for place in todo:
        if time.monotonic() >= deadline:
            break
        pid = place["id"]
        key = place_key(place)
        try:
            img_url, page = _resolve_one(place)
        except TransientLookupError as exc:
            wait = exc.retry_after if exc.retry_after else _THROTTLE_DEFAULT_SECS
            _remember_throttle(index, now + min(max(wait, 5.0), 3600.0))
            log.info("travel-desk photo lookup throttled (%s); pausing %.0fs", exc, wait)
            break
        except Exception as exc:  # noqa: BLE001 — one bad place never aborts the batch
            log.debug("travel-desk photo lookup failed for %s: %s", pid, exc)
            continue
        if not img_url:
            index[str(pid)] = {"key": key, "file": None, "source": None, "page": None,
                               "fetched_at": stamp, "fetched_at_ts": now, "miss": True}
            continue
        try:
            body, ct = _http_get_bytes(img_url)
        except Exception as exc:  # noqa: BLE001 — a failed download is retried next call
            log.debug("travel-desk photo download failed for %s: %s", pid, exc)
            continue
        fname = f"{pid}.{_ext_from(ct, img_url)}"
        try:
            (photos_dir(data_dir) / fname).write_bytes(body)
        except OSError as exc:
            log.debug("travel-desk photo write failed for %s: %s", pid, exc)
            continue
        index[str(pid)] = {"key": key, "file": fname, "source": img_url, "page": page,
                           "fetched_at": stamp, "fetched_at_ts": now, "miss": False}
        time.sleep(_PAUSE_SECS)

    _save_index(data_dir, index)

    photos: dict[str, Any] = {}
    resolved = missing = pending = 0
    for p in places:
        if not isinstance(p, dict) or not isinstance(p.get("id"), int):
            continue
        pid = p["id"]
        url = photo_url_for(data_dir, pid)
        photos[str(pid)] = url
        if url is not None:
            resolved += 1
        elif is_confirmed_miss(data_dir, pid):
            missing += 1
        else:
            pending += 1
    return {"photos": photos, "resolved": resolved, "missing": missing, "pending": pending}


def content_type_for(path: Path) -> str:
    """Content-Type for a cached photo file, from its extension."""
    ext = path.suffix.lstrip(".").lower()
    return _CONTENT_TYPE_BY_EXT.get(ext, "application/octet-stream")
