"""Turn a TREK bundle into the ``GET /trip`` view model (API.md §GET /trip).

Pure and synchronous — the route calls this via ``asyncio.to_thread`` after
fetching the bundle. ``photo_url_for(place_id)`` returns the cached-photo URL for
a place or ``None`` (the photos module owns the cache); ``trek_url`` is the TREK
base the view links back to. No network, no filesystem: unit-testable with a
plain dict.
"""
from __future__ import annotations

import re
from typing import Any, Callable

_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

#: A run of >=2 CJK ideographs — used to match trip-title place names for cover.
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")


def _weekday_cn(date: str | None) -> str | None:
    """Chinese weekday for an ISO ``YYYY-MM-DD`` date, or None if unparseable."""
    if not date or not isinstance(date, str):
        return None
    try:
        import datetime

        d = datetime.date.fromisoformat(date[:10])
    except (ValueError, TypeError):
        return None
    return _WEEKDAYS[d.weekday()]


def _time_key(value: str | None) -> tuple[int, int]:
    """Sort key for an ``HH:MM`` time. Missing/invalid -> sorts last.

    Returns ``(bucket, minutes)``: bucket 0 has a time, bucket 1 has none, so
    timed items precede untimed ones and untimed items keep their input order
    (Python's sort is stable and bucket-1 minutes are all 0).
    """
    if isinstance(value, str) and re.match(r"^\d{1,2}:\d{2}$", value):
        hh, mm = value.split(":")
        return (0, int(hh) * 60 + int(mm))
    return (1, 0)


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_trip_view(
    bundle: dict,
    photo_url_for: Callable[[int], str | None],
    trek_url: str,
    is_confirmed_miss: Callable[[int], bool] | None = None,
) -> dict:
    """Shape a TREK ``bundle`` into the API.md ``GET /trip`` view model.

    ``photo_url_for(pid)`` -> the ``/photo/<pid>`` URL when a cached image exists,
    else None. ``is_confirmed_miss(pid)`` -> True when a place has been resolved
    and confirmed to have no photo (so it is excluded from ``photos_pending``);
    defaults to "nothing is a confirmed miss".
    """
    if is_confirmed_miss is None:
        is_confirmed_miss = lambda _pid: False  # noqa: E731
    base = trek_url.rstrip("/")
    trip = bundle.get("trip") if isinstance(bundle.get("trip"), dict) else {}
    raw_days = bundle.get("days") if isinstance(bundle.get("days"), list) else []
    raw_places = bundle.get("places") if isinstance(bundle.get("places"), list) else []
    raw_accs = bundle.get("accommodations") if isinstance(bundle.get("accommodations"), list) else []

    trip_id = trip.get("id")
    day_count = len(raw_days)
    nights = max(day_count - 1, 0)

    # place lookup by id (from the bundle's places table)
    places_by_id: dict[int, dict] = {}
    for p in raw_places:
        if isinstance(p, dict) and isinstance(p.get("id"), int):
            places_by_id[p["id"]] = p

    used_place_ids: set[int] = set()
    # day_number -> day_id, to translate a stay's start/end day_id to a day index
    day_id_to_number: dict[int, int] = {}

    out_days: list[dict] = []
    total_stops = 0

    for day in raw_days:
        if not isinstance(day, dict):
            continue
        day_id = day.get("id")
        day_num = day.get("day_number")
        if isinstance(day_id, int) and isinstance(day_num, int):
            day_id_to_number[day_id] = day_num
        date = day.get("date")

        items: list[dict] = []

        # note cards
        for n in day.get("notes_items") or []:
            if not isinstance(n, dict):
                continue
            items.append(
                {
                    "kind": "card",
                    "time": n.get("time"),
                    "text": n.get("text") or "",
                    "icon": n.get("icon"),
                    "_sort": n.get("sort_order") if isinstance(n.get("sort_order"), int) else 0,
                }
            )

        # stops (assignments)
        stops: list[dict] = []
        for a in day.get("assignments") or []:
            if not isinstance(a, dict):
                continue
            pid = a.get("place_id")
            if isinstance(pid, int):
                used_place_ids.add(pid)
            stops.append(
                {
                    "kind": "stop",
                    "place_id": pid,
                    "time": a.get("assignment_time"),
                    "end": a.get("assignment_end_time"),
                    "_order_index": a.get("order_index") if isinstance(a.get("order_index"), int) else 0,
                }
            )

        # merge, then stable-sort by (time bucket/minutes). A card and a stop at
        # the same time: the card sorts first. Untimed keep input order.
        # kind_rank 0 for card, 1 for stop breaks a same-time tie in favor of cards.
        merged = items + stops
        for idx, it in enumerate(merged):
            it["_input"] = idx
        merged.sort(key=lambda it: (_time_key(it.get("time")), 0 if it["kind"] == "card" else 1, it["_input"]))

        # assign stop order (1-based, only counting stops) in sorted order
        order = 0
        final_items: list[dict] = []
        for it in merged:
            if it["kind"] == "stop":
                order += 1
                total_stops += 1
                final_items.append(
                    {
                        "kind": "stop",
                        "place_id": it.get("place_id"),
                        "time": it.get("time"),
                        "end": it.get("end"),
                        "order": order,
                    }
                )
            else:
                final_items.append(
                    {
                        "kind": "card",
                        "time": it.get("time"),
                        "text": it.get("text"),
                        "icon": it.get("icon"),
                    }
                )

        out_days.append(
            {
                "id": day_id,
                "day": day_num,
                "date": date,
                "weekday": _weekday_cn(date),
                "title": day.get("title"),
                "notes": day.get("notes"),
                "transport": day.get("default_transport_mode"),
                "items": final_items,
            }
        )

    # stays (accommodations) -> also mark their place as used
    out_stays: list[dict] = []
    for acc in raw_accs:
        if not isinstance(acc, dict):
            continue
        pid = acc.get("place_id")
        if isinstance(pid, int):
            used_place_ids.add(pid)
        out_stays.append(
            {
                "place_id": pid,
                "name": acc.get("place_name") or acc.get("reservation_title") or "",
                "address": acc.get("place_address"),
                "lat": _to_float(acc.get("place_lat")),
                "lng": _to_float(acc.get("place_lng")),
                "check_in": acc.get("check_in"),
                "check_out": acc.get("check_out"),
                "notes": acc.get("notes"),
                "start_day": day_id_to_number.get(acc.get("start_day_id")) if isinstance(acc.get("start_day_id"), int) else None,
                "end_day": day_id_to_number.get(acc.get("end_day_id")) if isinstance(acc.get("end_day_id"), int) else None,
                "photo": photo_url_for(pid) if isinstance(pid, int) else None,
            }
        )

    # places dict — only the ones used in items/stays
    out_places: dict[str, dict] = {}
    photos_pending = 0
    total_cost = 0.0
    for pid in used_place_ids:
        p = places_by_id.get(pid)
        if p is None:
            continue
        photo = photo_url_for(pid)
        if photo is None and not is_confirmed_miss(pid):
            photos_pending += 1
        price = _to_float(p.get("price"))
        if price is not None:
            total_cost += price
        out_places[str(pid)] = {
            "id": pid,
            "name": p.get("name") or "",
            "address": p.get("address"),
            "lat": _to_float(p.get("lat")),
            "lng": _to_float(p.get("lng")),
            "notes": p.get("notes"),
            "price": price,
            "currency": p.get("currency"),
            "website": p.get("website"),
            "phone": p.get("phone"),
            "category": p.get("category") or p.get("category_name"),
            "duration_minutes": p.get("duration_minutes"),
            "photo": photo,
        }

    cover_place_id = _pick_cover(trip, places_by_id, used_place_ids, photo_url_for)

    return {
        "trip": {
            "id": trip_id,
            "title": trip.get("title") or "",
            "description": trip.get("description") or "",
            "start": trip.get("start_date"),
            "end": trip.get("end_date"),
            "currency": trip.get("currency"),
            "days": day_count,
            "nights": nights,
            "url": f"{base}/trips/{trip_id}" if trip_id is not None else base,
            "cover_place_id": cover_place_id,
        },
        "days": out_days,
        "places": out_places,
        "stays": out_stays,
        "photos_pending": photos_pending,
        "totals": {
            "cost": round(total_cost, 2),
            "stops": total_stops,
            "stays": len(out_stays),
        },
    }


def _pick_cover(
    trip: dict,
    places_by_id: dict[int, dict],
    used_place_ids: set[int],
    photo_url_for: Callable[[int], str | None],
) -> int | None:
    """Cover place id when ``trip.cover_image`` is empty (API.md §GET /trip).

    1. a >=2-char CJK run in the title that appears in a used place's name -> that place
       (中文 titles), or a run of >=2 whole words shared by the title and a used
       place's name, case-insensitive (English titles: "…Twelve Apostles at Sunset"
       picks "Twelve Apostles").
    2. else the first used place (by id) that has a cached photo.
    3. else None.
    """
    if trip.get("cover_image"):
        # TREK already has a cover image; the contract's cover_place_id is only
        # the fallback selection, so leave it unset when TREK supplies one.
        return None

    title = trip.get("title") or ""
    if title:
        # A place matches the title when its name and the title share a run of
        # >=2 consecutive CJK characters (e.g. title "…十二门徒日落…" matches the
        # place "十二门徒岩 Twelve Apostles" on "十二门徒") or, for a Latin title,
        # a run of >=2 consecutive words. Checked in place-id order so the result
        # is deterministic.
        for pid in sorted(used_place_ids):
            p = places_by_id.get(pid)
            if not p:
                continue
            name = str(p.get("name") or "")
            if _shares_cjk_run(name, title) or _shares_word_run(name, title):
                return pid

    for pid in sorted(used_place_ids):
        if photo_url_for(pid) is not None:
            return pid
    return None


_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def _shares_word_run(name: str, title: str, min_words: int = 2) -> bool:
    """True when ``name`` and ``title`` share >=``min_words`` consecutive words.

    Words are Latin-letter tokens compared case-insensitively, so "Twelve Apostles"
    in a place name matches "…(Twelve Apostles at Sunset)" in a title while a single
    shared word ("Road", "Bay") does not.
    """
    name_words = [w.lower() for w in _WORD.findall(name)]
    title_words = [w.lower() for w in _WORD.findall(title)]
    if len(name_words) < min_words or len(title_words) < min_words:
        return False
    title_runs = {tuple(title_words[i:i + min_words]) for i in range(len(title_words) - min_words + 1)}
    return any(tuple(name_words[i:i + min_words]) in title_runs for i in range(len(name_words) - min_words + 1))


def _shares_cjk_run(name: str, title: str, min_len: int = 2) -> bool:
    """True when ``name`` and ``title`` share a run of >=``min_len`` CJK chars."""
    for run in _CJK_RUN.findall(name):
        # every >=min_len-char window of this place-name CJK run
        for i in range(len(run) - min_len + 1):
            for j in range(i + min_len, len(run) + 1):
                if run[i:j] in title:
                    return True
    return False
