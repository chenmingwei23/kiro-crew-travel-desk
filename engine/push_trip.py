#!/usr/bin/env python3
"""Push a JSON itinerary into the trip service (TREK).

Usage:  python3 push_trip.py itinerary.json [--base http://127.0.0.1:3000]
                 [--record <path>] [--replace <trip_id>]

The service URL and login come from the desk configuration (see deskpaths.py):
``data/config.json`` for the URL and ``<desk root>/trek.env`` for
ADMIN_EMAIL / ADMIN_PASSWORD. The file is only read; its contents are never printed.

  --record <path>   after a successful push, write
                    {"trip_id", "url", "pushed_at", "places", "days"} to <path>
                    (the leader stores this as trips/<slug>/trek.json).
  --replace <id>    DELETE /api/trips/<id> first, then create fresh (revise
                    re-push). Without it, every push CREATES a new trip.

Itinerary JSON shape (desk/CONTRACT.md §5; real examples: desk/example-itinerary.en.json, .zh.json):
{
  "title": "...", "description": "...",
  "start_date": "2026-10-01", "end_date": "2026-10-03", "currency": "AUD",
  "transport_mode": "driving",            # trip-wide default: driving|walking|cycling|transit
  "days": [
    {
      "date": "2026-10-01",               # optional; matched to auto-generated day by index otherwise
      "notes": "free-text day notes",     # optional (day-level notes field)
      "cards": [                          # optional: coloured note cards on the day timeline
        {"text": "...", "time": "08:00", "icon": "🚗", "color": null}
      ],
      "places": [
        {"name": "...", "lat": 30.2, "lng": 120.1, "address": "...",
         "notes": "...", "time": "09:00", "end_time": "11:00",
         "duration_minutes": 120, "transport_mode": "driving",   # leg LEAVING this stop
         "website": null, "phone": null, "price": null}
      ]
    }
  ],
  "stays": [                              # optional: hotels; place + accommodation spanning the nights
    {"name": "...", "lat": .., "lng": .., "address": "...", "from_date": "2026-10-01", "to_date": "2026-10-02",
     "check_in": "15:00", "check_out": "10:00", "confirmation": null, "stay_notes": "...", "notes": "..."}
  ]
}
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deskpaths  # noqa: E402
from trek_api import TrekAPI, TrekError  # noqa: E402


def push(itin: dict, api: TrekAPI, replace_id: str | None = None, log=print) -> dict:
    """Create the trip (optionally replacing ``replace_id``). Returns the record dict."""
    base = api.base
    if replace_id:
        api.delete_trip(replace_id)
        log(f"replaced: deleted old trip #{replace_id}")

    trip = api._authed("POST", "/api/trips", {
        "title": itin["title"],
        "description": itin.get("description"),
        "start_date": itin.get("start_date"),
        "end_date": itin.get("end_date"),
        "currency": itin.get("currency", "USD"),
    })
    trip_id = trip["id"]
    log(f"trip #{trip_id}: {trip['title']}  ->  {base}/trips/{trip_id}")

    place_count = 0
    days = api._authed("GET", f"/api/trips/{trip_id}/days")
    days = sorted(days, key=lambda d: d.get("day_number", 0))
    by_date = {d.get("date"): d for d in days if d.get("date")}
    default_mode = itin.get("transport_mode")

    for idx, spec in enumerate(itin.get("days", [])):
        day = by_date.get(spec.get("date")) if spec.get("date") else None
        if day is None:
            if idx < len(days):
                day = days[idx]
            else:
                day = api._authed("POST", f"/api/trips/{trip_id}/days", {"date": spec.get("date")})
                days.append(day)
        day_id = day["id"]

        if spec.get("notes"):
            api._authed("PUT", f"/api/trips/{trip_id}/days/{day_id}", {"notes": spec["notes"]})
        mode = spec.get("transport_mode", default_mode)
        if mode:
            api._authed("PUT", f"/api/trips/{trip_id}/days/{day_id}/transport", {"transport_mode": mode})

        for order, card in enumerate(spec.get("cards", [])):
            api._authed("POST", f"/api/trips/{trip_id}/days/{day_id}/notes", {
                "text": card["text"], "time": card.get("time"), "icon": card.get("icon"),
                "color": card.get("color"), "sort_order": order,
            })

        for p in spec.get("places", []):
            body = {k: p[k] for k in ("name", "lat", "lng", "address", "notes", "website", "phone",
                                      "price", "duration_minutes", "description") if p.get(k) is not None}
            if p.get("time"):
                body["place_time"] = p["time"]
            if p.get("end_time"):
                body["end_time"] = p["end_time"]
            place = api._authed("POST", f"/api/trips/{trip_id}/places", body)
            asg = api._authed("POST", f"/api/trips/{trip_id}/days/{day_id}/assignments",
                              {"place_id": place["id"], "notes": p.get("stop_notes")})
            asg_id = asg["id"] if isinstance(asg, dict) and "id" in asg else None
            if asg_id and (p.get("time") or p.get("end_time")):
                api._authed("PUT", f"/api/trips/{trip_id}/assignments/{asg_id}/time",
                            {"place_time": p.get("time"), "end_time": p.get("end_time")})
            if asg_id and p.get("transport_mode"):
                api._authed("PUT", f"/api/trips/{trip_id}/assignments/{asg_id}/transport",
                            {"transport_mode": p["transport_mode"], "direction": "outgoing"})
            log(f"  day {day.get('day_number', idx + 1)} ({day.get('date')}): + {p['name']}")
            place_count += 1

    # Stays: a hotel is a place in the pool plus an accommodation spanning check-in .. check-out.
    for s in itin.get("stays", []):
        start = by_date.get(s["from_date"])
        end = by_date.get(s["to_date"])
        if not start or not end:
            log(f"  ! stay {s['name']}: dates {s['from_date']}..{s['to_date']} not in trip, skipped")
            continue
        body = {k: s[k] for k in ("name", "lat", "lng", "address", "notes", "website", "phone", "price")
                if s.get(k) is not None}
        place = api._authed("POST", f"/api/trips/{trip_id}/places", body)
        api._authed("POST", f"/api/trips/{trip_id}/accommodations", {
            "place_id": place["id"], "start_day_id": start["id"], "end_day_id": end["id"],
            "check_in": s.get("check_in"), "check_out": s.get("check_out"),
            "confirmation": s.get("confirmation"), "notes": s.get("stay_notes"),
        })
        log(f"  stay {s['from_date']} -> {s['to_date']}: {s['name']}")
        place_count += 1

    return {
        "trip_id": trip_id,
        "url": f"{base}/trips/{trip_id}",
        "pushed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "places": place_count,
        "days": len(itin.get("days", [])),
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 1
    itin_path = argv[0]
    base = None
    if "--base" in argv:
        base = argv[argv.index("--base") + 1]
    record_path = argv[argv.index("--record") + 1] if "--record" in argv else None
    replace_id = argv[argv.index("--replace") + 1] if "--replace" in argv else None

    with open(itin_path, encoding="utf-8") as fh:
        itin = json.load(fh)

    api = TrekAPI(base)
    try:
        api.login()
        record = push(itin, api, replace_id)
    except TrekError as exc:
        print(f"push_trip.py: {exc}", file=sys.stderr)
        return 1

    if record_path:
        with open(record_path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=2)
        print(f"recorded -> {record_path}")
    print(f"done -> {record['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
