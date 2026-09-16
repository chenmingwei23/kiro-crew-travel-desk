#!/usr/bin/env python3
"""Geocode place queries with Nominatim (OpenStreetMap), 1 request/second.

Usage:
  python3 geocode.py "query one" "query two" ...
      -> prints TSV: query, lat, lng, display_name
  python3 geocode.py --batch <itinerary.json> [--country <iso2>] [--write]
      -> for every place in the itinerary missing lat/lng, resolve "<name>, <address>"
         and fill it in. Prints a TSV report; with --write, saves the file back.
         Places that cannot be resolved are left untouched (never guess a coord).
"""
import json
import sys
import time
import urllib.parse
import urllib.request

UA = "travel-desk/1.0 (KiroCrew app; trip planning)"


def geocode(q, countrycodes=None):
    url = ("https://nominatim.openstreetmap.org/search?format=json&limit=1&addressdetails=0"
           + (f"&countrycodes={countrycodes}" if countrycodes else "")
           + "&q=" + urllib.parse.quote(q))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        hits = json.loads(r.read())
    if not hits:
        return None
    h = hits[0]
    return float(h["lat"]), float(h["lon"]), h.get("display_name", "")


def batch(path, countrycodes=None, write=False):
    itin = json.load(open(path))
    missing = []
    for day in itin.get("days", []):
        for p in day.get("places", []):
            if p.get("lat") is None or p.get("lng") is None:
                missing.append(p)
    for s in itin.get("stays", []):
        if s.get("lat") is None or s.get("lng") is None:
            missing.append(s)

    filled = 0
    for i, p in enumerate(missing):
        if i:
            time.sleep(1.1)
        q = ", ".join(x for x in (p.get("name"), p.get("address")) if x)
        hit = geocode(q, countrycodes)
        if hit:
            p["lat"], p["lng"] = round(hit[0], 5), round(hit[1], 5)
            filled += 1
            print(f"{p.get('name')}\t{p['lat']:.5f}\t{p['lng']:.5f}\t{hit[2][:80]}")
        else:
            print(f"{p.get('name')}\tNOT FOUND\t(left untouched)")

    if write and filled:
        with open(path, "w") as fh:
            json.dump(itin, fh, ensure_ascii=False, indent=2)
        print(f"# wrote {filled} coords back to {path}")
    else:
        print(f"# resolved {filled}/{len(missing)} missing "
              f"(pass --write to save)")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--batch":
        if len(args) < 2:
            raise SystemExit(__doc__)
        path = args[1]
        country = None
        if "--country" in args:
            country = args[args.index("--country") + 1]
        raise SystemExit(batch(path, country, write=("--write" in args)))

    for i, q in enumerate(args):
        if i:
            time.sleep(1.1)
        hit = geocode(q)
        if hit:
            print(f"{q}\t{hit[0]:.5f}\t{hit[1]:.5f}\t{hit[2][:90]}")
        else:
            print(f"{q}\tNOT FOUND")
