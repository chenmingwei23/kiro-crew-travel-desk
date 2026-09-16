"""Unit tests for backend.trekdata.build_trip_view (API.md §GET /trip).

Pure function — no network, no filesystem. ``photo_url_for`` is a plain lambda.
"""
from __future__ import annotations

from backend import trekdata

TREK = "http://127.0.0.1:3000"


def _bundle(**over):
    b = {
        "trip": {
            "id": 5, "title": "大洋路自驾", "description": "d",
            "start_date": "2026-10-17", "end_date": "2026-10-19",
            "currency": "AUD", "cover_image": None,
        },
        "days": [
            {
                "id": 8, "day_number": 1, "date": "2026-10-17", "title": None,
                "notes": "day one", "default_transport_mode": "driving",
                "notes_items": [
                    {"text": "加油", "time": "09:30", "icon": "⛽", "sort_order": 0},
                    {"text": "无时间提示", "time": None, "icon": "ℹ️", "sort_order": 9},
                ],
                "assignments": [
                    {"place_id": 27, "assignment_time": "12:00", "assignment_end_time": "12:45", "order_index": 1},
                    {"place_id": 26, "assignment_time": "11:00", "assignment_end_time": "11:30", "order_index": 0},
                ],
            },
        ],
        "places": [
            {"id": 26, "name": "贝尔斯海滩 Bells Beach", "lat": -38.37, "lng": 144.25,
             "address": "a", "price": 12.0, "currency": "AUD", "duration_minutes": 30},
            {"id": 27, "name": "斯普利特角灯塔 Split Point", "lat": -38.46, "lng": 144.10,
             "address": "b", "price": None, "duration_minutes": 45},
            {"id": 99, "name": "未安排的地点 Unused", "lat": 0, "lng": 0, "price": 500.0},
        ],
        "accommodations": [
            {"place_id": 40, "place_name": "Captains", "place_address": "c",
             "place_lat": -38.75, "place_lng": 143.66, "check_in": "15:00",
             "check_out": "10:00", "notes": "n", "start_day_id": 8, "end_day_id": 8},
        ],
    }
    b.update(over)
    return b


def _no_photos(_pid):
    return None


def test_items_sorted_by_time_stops_ordered():
    view = trekdata.build_trip_view(_bundle(), _no_photos, TREK)
    items = view["days"][0]["items"]
    # 09:30 card, 11:00 stop(order1), 12:00 stop(order2), then untimed card last
    assert [it["kind"] for it in items] == ["card", "stop", "stop", "card"]
    assert items[0]["time"] == "09:30"
    assert items[1]["place_id"] == 26 and items[1]["order"] == 1
    assert items[2]["place_id"] == 27 and items[2]["order"] == 2
    assert items[3]["text"] == "无时间提示"  # untimed sorts last


def test_same_time_card_before_stop():
    b = _bundle()
    b["days"][0]["notes_items"] = [{"text": "同时便签", "time": "11:00", "icon": "!", "sort_order": 0}]
    view = trekdata.build_trip_view(b, _no_photos, TREK)
    items = view["days"][0]["items"]
    at_11 = [it for it in items if it.get("time") == "11:00"]
    assert at_11[0]["kind"] == "card"
    assert at_11[1]["kind"] == "stop"


def test_weekday_and_nights():
    view = trekdata.build_trip_view(_bundle(), _no_photos, TREK)
    assert view["days"][0]["weekday"] == "周六"  # 2026-10-17 is a Saturday
    assert view["trip"]["nights"] == 0  # 1 day -> 0 nights
    assert view["trip"]["days"] == 1


def test_places_filtered_to_used_only():
    view = trekdata.build_trip_view(_bundle(), _no_photos, TREK)
    keys = set(view["places"].keys())
    # 26 + 27 are used and have a places-table row; 99 is unused; 40 is a stay
    # place with no row in the bundle places table, so it is not in `places`.
    assert keys == {"26", "27"}
    assert "99" not in keys


def test_totals_cost_sums_used_places():
    view = trekdata.build_trip_view(_bundle(), _no_photos, TREK)
    # 26 -> 12.0, 27 -> None(0), 40 -> no price row in places table(0); 99 excluded
    assert view["totals"]["cost"] == 12.0
    assert view["totals"]["stops"] == 2
    assert view["totals"]["stays"] == 1


def test_cover_by_title_cjk_match():
    b = _bundle()
    b["trip"]["title"] = "去贝尔斯海滩看浪"  # contains 贝尔斯海滩
    view = trekdata.build_trip_view(b, _no_photos, TREK)
    assert view["trip"]["cover_place_id"] == 26


def test_cover_by_shared_cjk_substring():
    # title carries "十二门徒" as part of a longer run; place name is "十二门徒岩".
    b = _bundle()
    b["trip"]["title"] = "大洋路（十二门徒日落）"
    b["places"][0]["name"] = "十二门徒岩 Twelve Apostles"  # place 26
    view = trekdata.build_trip_view(b, _no_photos, TREK)
    assert view["trip"]["cover_place_id"] == 26


def test_cover_first_with_photo_when_no_title_match():
    b = _bundle()
    b["trip"]["title"] = "无地名标题"

    def photo_for(pid):
        return "/photo/27" if pid == 27 else None

    view = trekdata.build_trip_view(b, photo_for, TREK)
    assert view["trip"]["cover_place_id"] == 27


def test_cover_by_english_title_word_run():
    # An English title shares the two-word run "Twelve Apostles" with place 27.
    b = _bundle()
    b["trip"]["title"] = "Great Ocean Road · 3-Day Melbourne Loop (Twelve Apostles at Sunset)"
    b["places"][1]["name"] = "Twelve Apostles"  # place 27
    view = trekdata.build_trip_view(b, _no_photos, TREK)
    assert view["trip"]["cover_place_id"] == 27


def test_cover_english_single_shared_word_is_not_a_match():
    # "Road" alone appears in both; one word is not a run, so no title match and
    # (no photos) no cover.
    b = _bundle()
    b["trip"]["title"] = "Great Ocean Road weekend"
    b["places"][0]["name"] = "Road House Diner"
    view = trekdata.build_trip_view(b, _no_photos, TREK)
    assert view["trip"]["cover_place_id"] is None


def test_cover_none_when_nothing_matches():
    b = _bundle()
    b["trip"]["title"] = "无地名标题"
    view = trekdata.build_trip_view(b, _no_photos, TREK)
    assert view["trip"]["cover_place_id"] is None


def test_photo_url_threaded_into_places_and_pending():
    def photo_for(pid):
        return f"/photo/{pid}" if pid == 26 else None

    view = trekdata.build_trip_view(_bundle(), photo_for, TREK)
    assert view["places"]["26"]["photo"] == "/photo/26"
    assert view["places"]["27"]["photo"] is None
    # only 27 (a places-table place) lacks a photo -> pending 1
    assert view["photos_pending"] == 1


def test_stay_day_index_and_photo():
    view = trekdata.build_trip_view(_bundle(), _no_photos, TREK)
    stay = view["stays"][0]
    assert stay["place_id"] == 40
    assert stay["start_day"] == 1 and stay["end_day"] == 1
    assert stay["photo"] is None


def test_empty_bundle_is_safe():
    view = trekdata.build_trip_view({}, _no_photos, TREK)
    assert view["days"] == []
    assert view["places"] == {}
    assert view["totals"] == {"cost": 0, "stops": 0, "stays": 0}
    assert view["trip"]["days"] == 0 and view["trip"]["nights"] == 0
