"""Backend route tests (API.md §8.2/§8.5).

Handlers are called directly with a fake authenticated request and an AppContext
pointed at a tmp desk root, so no gateway is needed. The tmp tree carries the
values a handler must resolve (a specific slug, an events file), which is what
proves a handler reads ``deskRoot`` instead of the real desk. TREK and the
photo network are always mocked — the suite never hits the wire.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from backend import photos, routes, setup
from backend.paths import LEADER_AGENT, LEADER_SLOT, SERVICE_ACTIONS
from conftest import FakeRequest


def _body(resp: Any) -> Any:
    raw = resp.body
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return json.loads(raw)


def _call(handler, ctx, **req_kwargs):
    request = FakeRequest(**req_kwargs)
    return asyncio.run(handler(request, ctx))


# ---------------------------------------------------------------------------
# a fake TREK client the /trip, /trips, /photos handlers import
# ---------------------------------------------------------------------------

_FAKE_BUNDLE = {
    "trip": {
        "id": 5, "title": "大洋路自驾", "description": "d",
        "start_date": "2026-10-17", "end_date": "2026-10-19",
        "currency": "AUD", "cover_image": None,
    },
    "days": [
        {
            "id": 8, "day_number": 1, "date": "2026-10-17", "title": None,
            "notes": "day one", "default_transport_mode": "driving",
            "notes_items": [{"text": "加油", "time": "09:30", "icon": "⛽", "sort_order": 0}],
            "assignments": [
                {"place_id": 26, "assignment_time": "11:00", "assignment_end_time": "11:30", "order_index": 0},
            ],
        },
    ],
    "places": [
        {"id": 26, "name": "贝尔斯海滩 Bells Beach", "lat": -38.37, "lng": 144.25,
         "address": "a", "price": 12.0, "currency": "AUD", "image_url": None,
         "duration_minutes": 30},
    ],
    "accommodations": [
        {"place_id": 40, "place_name": "Captains", "place_address": "b",
         "place_lat": -38.75, "place_lng": 143.66, "check_in": "15:00",
         "check_out": "10:00", "notes": "n", "start_day_id": 8, "end_day_id": 8},
    ],
}


class _FakeTrek:
    def __init__(self, *, trips=None, bundle=None, raise_http=None):
        self._trips = trips if trips is not None else [
            {"id": 5, "title": "大洋路自驾", "start_date": "2026-10-17",
             "end_date": "2026-10-19", "day_count": 3, "place_count": 16},
        ]
        self._bundle = bundle if bundle is not None else _FAKE_BUNDLE
        self._raise_http = raise_http

    def list_trips(self):
        return self._trips

    def bundle(self, trip_id):
        if self._raise_http is not None:
            raise RuntimeError(f"GET /api/trips/{trip_id}/bundle -> HTTP {self._raise_http}: nope")
        return {"bundle": self._bundle, "days": len(self._bundle["days"]),
                "places": len(self._bundle["places"])}


def _patch_trek(monkeypatch, client):
    monkeypatch.setattr(routes, "_trek_client", lambda ctx: client)


# ---------------------------------------------------------------------------
# registration shape
# ---------------------------------------------------------------------------

REQUIRED_ROUTES = {
    ("GET", "/status"),
    ("GET", "/trips"),
    ("GET", "/trip"),
    ("GET", "/photos"),
    ("GET", "/photo/{place_id}"),
    ("GET", "/org"),
    ("GET", "/run"),
    ("GET", "/local-trips"),
    ("GET", "/setup"),
    ("POST", "/setup"),
    ("POST", "/service/{action}"),
}


def test_register_routes_returns_approutes(app_ctx):
    result = routes.register_routes(app_ctx)
    assert isinstance(result, list)
    from kiro_crew.apps.route_registry import AppRoute

    assert result and all(isinstance(r, AppRoute) for r in result)
    declared = {(str(r.method).upper(), str(r.path)) for r in result}
    assert REQUIRED_ROUTES <= declared, f"missing: {REQUIRED_ROUTES - declared}"
    # proxy route is gone
    assert ("POST", "/proxy/{action}") not in declared


def test_no_proxy_action_allowlist():
    import backend.paths as paths

    assert not hasattr(paths, "PROXY_ACTIONS")
    assert not hasattr(paths, "proxy_url")


def test_unauthenticated_is_401(app_ctx):
    resp = _call(routes.get_run, app_ctx, user=None, query={})
    assert resp.status == 401
    assert _body(resp)["error"] == "unauthorized"


# ---------------------------------------------------------------------------
# /status — no proxy key
# ---------------------------------------------------------------------------

def test_status_shape(app_ctx, monkeypatch):
    async def fake_run(argv, timeout=300.0):
        return 127, "", "no docker here"

    monkeypatch.setattr(routes, "_run", fake_run)
    monkeypatch.setattr(routes.trek_api, "health", lambda url, timeout=3.0: False)
    body = _body(_call(routes.get_status, app_ctx))
    assert body["leader_slot"] == LEADER_SLOT
    assert body["leader_agent"] == LEADER_AGENT
    assert body["trek"]["running"] is False and body["trek"]["reachable"] is False
    assert body["trek"]["configured"] is False
    assert body["trek"]["container"]["running"] is None  # no docker
    assert body["trek"]["url"].endswith(":3000")
    assert body["setup_needed"] is True
    assert "proxy" not in body


class _FakeSession:
    """What ``_trek_client`` hands the probe: the probe asks who the ticket belongs to."""

    def __init__(self, fail: Exception | None = None) -> None:
        self._fail = fail

    def me(self):
        if self._fail:
            raise self._fail
        return {"id": 1}


def test_status_ready_when_reachable_and_login_works(app_ctx, monkeypatch):
    async def fake_run(argv, timeout=300.0):
        return 0, "true", ""

    monkeypatch.setattr(routes, "_run", fake_run)
    monkeypatch.setattr(routes.trek_api, "health", lambda url, timeout=3.0: True)
    setup.write_env(app_ctx, {"ADMIN_EMAIL": "a@b.co", "ADMIN_PASSWORD": "longenough"})
    monkeypatch.setattr(routes, "_trek_client", lambda ctx: _FakeSession())
    routes._auth_cache.clear()
    body = _body(_call(routes.get_status, app_ctx))
    assert body["trek"]["configured"] is True
    assert body["trek"]["login_source"] == "env"
    assert body["trek"]["authenticated"] is True
    assert body["trek"]["connected"] is True and body["trek"]["healthy"] is True
    assert body["setup_needed"] is False


def test_status_connects_on_a_valid_ticket_without_any_login(app_ctx, desk_root, monkeypatch):
    """An existing installation has a ticket the service issued earlier but no
    login on file: the app works with the ticket instead of asking for a login."""
    async def fake_run(argv, timeout=300.0):
        return 127, "", "no docker here"  # nothing to adopt either

    monkeypatch.setattr(routes, "_run", fake_run)
    monkeypatch.setattr(routes.trek_api, "health", lambda url, timeout=3.0: True)
    (desk_root / ".trek_token").write_text("eyJ.ticket.sig")
    monkeypatch.setattr(routes, "_trek_client", lambda ctx: _FakeSession())
    routes._auth_cache.clear(); routes._detect_cache.clear()
    body = _body(_call(routes.get_status, app_ctx))
    assert body["trek"]["configured"] is False
    assert body["trek"]["login_source"] == "ticket"
    assert body["trek"]["connected"] is True
    assert body["setup_needed"] is False


def test_status_expired_ticket_without_login_points_at_settings(app_ctx, desk_root, monkeypatch):
    async def fake_run(argv, timeout=300.0):
        return 127, "", "no docker here"

    monkeypatch.setattr(routes, "_run", fake_run)
    monkeypatch.setattr(routes.trek_api, "health", lambda url, timeout=3.0: True)
    (desk_root / ".trek_token").write_text("stale")
    boom = routes.trek_api.TrekError(0, "no login for the trip service: set it in the app's Settings page")
    monkeypatch.setattr(routes, "_trek_client", lambda ctx: _FakeSession(fail=boom))
    routes._auth_cache.clear(); routes._detect_cache.clear()
    body = _body(_call(routes.get_status, app_ctx))
    assert body["trek"]["connected"] is False and body["setup_needed"] is True
    assert "Settings" in body["trek"]["auth_error"]


_INSPECT = json.dumps([{
    "Name": "/trek",
    "Config": {"Image": "mauriceboe/trek",
               "Env": ["PATH=/usr/bin", "ADMIN_EMAIL=owner@example.com",
                       "ADMIN_PASSWORD=s3cret-from-container", "ENCRYPTION_KEY=" + "k" * 64]},
}])


def _docker_with_trek(calls):
    async def fake_run(argv, timeout=300.0):
        calls.append(argv)
        if argv[:2] == ["docker", "ps"]:
            return 0, "af18c4082e4e\n", ""
        if argv[:2] == ["docker", "inspect"] and argv[2] == "af18c4082e4e":
            return 0, _INSPECT, ""
        if argv[:2] == ["docker", "inspect"]:  # the app-managed container name: not there
            return 1, "", "Error: No such object"
        return 0, "", ""
    return fake_run


def test_status_adopts_the_login_of_a_local_docker_service(app_ctx, desk_root, monkeypatch):
    """No login on file, but a container publishing the port runs on this machine:
    its admin login is tested, saved like a typed one, and the app is connected."""
    calls: list[list[str]] = []
    monkeypatch.setattr(routes, "_run", _docker_with_trek(calls))
    monkeypatch.setattr(routes.trek_api, "health", lambda url, timeout=3.0: True)
    tested = []
    monkeypatch.setattr(routes.setup, "test_login",
                        lambda url, email, pw: (tested.append((url, email, pw)) or
                                                {"reachable": True, "authenticated": True, "error": ""}))
    monkeypatch.setattr(routes, "_trek_client", lambda ctx: _FakeSession())
    routes._auth_cache.clear(); routes._detect_cache.clear()
    body = _body(_call(routes.get_status, app_ctx))
    assert tested == [(body["trek"]["url"], "owner@example.com", "s3cret-from-container")]
    env = setup.read_env(app_ctx)
    assert env["ADMIN_EMAIL"] == "owner@example.com" and env["ADMIN_PASSWORD"] == "s3cret-from-container"
    assert (desk_root / "trek.env").stat().st_mode & 0o777 == 0o600
    assert body["trek"]["login_source"] == "detected" and body["trek"]["adopted_container"] == "trek"
    assert body["trek"]["configured"] is True and body["trek"]["connected"] is True
    assert body["setup_needed"] is False
    ps = [c for c in calls if c[:2] == ["docker", "ps"]]
    assert ps and f"publish={setup.port_of(body['trek']['url'])}" in ps[0]
    # the password never travels through argv or the response
    dumped = json.dumps(body)
    assert "s3cret" not in dumped and not any("s3cret" in tok for c in calls for tok in c)


def test_status_does_not_adopt_a_refused_login_and_backs_off(app_ctx, desk_root, monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(routes, "_run", _docker_with_trek(calls))
    monkeypatch.setattr(routes.trek_api, "health", lambda url, timeout=3.0: True)
    monkeypatch.setattr(routes.setup, "test_login",
                        lambda url, email, pw: {"reachable": True, "authenticated": False,
                                                "error": "the service refused that email/password"})
    routes._auth_cache.clear(); routes._detect_cache.clear()
    body = _body(_call(routes.get_status, app_ctx))
    assert body["trek"]["login_source"] == "none" and body["setup_needed"] is True
    assert not (desk_root / "trek.env").exists()
    n_ps = len([c for c in calls if c[:2] == ["docker", "ps"]])
    _call(routes.get_status, app_ctx)  # within the back-off window: docker is not asked again
    assert len([c for c in calls if c[:2] == ["docker", "ps"]]) == n_ps


def test_status_never_inspects_docker_for_a_remote_address(app_ctx, monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(routes, "_run", _docker_with_trek(calls))
    monkeypatch.setattr(routes.trek_api, "health", lambda url, timeout=3.0: True)
    monkeypatch.setattr(routes, "trek_url", lambda ctx: "http://trek.example.net:3000")
    routes._auth_cache.clear(); routes._detect_cache.clear()
    body = _body(_call(routes.get_status, app_ctx))
    assert body["trek"]["login_source"] == "none"
    assert not any(c[:2] == ["docker", "ps"] for c in calls)


def test_login_from_inspect_parses_env_and_ignores_containers_without_a_login():
    assert setup.login_from_inspect(_INSPECT) == {
        "container": "trek", "image": "mauriceboe/trek",
        "email": "owner@example.com", "password": "s3cret-from-container"}
    other = json.dumps([{"Name": "/db", "Config": {"Image": "postgres", "Env": ["POSTGRES_PASSWORD=x"]}}])
    assert setup.login_from_inspect(other) is None
    assert setup.login_from_inspect("not json") is None
    assert setup.login_from_inspect("") is None


def test_is_local_url():
    assert setup.is_local_url("http://127.0.0.1:3000")
    assert setup.is_local_url("http://localhost:3000/")
    assert setup.is_local_url("http://[::1]:3000")
    assert not setup.is_local_url("http://trek.example.net:3000")
    assert not setup.is_local_url("http://192.168.1.20:3000")
    assert not setup.is_local_url("nonsense")


# ---------------------------------------------------------------------------
# /trips — TREK url + counts; import failure degrades to empty + error, 200
# ---------------------------------------------------------------------------

def test_trips_ok_shape(app_ctx, monkeypatch):
    _patch_trek(monkeypatch, _FakeTrek())
    body = _body(_call(routes.get_trips, app_ctx))
    assert body["error"] == ""
    t = body["trips"][0]
    assert t["id"] == 5
    assert t["day_count"] == 3 and t["place_count"] == 16
    assert t["url"] == "http://127.0.0.1:3000/trips/5"  # TREK itself, not a proxy


def test_trips_degrades_on_import_failure(app_ctx, monkeypatch):
    # No login configured and nothing listening -> graceful empty list, 200.
    monkeypatch.setattr(routes.trek_api, "health", lambda url, timeout=3.0: False)
    resp = _call(routes.get_trips, app_ctx)
    assert resp.status == 200
    body = _body(resp)
    assert body["trips"] == []
    assert "error" in body


# ---------------------------------------------------------------------------
# /trip
# ---------------------------------------------------------------------------

def test_trip_ok(app_ctx, monkeypatch):
    _patch_trek(monkeypatch, _FakeTrek())
    body = _body(_call(routes.get_trip, app_ctx, query={"id": "5"}))
    assert body["trip"]["id"] == 5
    assert body["trip"]["days"] == 1 and body["trip"]["nights"] == 0
    assert body["trip"]["url"] == "http://127.0.0.1:3000/trips/5"
    assert len(body["days"]) == 1
    assert "26" in body["places"]
    assert body["totals"]["stops"] == 1 and body["totals"]["stays"] == 1


def test_trip_bad_id_400(app_ctx, monkeypatch):
    _patch_trek(monkeypatch, _FakeTrek())
    resp = _call(routes.get_trip, app_ctx, query={"id": "abc"})
    assert resp.status == 400


def test_trip_missing_id_400(app_ctx, monkeypatch):
    _patch_trek(monkeypatch, _FakeTrek())
    resp = _call(routes.get_trip, app_ctx, query={})
    assert resp.status == 400


def test_trip_trek_404(app_ctx, monkeypatch):
    _patch_trek(monkeypatch, _FakeTrek(raise_http=404))
    resp = _call(routes.get_trip, app_ctx, query={"id": "99"})
    assert resp.status == 404


def test_trip_unreachable_502(app_ctx, monkeypatch):
    def _boom(ctx):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(routes, "_trek_client", _boom)
    resp = _call(routes.get_trip, app_ctx, query={"id": "5"})
    assert resp.status == 502


# ---------------------------------------------------------------------------
# /photos
# ---------------------------------------------------------------------------

def test_photos_resolves(app_ctx, monkeypatch):
    _patch_trek(monkeypatch, _FakeTrek())

    def fake_resolve(data_dir, places, **kw):
        return {"photos": {"26": "/api/apps/travel-desk/photo/26", "40": None},
                "resolved": 1, "missing": 1}

    monkeypatch.setattr(routes.photos, "resolve_photos", fake_resolve)
    body = _body(_call(routes.get_photos, app_ctx, query={"id": "5"}))
    assert body["resolved"] == 1 and body["missing"] == 1
    assert body["photos"]["26"].endswith("/photo/26")


def test_photos_bad_id_400(app_ctx, monkeypatch):
    _patch_trek(monkeypatch, _FakeTrek())
    resp = _call(routes.get_photos, app_ctx, query={"id": "x"})
    assert resp.status == 400


# ---------------------------------------------------------------------------
# /photo/{place_id}
# ---------------------------------------------------------------------------

def test_photo_non_numeric_400(app_ctx):
    resp = _call(routes.get_photo, app_ctx, match_info={"place_id": "26x"})
    assert resp.status == 400


def test_photo_missing_404(app_ctx):
    resp = _call(routes.get_photo, app_ctx, match_info={"place_id": "999"})
    assert resp.status == 404


def test_photo_served_with_headers(app_ctx, data_dir):
    # seed a cached photo + index
    pdir = photos.photos_dir(data_dir)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "26.jpg").write_bytes(b"\xff\xd8\xff\xe0jpegbytes")
    photos.index_path(data_dir).write_text(
        json.dumps({"26": {"key": "k", "file": "26.jpg", "miss": False}}),
        encoding="utf-8",
    )
    resp = _call(routes.get_photo, app_ctx, match_info={"place_id": "26"})
    assert resp.status == 200
    assert resp.headers["Cache-Control"] == "public, max-age=86400"
    assert resp.content_type == "image/jpeg"
    assert resp.body == b"\xff\xd8\xff\xe0jpegbytes"


# ---------------------------------------------------------------------------
# /org
# ---------------------------------------------------------------------------

def test_org_all_idle_without_events(app_ctx, desk_root, monkeypatch):
    members = [
        {"id": "leader", "title": "团长", "slot_hint": {"slot_key": LEADER_SLOT}},
        {"id": "planner", "title": "行程师", "slot_hint": {"folder": "Travel Desk", "title": "行程师 · itinerary-planner"}},
        {"id": "destination", "title": "目的地分析师", "slot_hint": None},
    ]
    monkeypatch.setattr(routes.deskdata, "load_members", lambda _root: members)
    body = _body(_call(routes.get_org, app_ctx, query={}))
    got = {m["id"]: m for m in body["members"]}
    assert all(m["state"] == "idle" for m in body["members"])
    assert got["leader"]["slot_key"] == LEADER_SLOT
    assert got["planner"]["slot_key"] is None
    assert got["destination"]["slot_key"] is None


def test_org_state_inferred_from_events(app_ctx, desk_root, make_trip, monkeypatch):
    make_trip(
        desk_root, "202610-test",
        events=[
            {"who": "planner", "kind": "dispatched", "msg": "开始规划"},
            {"who": "destination", "kind": "failed", "msg": "查不到坐标"},
            {"who": "briefing", "kind": "delivered", "msg": "简报已交"},
        ],
    )
    members = [
        {"id": "planner", "title": "行程师", "slot_hint": None},
        {"id": "destination", "title": "目的地", "slot_hint": None},
        {"id": "briefing", "title": "简报", "slot_hint": None},
        {"id": "leader", "title": "团长", "slot_hint": None},
    ]
    monkeypatch.setattr(routes.deskdata, "load_members", lambda _root: members)
    body = _body(_call(routes.get_org, app_ctx, query={"trip": "202610-test"}))
    got = {m["id"]: m for m in body["members"]}
    assert got["planner"]["state"] == "working"
    assert got["planner"]["state_msg"] == "开始规划"
    assert got["destination"]["state"] == "blocked"
    assert got["briefing"]["state"] == "idle"
    assert got["leader"]["state"] == "idle"


def test_stale_working_event_reads_idle():
    from backend import deskdata

    fresh = {"who": "lodging", "kind": "stage", "msg": "checking", "at": "2026-09-16T17:00:00+00:00"}
    now = 1789578000.0  # 2026-09-16T17:00:00Z as epoch seconds
    assert deskdata.infer_states([fresh], now=now + 60)["lodging"]["state"] == "working"
    assert deskdata.infer_states([fresh], now=now + 31 * 60)["lodging"]["state"] == "idle"
    blocked = {"who": "intel", "kind": "failed", "msg": "x", "at": "2026-09-16T17:00:00+00:00"}
    assert deskdata.infer_states([blocked], now=now + 3600)["intel"]["state"] == "blocked"


def test_org_missing_members_file_is_empty(app_ctx, tmp_path, monkeypatch):
    monkeypatch.setattr(routes.paths, "app_root", lambda: tmp_path / "nowhere")
    body = _body(_call(routes.get_org, app_ctx, query={}))
    assert body["members"] == []


def test_org_reads_shipped_roster(app_ctx):
    body = _body(_call(routes.get_org, app_ctx, query={}))
    ids = [m["id"] for m in body["members"]]
    assert len(ids) == 13 and ids[0] == "leader"
    leader = body["members"][0]
    assert leader["slot_key"] == LEADER_SLOT
    assert leader["title_en"] and leader["duty_en"]


# ---------------------------------------------------------------------------
# /run
# ---------------------------------------------------------------------------

def test_run_artifact_table(app_ctx, desk_root, make_trip):
    make_trip(
        desk_root, "202610-run", title="青岛自驾",
        artifacts=["itinerary.json", "research/destination.md"],
        events=[{"who": "planner", "kind": "dispatched", "msg": "go"}],
    )
    body = _body(_call(routes.get_run, app_ctx, query={"trip": "202610-run"}))
    assert body["trip"] == "202610-run"
    assert body["request"].startswith("# 青岛自驾")
    arts = body["artifacts"]
    assert arts["itinerary.json"] is True
    assert arts["research/destination.md"] is True
    assert arts["brief.md"] is False
    assert len(body["events"]) == 1


def test_run_no_trips_is_empty(app_ctx):
    body = _body(_call(routes.get_run, app_ctx, query={}))
    assert body["trip"] is None
    assert body["artifacts"] == {}


def test_run_rejects_bad_slug(app_ctx):
    resp = _call(routes.get_run, app_ctx, query={"trip": "../../etc"})
    assert resp.status == 400


# ---------------------------------------------------------------------------
# /local-trips
# ---------------------------------------------------------------------------

def test_local_trips_lists_dirs(app_ctx, desk_root, make_trip):
    make_trip(desk_root, "202610-a", title="行程A")
    make_trip(desk_root, "202611-b", title="行程B")
    body = _body(_call(routes.get_local_trips, app_ctx))
    slugs = {t["slug"] for t in body["trips"]}
    assert slugs == {"202610-a", "202611-b"}


# ---------------------------------------------------------------------------
# service action allowlist
# ---------------------------------------------------------------------------

def test_service_unknown_action_is_400(app_ctx):
    resp = _call(routes.post_service, app_ctx, match_info={"action": "nuke"})
    assert resp.status == 400
    assert "unknown action" in _body(resp)["error"]


@pytest.mark.parametrize("action", sorted(set(SERVICE_ACTIONS) - {"create", "backup"}))
def test_service_known_actions_run_argv(app_ctx, action, monkeypatch):
    calls = []

    async def fake_run(argv, timeout=300.0):
        calls.append(argv)
        return 0, "ok", ""

    async def fake_wait(url, seconds=60.0):
        return True

    monkeypatch.setattr(routes, "_run", fake_run)
    monkeypatch.setattr(routes, "_wait_healthy", fake_wait)
    resp = _call(routes.post_service, app_ctx, match_info={"action": action})
    assert resp.status == 200
    body = _body(resp)
    assert body["ok"] is True and body["action"] == action
    assert calls and all(isinstance(c, list) for c in calls)
    assert all(isinstance(tok, str) for c in calls for tok in c)
    assert all("docker" == c[0] for c in calls)


def test_service_backup_requires_managed_dir(app_ctx):
    resp = _call(routes.post_service, app_ctx, match_info={"action": "backup"})
    assert resp.status == 400


def test_service_backup_tars_the_service_state(app_ctx, desk_root, monkeypatch):
    (desk_root / "trek" / "data").mkdir(parents=True)
    (desk_root / "trek" / "uploads").mkdir(parents=True)
    calls = []

    async def fake_run(argv, timeout=300.0):
        calls.append(argv)
        return 0, "", ""

    monkeypatch.setattr(routes, "_run", fake_run)
    resp = _call(routes.post_service, app_ctx, match_info={"action": "backup"})
    assert resp.status == 200
    assert calls[-1][0] == "tar" and str(desk_root / "trek") in calls[-1]


class _FakeJSONRequest(FakeRequest):
    def __init__(self, payload, **kw):
        super().__init__(**kw)
        self._payload = payload

    async def json(self):
        return self._payload


def test_service_create_writes_env_and_runs_docker(app_ctx, desk_root, monkeypatch):
    calls = []

    async def fake_run(argv, timeout=300.0):
        calls.append(argv)
        return 0, "abc123", ""

    async def fake_wait(url, seconds=60.0):
        return True

    monkeypatch.setattr(routes, "_run", fake_run)
    monkeypatch.setattr(routes, "_wait_healthy", fake_wait)
    req = _FakeJSONRequest({"email": "me@example.com", "password": "longenough", "port": 3200},
                           match_info={"action": "create"})
    resp = asyncio.run(routes.post_service(req, app_ctx))
    assert resp.status == 200, _body(resp)
    body = _body(resp)
    assert body["url"] == "http://127.0.0.1:3200"
    run_cmd = calls[-1]
    assert run_cmd[:3] == ["docker", "run", "-d"]
    assert "127.0.0.1:3200:3000" in run_cmd
    assert "--env-file" in run_cmd and str(desk_root / "trek.env") in run_cmd
    env = setup.read_env(app_ctx)
    assert env["ADMIN_EMAIL"] == "me@example.com"
    assert len(env["ENCRYPTION_KEY"]) == 64
    assert (desk_root / "trek.env").stat().st_mode & 0o777 == 0o600
    assert (desk_root / "trek" / "data").is_dir() and (desk_root / "trek" / "uploads").is_dir()
    assert routes.paths.app_config(app_ctx)["trekUrl"] == "http://127.0.0.1:3200"
    # the env file is only ever passed BY PATH, never expanded into argv
    assert not any("longenough" in tok for tok in run_cmd)


def test_service_create_rejects_weak_input(app_ctx):
    req = _FakeJSONRequest({"email": "nope", "password": "short"}, match_info={"action": "create"})
    resp = asyncio.run(routes.post_service(req, app_ctx))
    assert resp.status == 400


def test_service_create_with_blank_login_generates_one(app_ctx, desk_root, monkeypatch):
    """One click: no email, no password typed. The app makes the admin login,
    stores it in trek.env, and tells the page the email but never the password."""
    calls = []

    async def fake_run(argv, timeout=300.0):
        calls.append(argv)
        return 0, "abc123", ""

    async def fake_wait(url, seconds=60.0):
        return True

    monkeypatch.setattr(routes, "_run", fake_run)
    monkeypatch.setattr(routes, "_wait_healthy", fake_wait)
    req = _FakeJSONRequest({}, match_info={"action": "create"})
    resp = asyncio.run(routes.post_service(req, app_ctx))
    assert resp.status == 200, _body(resp)
    body = _body(resp)
    env = setup.read_env(app_ctx)
    assert body["email"] == env["ADMIN_EMAIL"] == setup.GENERATED_EMAIL
    assert body["env_path"] == str(desk_root / "trek.env")
    assert len(env["ADMIN_PASSWORD"]) >= 16
    assert env["ADMIN_PASSWORD"] not in json.dumps(body)
    assert not any(env["ADMIN_PASSWORD"] in tok for c in calls for tok in c)
    assert (desk_root / "trek.env").stat().st_mode & 0o777 == 0o600


def test_service_create_half_typed_login_is_still_validated(app_ctx):
    req = _FakeJSONRequest({"email": "me@example.com", "password": ""}, match_info={"action": "create"})
    resp = asyncio.run(routes.post_service(req, app_ctx))
    assert resp.status == 400


# ---------------------------------------------------------------------------
# /setup
# ---------------------------------------------------------------------------

def test_get_setup_never_returns_secrets(app_ctx, monkeypatch):
    async def fake_run(argv, timeout=300.0):
        return 0, "Docker version", ""

    monkeypatch.setattr(routes, "_run", fake_run)
    monkeypatch.setattr(routes.trek_api, "health", lambda url, timeout=3.0: False)
    setup.write_env(app_ctx, {"ADMIN_EMAIL": "a@b.co", "ADMIN_PASSWORD": "longenough",
                              "ENCRYPTION_KEY": "k" * 64})
    body = _body(_call(routes.get_setup, app_ctx))
    assert body["email"] == "a@b.co" and body["has_password"] is True
    assert body["docker_available"] is True and body["reachable"] is False
    dumped = json.dumps(body)
    assert "longenough" not in dumped and "kkkk" not in dumped


def test_post_setup_saves_after_successful_login(app_ctx, desk_root, monkeypatch):
    monkeypatch.setattr(routes.setup, "test_login",
                        lambda url, email, pw: {"reachable": True, "authenticated": True, "error": ""})
    req = _FakeJSONRequest({"trek_url": "http://127.0.0.1:3456/", "email": "a@b.co", "password": "longenough"})
    resp = asyncio.run(routes.post_setup(req, app_ctx))
    assert resp.status == 200, _body(resp)
    assert _body(resp)["saved"] is True
    assert routes.paths.app_config(app_ctx)["trekUrl"] == "http://127.0.0.1:3456"
    env = setup.read_env(app_ctx)
    assert env["ADMIN_EMAIL"] == "a@b.co" and env["ADMIN_PASSWORD"] == "longenough"


def test_post_setup_test_only_does_not_save(app_ctx, monkeypatch):
    monkeypatch.setattr(routes.setup, "test_login",
                        lambda url, email, pw: {"reachable": True, "authenticated": True, "error": ""})
    req = _FakeJSONRequest({"trek_url": "127.0.0.1:3456", "email": "a@b.co",
                            "password": "longenough", "test_only": True})
    resp = asyncio.run(routes.post_setup(req, app_ctx))
    assert resp.status == 200
    assert _body(resp)["saved"] is False
    assert "trekUrl" not in routes.paths.app_config(app_ctx) or \
        routes.paths.app_config(app_ctx)["trekUrl"] == "http://127.0.0.1:3000"
    assert not setup.read_env(app_ctx).get("ADMIN_EMAIL")


def test_post_setup_bad_login_is_502_with_reason(app_ctx, monkeypatch):
    monkeypatch.setattr(routes.setup, "test_login",
                        lambda url, email, pw: {"reachable": True, "authenticated": False,
                                                "error": "the service refused that email/password"})
    req = _FakeJSONRequest({"trek_url": "http://127.0.0.1:3456", "email": "a@b.co", "password": "longenough"})
    resp = asyncio.run(routes.post_setup(req, app_ctx))
    assert resp.status == 502
    assert "refused" in _body(resp)["error"]


def test_post_setup_validates_input(app_ctx):
    req = _FakeJSONRequest({"trek_url": "", "email": "a@b.co", "password": "longenough"})
    assert asyncio.run(routes.post_setup(req, app_ctx)).status == 400
    req = _FakeJSONRequest({"trek_url": "http://x:1", "email": "not-an-email", "password": "longenough"})
    assert asyncio.run(routes.post_setup(req, app_ctx)).status == 400


def test_post_proxy_handler_is_gone():
    assert not hasattr(routes, "post_proxy")
    assert not hasattr(routes, "_proxy_argv")
    assert not hasattr(routes, "post_container")
