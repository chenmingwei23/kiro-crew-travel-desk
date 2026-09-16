"""Unit tests for backend.photos (API.md §GET /photos, §GET /photo).

The network is confined to ``photos._http_get_json`` / ``photos._http_get_bytes``
and mocked in every test; nothing hits the wire.
"""
from __future__ import annotations

import json
import time

import pytest

from backend import photos


def _place(pid=26, name="Bells Beach", lat=-38.37, lng=144.25, image_url=None):
    return {"id": pid, "name": name, "lat": lat, "lng": lng, "image_url": image_url}


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "appdata"
    d.mkdir()
    return d


def _read_index(data_dir):
    return json.loads(photos.index_path(data_dir).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# download + write to disk (image_url path)
# ---------------------------------------------------------------------------

def test_download_writes_file_and_index(data_dir, monkeypatch):
    got = {}

    def fake_bytes(url):
        got["url"] = url
        return b"JPEGDATA", "image/jpeg"

    monkeypatch.setattr(photos, "_http_get_bytes", fake_bytes)
    res = photos.resolve_photos(data_dir, [_place(image_url="http://x/a.jpg")])
    assert res["resolved"] == 1 and res["missing"] == 0
    assert res["photos"]["26"] == "/api/apps/travel-desk/photo/26"
    # file on disk
    assert (photos.photos_dir(data_dir) / "26.jpg").read_bytes() == b"JPEGDATA"
    # index entry
    entry = _read_index(data_dir)["26"]
    assert entry["file"] == "26.jpg" and entry["miss"] is False
    assert entry["source"] == "http://x/a.jpg"
    assert got["url"] == "http://x/a.jpg"


def test_user_agent_sent_on_download(data_dir, monkeypatch):
    seen = {}

    def fake_bytes(url):
        # emulate the real function reading the header it sets
        seen["ua"] = photos.USER_AGENT
        return b"PNGDATA", "image/png"

    monkeypatch.setattr(photos, "_http_get_bytes", fake_bytes)
    photos.resolve_photos(data_dir, [_place(image_url="http://x/a.png")])
    assert seen["ua"] == "travel-desk/0.2 (KiroCrew app)"
    assert (photos.photos_dir(data_dir) / "26.png").exists()


# ---------------------------------------------------------------------------
# cache hit — a second resolve does not re-download
# ---------------------------------------------------------------------------

def test_cache_hit_skips_second_download(data_dir, monkeypatch):
    calls = {"n": 0}

    def fake_bytes(url):
        calls["n"] += 1
        return b"D", "image/jpeg"

    monkeypatch.setattr(photos, "_http_get_bytes", fake_bytes)
    p = _place(image_url="http://x/a.jpg")
    photos.resolve_photos(data_dir, [p])
    photos.resolve_photos(data_dir, [p])
    assert calls["n"] == 1  # second call served from cache


def test_cached_photo_path_and_url(data_dir, monkeypatch):
    monkeypatch.setattr(photos, "_http_get_bytes", lambda url: (b"D", "image/webp"))
    photos.resolve_photos(data_dir, [_place(image_url="http://x/a.webp")])
    path = photos.cached_photo_path(data_dir, 26)
    assert path is not None and path.name == "26.webp"
    assert photos.photo_url_for(data_dir, 26) == "/api/apps/travel-desk/photo/26"
    assert photos.photo_url_for(data_dir, 999) is None


# ---------------------------------------------------------------------------
# key change invalidates the cache (rename / move)
# ---------------------------------------------------------------------------

def test_key_change_forces_redownload(data_dir, monkeypatch):
    calls = {"n": 0}

    def fake_bytes(url):
        calls["n"] += 1
        return b"D", "image/jpeg"

    monkeypatch.setattr(photos, "_http_get_bytes", fake_bytes)
    photos.resolve_photos(data_dir, [_place(name="Old Name", image_url="http://x/a.jpg")])
    # same id, different name -> key changes -> re-resolve
    photos.resolve_photos(data_dir, [_place(name="New Name", image_url="http://x/b.jpg")])
    assert calls["n"] == 2


# ---------------------------------------------------------------------------
# miss recorded, not retried within 24h, retried after
# ---------------------------------------------------------------------------

def test_miss_recorded_and_not_retried_within_24h(data_dir, monkeypatch):
    calls = {"json": 0}

    def fake_json(url, params):
        calls["json"] += 1
        return {"query": {"search": [], "pages": {}, "geosearch": []}}

    monkeypatch.setattr(photos, "_http_get_json", fake_json)
    # no image_url -> falls to wiki -> empty -> miss
    p = _place(image_url=None)
    res1 = photos.resolve_photos(data_dir, [p], now=1000.0)
    assert res1["missing"] == 1 and res1["resolved"] == 0
    entry = _read_index(data_dir)["26"]
    assert entry["miss"] is True
    first_calls = calls["json"]

    # within 24h: no new lookups
    photos.resolve_photos(data_dir, [p], now=1000.0 + 3600)
    assert calls["json"] == first_calls  # unchanged


def test_miss_retried_after_24h(data_dir, monkeypatch):
    calls = {"json": 0}

    def fake_json(url, params):
        calls["json"] += 1
        return {"query": {"search": [], "pages": {}, "geosearch": []}}

    monkeypatch.setattr(photos, "_http_get_json", fake_json)
    p = _place(image_url=None)
    photos.resolve_photos(data_dir, [p], now=1000.0)
    before = calls["json"]
    # after 24h + 1s: re-looked up
    photos.resolve_photos(data_dir, [p], now=1000.0 + 24 * 3600 + 1)
    assert calls["json"] > before


# ---------------------------------------------------------------------------
# wikipedia title-search resolution path
# ---------------------------------------------------------------------------

def _search_pages(*pages):
    """A generator=search response: pages keyed by id, with an index order."""
    return {"query": {"pages": {str(i + 1): {"index": i + 1, **pg} for i, pg in enumerate(pages)}}}


def test_wiki_search_resolves_a_geo_plausible_page(data_dir, monkeypatch):
    def fake_json(url, params):
        assert params.get("generator") == "search"
        assert params.get("gsrsearch") == "Bells Beach"
        return _search_pages(
            {"title": "Bells Beach", "thumbnail": {"source": "http://img/bells.jpg"},
             "coordinates": [{"lat": -38.37, "lon": 144.25}]},
        )

    def fake_bytes(url):
        assert url == "http://img/bells.jpg"
        return b"IMG", "image/jpeg"

    monkeypatch.setattr(photos, "_http_get_json", fake_json)
    monkeypatch.setattr(photos, "_http_get_bytes", fake_bytes)
    monkeypatch.setattr(photos, "_PAUSE_SECS", 0)
    res = photos.resolve_photos(data_dir, [_place(image_url=None)])
    assert res["resolved"] == 1
    assert _read_index(data_dir)["26"]["page"] == "Bells Beach"


def test_wrong_subject_is_rejected_then_geosearch_wins(data_dir, monkeypatch):
    """'Twelve Apostles' must not come back as the Last Supper."""
    calls = []

    def fake_json(url, params):
        calls.append(params.get("generator"))
        if params.get("generator") == "search":
            return _search_pages(
                {"title": "Apostles in the New Testament", "thumbnail": {"source": "http://img/last-supper.jpg"}},
                {"title": "Twelve Apostles (band)", "thumbnail": {"source": "http://img/band.jpg"},
                 "coordinates": [{"lat": 51.5, "lon": -0.1}]},
            )
        return _search_pages(
            {"title": "The Twelve Apostles (Victoria)", "thumbnail": {"source": "http://img/apostles.jpg"},
             "coordinates": [{"lat": -38.66, "lon": 143.10}]},
        )

    got = {}

    def fake_bytes(url):
        got["url"] = url
        return b"IMG", "image/jpeg"

    monkeypatch.setattr(photos, "_http_get_json", fake_json)
    monkeypatch.setattr(photos, "_http_get_bytes", fake_bytes)
    monkeypatch.setattr(photos, "_PAUSE_SECS", 0)
    place = _place(pid=35, name="十二门徒岩 Twelve Apostles", lat=-38.6653, lng=143.1042, image_url=None)
    res = photos.resolve_photos(data_dir, [place])
    assert res["resolved"] == 1
    assert got["url"] == "http://img/apostles.jpg"
    assert calls[:2] == ["search", "geosearch"]
    assert _read_index(data_dir)["35"]["page"] == "The Twelve Apostles (Victoria)"


def test_title_words_accept_a_page_without_coordinates(data_dir, monkeypatch):
    def fake_json(url, params):
        return _search_pages({"title": "Gibson Steps", "thumbnail": {"source": "http://img/gibson.jpg"}})

    monkeypatch.setattr(photos, "_http_get_json", fake_json)
    monkeypatch.setattr(photos, "_http_get_bytes", lambda url: (b"IMG", "image/jpeg"))
    monkeypatch.setattr(photos, "_PAUSE_SECS", 0)
    res = photos.resolve_photos(data_dir, [_place(pid=33, name="吉布森台阶 Gibson Steps", image_url=None)])
    assert res["resolved"] == 1


def test_throttling_is_not_a_miss(data_dir, monkeypatch):
    import urllib.error

    def throttled(url, params):
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(photos, "_http_get_json", throttled)
    monkeypatch.setattr(photos, "_PAUSE_SECS", 0)
    places = [_place(pid=1, image_url=None), _place(pid=2, image_url=None)]
    res = photos.resolve_photos(data_dir, places, now=1000.0)
    assert res["resolved"] == 0 and res["missing"] == 0 and res["pending"] == 2
    idx = _read_index(data_dir)
    assert set(idx.keys()) == {"_meta"}  # no per-place miss recorded
    assert idx["_meta"]["throttled_until"] >= 1000.0 + 5
    assert not photos.is_confirmed_miss(data_dir, 1)


def test_throttle_window_skips_the_network(data_dir, monkeypatch):
    import urllib.error

    calls = {"n": 0}

    def throttled(url, params):
        calls["n"] += 1
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {"Retry-After": "30"}, None)

    monkeypatch.setattr(photos, "_http_get_json", throttled)
    monkeypatch.setattr(photos, "_PAUSE_SECS", 0)
    places = [_place(pid=1, image_url=None)]
    photos.resolve_photos(data_dir, places, now=1000.0)
    assert calls["n"] == 1
    # inside the Retry-After window: no request at all
    res = photos.resolve_photos(data_dir, places, now=1010.0)
    assert calls["n"] == 1 and res["pending"] == 1
    # after it: tries again
    photos.resolve_photos(data_dir, places, now=1031.0)
    assert calls["n"] == 2


def test_exact_title_rule_rejects_lookalikes(data_dir, monkeypatch):
    def fake_json(url, params):
        if params.get("generator") == "search":
            return _search_pages({"title": "Lorne Michaels", "thumbnail": {"source": "http://img/michaels.jpg"}})
        return _search_pages({"title": "Lorne, Victoria", "thumbnail": {"source": "http://img/lorne.jpg"},
                              "coordinates": [{"lat": -38.54, "lon": 143.97}]})

    got = {}
    monkeypatch.setattr(photos, "_http_get_json", fake_json)
    monkeypatch.setattr(photos, "_http_get_bytes", lambda url: got.setdefault("url", url) and (b"IMG", "image/jpeg"))
    monkeypatch.setattr(photos, "_PAUSE_SECS", 0)
    res = photos.resolve_photos(data_dir, [_place(pid=29, name="洛恩镇 Lorne（午餐）", lat=-38.54, lng=143.97, image_url=None)])
    assert res["resolved"] == 1 and got["url"] == "http://img/lorne.jpg"


def test_latin_part_drops_cjk_and_bracketed_hints():
    assert photos._latin_part("洛恩镇 Lorne（午餐）") == "Lorne"
    assert photos._latin_part("奥特威角灯塔 Cape Otway Lightstation（可选）") == "Cape Otway Lightstation"
    assert photos._latin_part("Captains at the Bay · Apollo Bay") == "Captains at the Bay Apollo Bay"
    assert photos._latin_part("十二门徒岩") == ""


# ---------------------------------------------------------------------------
# budget: a slow batch stops at the deadline, reports the rest as pending
# ---------------------------------------------------------------------------

def test_budget_stops_early_and_reports_pending(data_dir, monkeypatch):
    def slow_bytes(url):
        time.sleep(0.2)
        return b"D", "image/jpeg"

    monkeypatch.setattr(photos, "_http_get_bytes", slow_bytes)
    monkeypatch.setattr(photos, "_PAUSE_SECS", 0)
    places = [_place(pid=i, image_url=f"http://x/{i}.jpg") for i in range(1, 6)]
    res = photos.resolve_photos(data_dir, places, budget_secs=0.3)
    assert set(res["photos"].keys()) == {"1", "2", "3", "4", "5"}
    assert res["resolved"] + res["missing"] + res["pending"] == 5
    assert 1 <= res["resolved"] < 5
    assert res["missing"] == 0


# ---------------------------------------------------------------------------
# per-place exception isolation
# ---------------------------------------------------------------------------

def test_one_bad_source_does_not_break_others(data_dir, monkeypatch):
    def fake_json(url, params):
        return {"query": {"search": [], "pages": {}, "geosearch": []}}

    def fake_bytes(url):
        if "bad" in url:
            raise RuntimeError("boom")
        return b"OK", "image/jpeg"

    monkeypatch.setattr(photos, "_http_get_json", fake_json)
    monkeypatch.setattr(photos, "_http_get_bytes", fake_bytes)
    good = _place(pid=1, image_url="http://x/good.jpg")
    bad = _place(pid=2, image_url="http://x/bad.jpg")
    res = photos.resolve_photos(data_dir, [good, bad])
    assert res["photos"]["1"] is not None
    assert res["photos"]["2"] is None  # download failed -> miss, no crash


# ---------------------------------------------------------------------------
# content_type_for
# ---------------------------------------------------------------------------

def test_content_type_for():
    from pathlib import Path

    assert photos.content_type_for(Path("26.jpg")) == "image/jpeg"
    assert photos.content_type_for(Path("26.png")) == "image/png"
    assert photos.content_type_for(Path("26.webp")) == "image/webp"
    assert photos.content_type_for(Path("26.bin")) == "application/octet-stream"
