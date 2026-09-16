"""Tests for the Travel Desk engine. Offline only — no real TREK, no network.

Run:  python3 -m pytest tests/test_engine_orchestrate.py -x -q
"""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENGINE))

import desk_event  # noqa: E402
import orchestrate  # noqa: E402


@pytest.fixture()
def desk(tmp_path, monkeypatch):
    """Point every engine module at a tmp DESK_ROOT."""
    monkeypatch.setenv("DESK_ROOT", str(tmp_path))
    importlib.reload(orchestrate)
    importlib.reload(desk_event)
    return tmp_path


def _make_trip(desk_root, slug="202610-demo", request_body="目的地：悉尼蓝山\n人数：2 人自驾",
               capsys=None):
    assert orchestrate.cmd_new(_ns(slug=slug)) == 0
    req = desk_root / "trips" / slug / "request.md"
    req.write_text(request_body, encoding="utf-8")
    if capsys is not None:
        capsys.readouterr()  # drain cmd_new's JSON so later reads see only the next command
    return slug, request_body


class _ns:
    def __init__(self, **kw):
        self.__dict__.update(kw)


# ---- new --------------------------------------------------------------------

def test_new_builds_skeleton(desk):
    assert orchestrate.cmd_new(_ns(slug="202610-demo")) == 0
    root = desk / "trips" / "202610-demo"
    assert (root / "request.md").exists()
    for sub in ("research", "debate", "risk", "runs"):
        assert (root / sub).is_dir()


def test_new_refuses_existing_nonempty(desk):
    orchestrate.cmd_new(_ns(slug="202610-demo"))
    assert orchestrate.cmd_new(_ns(slug="202610-demo")) == 1


# ---- plan -------------------------------------------------------------------

def test_plan_full_three_tasks_order_and_depends(desk, capsys):
    slug, body = _make_trip(desk, capsys=capsys)
    assert orchestrate.cmd_plan(_ns(trip=slug, intent="full")) == 0
    out = json.loads(capsys.readouterr().out)
    ids = [t["id"] for t in out["tasks"]]
    assert ids == ["draft", "risk", "brief"]
    by_id = {t["id"]: t for t in out["tasks"]}
    assert by_id["draft"]["depends_on"] == []
    assert by_id["risk"]["depends_on"] == ["draft"]
    assert by_id["brief"]["depends_on"] == ["risk"]


def test_plan_prompts_embed_request_and_sentinel(desk, capsys):
    slug, body = _make_trip(desk, capsys=capsys)
    orchestrate.cmd_plan(_ns(trip=slug, intent="full"))
    out = json.loads(capsys.readouterr().out)
    sentinels = {"draft": "ITINERARY DRAFTED", "risk": "RISK REVIEW WRITTEN",
                 "brief": "BRIEF WRITTEN"}
    for t in out["tasks"]:
        assert body in t["prompt"], f"{t['id']} prompt missing request.md body"
        assert sentinels[t["id"]] in t["prompt"]
        assert t["sentinel"] in t["prompt"]
        # absolute paths and the RUN EVENTS instruction must be embedded
        assert str(desk / "trips" / slug) in t["prompt"]
        assert "desk_event.py append" in t["prompt"]


def test_plan_single_intents(desk, capsys):
    slug, _ = _make_trip(desk, capsys=capsys)
    for intent, tid, sent in [("draft", "draft", "ITINERARY DRAFTED"),
                              ("risk", "risk", "RISK REVIEW WRITTEN"),
                              ("revise", "revise", "ITINERARY REVISED"),
                              ("brief", "brief", "BRIEF WRITTEN")]:
        orchestrate.cmd_plan(_ns(trip=slug, intent=intent))
        out = json.loads(capsys.readouterr().out)
        assert [t["id"] for t in out["tasks"]] == [tid]
        assert out["tasks"][0]["sentinel"] == sent


def test_plan_unknown_trip_fails(desk):
    assert orchestrate.cmd_plan(_ns(trip="nope", intent="full")) == 1


# ---- leaf-plan --------------------------------------------------------------

def test_leaf_plan_stage_agent_sets(desk, capsys):
    slug, _ = _make_trip(desk, capsys=capsys)
    expected = {
        "analysts": {"trip-destination-analyst", "trip-transport-analyst",
                     "trip-lodging-food-analyst", "trip-intel-analyst"},
        "debate-1": {"trip-advocate-packed", "trip-advocate-slow"},
        "debate-2": {"trip-advocate-packed", "trip-advocate-slow"},
        "risk": {"trip-risk-budget", "trip-risk-safety", "trip-risk-stamina"},
    }
    for stage, agents in expected.items():
        orchestrate.cmd_leaf_plan(_ns(trip=slug, stage=stage))
        out = json.loads(capsys.readouterr().out)
        assert {t["agent"] for t in out["tasks"]} == agents
        for t in out["tasks"]:
            assert "DONE" in t["task"]  # every leaf carries a sentinel


# ---- status -----------------------------------------------------------------

def test_status_reports_artifacts(desk, capsys):
    slug, _ = _make_trip(desk, capsys=capsys)
    orchestrate.cmd_status(_ns(trip=slug))
    out = json.loads(capsys.readouterr().out)
    assert out["artifacts"]["request.md"] is True
    assert out["artifacts"]["itinerary.json"] is False


# ---- desk_event -------------------------------------------------------------

def test_desk_event_append_writes_line(desk):
    slug, _ = _make_trip(desk)
    rc = desk_event.main(["append", "--trip", slug, "--who", "planner",
                          "--kind", "delivered", "--msg", "itinerary 已出"])
    assert rc == 0
    ev = desk / "trips" / slug / "runs" / "events.jsonl"
    rows = [json.loads(l) for l in ev.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["who"] == "planner"
    assert rows[-1]["kind"] == "delivered"
    assert rows[-1]["trip"] == slug


def test_desk_event_stage_fields(desk):
    slug, _ = _make_trip(desk)
    desk_event.main(["append", "--trip", slug, "--who", "planner", "--kind", "stage",
                     "--msg", "4 份分析已回", "--stage-name", "分析",
                     "--done", "4", "--total", "4"])
    ev = desk / "trips" / slug / "runs" / "events.jsonl"
    row = json.loads(ev.read_text(encoding="utf-8").splitlines()[-1])
    assert row["stage"] == {"name": "分析", "done": 4, "total": 4}


def test_desk_event_bad_kind_nonzero(desk):
    slug, _ = _make_trip(desk)
    # argparse rejects an out-of-choice --kind with SystemExit(2): a nonzero
    # failure, never a silent success.
    with pytest.raises(SystemExit) as exc:
        desk_event.main(["append", "--trip", slug, "--who", "planner",
                         "--kind", "bogus", "--msg", "x"])
    assert exc.value.code != 0


def test_desk_event_bad_kind_via_build_nonzero(desk):
    slug, _ = _make_trip(desk)
    with pytest.raises(ValueError):
        desk_event.build_event(slug, "planner", "bogus", "x")


def test_desk_event_bad_stage_partial(desk):
    with pytest.raises(ValueError):
        desk_event.build_stage("分析", 4, None)


# ---- push_trip --record (TREK calls monkeypatched) --------------------------

def test_push_trip_record(desk, tmp_path, monkeypatch):
    import push_trip
    importlib.reload(push_trip)

    itin = {
        "title": "demo", "start_date": "2026-10-03", "end_date": "2026-10-04",
        "days": [
            {"date": "2026-10-03", "places": [
                {"name": "A", "lat": -33.7, "lng": 150.3},
                {"name": "B", "lat": -33.6, "lng": 150.2}]},
            {"date": "2026-10-04", "places": [
                {"name": "C", "lat": -32.9, "lng": 151.1}]},
        ],
    }
    itin_path = tmp_path / "itin.json"
    itin_path.write_text(json.dumps(itin), encoding="utf-8")
    record_path = tmp_path / "trek.json"

    # Stub out the login and every network call.
    monkeypatch.setenv("TREK_ADMIN_EMAIL", "x")
    monkeypatch.setenv("TREK_ADMIN_PASSWORD", "y")

    day_seq = [{"id": 1, "day_number": 1, "date": "2026-10-03"},
               {"id": 2, "day_number": 2, "date": "2026-10-04"}]
    place_ids = iter(range(100, 200))

    def fake_call(self, method, path, body=None, timeout=30.0):
        if path == "/api/auth/login":
            return {"token": "t", "user": {"id": 1}}
        if method == "POST" and path == "/api/trips":
            return {"id": 42, "title": body["title"]}
        if method == "GET" and path.endswith("/days"):
            return list(day_seq)
        if method == "POST" and path.endswith("/places"):
            return {"id": next(place_ids)}
        if "assignments" in path and method == "POST":
            return {"id": 900}
        return {}

    monkeypatch.setattr(push_trip.TrekAPI, "call", fake_call)
    monkeypatch.setattr(sys, "argv",
                        ["push_trip.py", str(itin_path), "--record", str(record_path)])
    push_trip.main()

    rec = json.loads(record_path.read_text(encoding="utf-8"))
    assert rec["trip_id"] == 42
    assert rec["url"].endswith("/trips/42")
    assert rec["places"] == 3
    assert rec["days"] == 2
    assert "pushed_at" in rec


def test_push_trip_replace_deletes_first(desk, tmp_path, monkeypatch):
    import push_trip
    importlib.reload(push_trip)

    itin = {"title": "d", "start_date": "2026-10-03", "end_date": "2026-10-03",
            "days": [{"date": "2026-10-03", "places": []}]}
    itin_path = tmp_path / "itin.json"
    itin_path.write_text(json.dumps(itin), encoding="utf-8")

    monkeypatch.setenv("TREK_ADMIN_EMAIL", "x")
    monkeypatch.setenv("TREK_ADMIN_PASSWORD", "y")
    calls = []

    def fake_call(self, method, path, body=None, timeout=30.0):
        calls.append((method, path))
        if path == "/api/auth/login":
            return {"token": "t", "user": {}}
        if method == "POST" and path == "/api/trips":
            return {"id": 7, "title": "d"}
        if path.endswith("/days"):
            return [{"id": 1, "day_number": 1, "date": "2026-10-03"}]
        return {}

    monkeypatch.setattr(push_trip.TrekAPI, "call", fake_call)
    monkeypatch.setattr(sys, "argv",
                        ["push_trip.py", str(itin_path), "--replace", "99"])
    push_trip.main()
    assert ("DELETE", "/api/trips/99") in calls
