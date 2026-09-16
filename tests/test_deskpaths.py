"""deskpaths + the language-aware orchestrator prompts. Offline."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENGINE))

import deskpaths  # noqa: E402
import orchestrate  # noqa: E402


@pytest.fixture()
def desk(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAVEL_DESK_ROOT", str(tmp_path / "desk"))
    monkeypatch.delenv("DESK_ROOT", raising=False)
    monkeypatch.delenv("KIROCREW_HOME", raising=False)
    importlib.reload(deskpaths)
    importlib.reload(orchestrate)
    return tmp_path / "desk"


class _ns:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_desk_root_env_wins(desk):
    assert deskpaths.desk_root() == desk.resolve()
    assert orchestrate.desk_root() == desk.resolve()


def test_desk_root_default_is_gateway_workspace(tmp_path, monkeypatch):
    monkeypatch.delenv("TRAVEL_DESK_ROOT", raising=False)
    monkeypatch.delenv("DESK_ROOT", raising=False)
    monkeypatch.setenv("KIROCREW_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(deskpaths, "load_config", lambda: {})
    assert deskpaths.desk_root() == (tmp_path / "home" / "workspace" / "travel-desk").resolve()


def test_desk_root_from_config(tmp_path, monkeypatch):
    monkeypatch.delenv("TRAVEL_DESK_ROOT", raising=False)
    monkeypatch.delenv("DESK_ROOT", raising=False)
    monkeypatch.setattr(deskpaths, "load_config", lambda: {"deskRoot": str(tmp_path / "custom")})
    assert deskpaths.desk_root() == (tmp_path / "custom").resolve()


def test_gateway_home_from_install_location(tmp_path, monkeypatch):
    monkeypatch.delenv("KIROCREW_HOME", raising=False)
    monkeypatch.setattr(deskpaths, "app_root", lambda: tmp_path / "home" / "apps" / "travel-desk")
    assert deskpaths.gateway_home() == tmp_path / "home"


def test_init_creates_skeleton_and_templates_once(desk, capsys):
    assert orchestrate.cmd_init(_ns()) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["desk_root"] == str(desk.resolve())
    assert (desk / "trips").is_dir() and (desk / "backups").is_dir()
    profile = desk / "memory" / "traveler_profile.md"
    assert profile.is_file() and "Traveller profile" in profile.read_text(encoding="utf-8")
    profile.write_text("mine", encoding="utf-8")
    assert orchestrate.cmd_init(_ns()) == 0  # idempotent: never overwrites memory
    assert profile.read_text(encoding="utf-8") == "mine"


def test_whoami_lists_every_path(desk, capsys):
    assert orchestrate.cmd_whoami(_ns()) == 0
    info = json.loads(capsys.readouterr().out)
    for key in ("app_root", "engine", "desk_root", "trips_dir", "charter", "contract",
                "traveler_profile", "lessons", "trek_url", "trek_env"):
        assert key in info, key
    assert info["desk_root"] == str(desk.resolve())
    assert info["charter"].endswith("desk/CHARTER.md")
    assert Path(info["charter"]).is_file()


def _trip(desk, slug, body, capsys):
    assert orchestrate.cmd_new(_ns(slug=slug)) == 0
    (desk / "trips" / slug / "request.md").write_text(body, encoding="utf-8")
    capsys.readouterr()


def test_request_language_detection(desk, capsys):
    _trip(desk, "202610-zh", "# 行程\n- 目的地：悉尼\n", capsys)
    _trip(desk, "202610-en", "# Trip\n- Destination: Sydney\n", capsys)
    assert orchestrate.request_lang("202610-zh") == "zh"
    assert orchestrate.request_lang("202610-en") == "en"
    assert orchestrate.request_lang("missing") == "en"


def test_new_template_is_english_only(desk, capsys):
    assert orchestrate.cmd_new(_ns(slug="202611-x")) == 0
    text = (desk / "trips" / "202611-x" / "request.md").read_text(encoding="utf-8")
    assert not orchestrate._CJK_RE.search(text)
    assert orchestrate.request_lang("202611-x") == "en"


def test_headings_follow_request_language(desk, capsys):
    _trip(desk, "202610-zh", "- 目的地：悉尼\n", capsys)
    _trip(desk, "202610-en", "- Destination: Sydney\n", capsys)
    zh = orchestrate.leaf_tasks("202610-zh", "analysts")
    en = orchestrate.leaf_tasks("202610-en", "analysts")
    assert "## 候选景点" in zh[0]["task"] and "Chinese" in zh[0]["task"]
    assert "## Candidate sights" in en[0]["task"] and "in English" in en[0]["task"]
    assert "## 候选景点" not in en[0]["task"]
    # the desk_event command carries the member id and the engine path
    assert "--who destination" in en[0]["task"] and "desk_event.py" in en[0]["task"]


def test_plan_tasks_use_english_session_titles(desk, capsys):
    _trip(desk, "202610-en", "- Destination: Sydney\n", capsys)
    assert orchestrate.cmd_plan(_ns(trip="202610-en", intent="full")) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["language"] == "en"
    titles = [t["session_title"] for t in plan["tasks"]]
    assert titles == ["Travel Desk · Itinerary Planner", "Travel Desk · Risk Review", "Travel Desk · Briefing"]
    assert all(t["session_folder"] == "Travel Desk" for t in plan["tasks"])
    draft = plan["tasks"][0]["prompt"]
    assert "ITINERARY DRAFTED" in draft and "example-itinerary.en.json" in draft
    assert str(ENGINE) in draft  # absolute paths are resolved at plan time, not shipped


def test_no_placeholder_tokens_in_generated_prompts(desk, capsys):
    import re
    _trip(desk, "202610-en", "- Destination: Sydney\n", capsys)
    assert orchestrate.cmd_plan(_ns(trip="202610-en", intent="full")) == 0
    text = capsys.readouterr().out
    assert not re.search(r"\{[A-Z][A-Z0-9_]*\}", text)


def test_trek_credentials_from_env_file(desk, monkeypatch):
    monkeypatch.delenv("TREK_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("TREK_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("TREK_ENV", raising=False)
    desk.mkdir(parents=True, exist_ok=True)
    (desk / "trek.env").write_text("ENCRYPTION_KEY=abc\nADMIN_EMAIL=a@b.co\nADMIN_PASSWORD='p w'\n", encoding="utf-8")
    creds = deskpaths.trek_credentials()
    assert creds == {"ADMIN_EMAIL": "a@b.co", "ADMIN_PASSWORD": "p w"}
