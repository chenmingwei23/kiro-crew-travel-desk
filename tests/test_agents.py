"""The 13 shipped agent specs: present, valid, registrable, depersonalised, in sync.

The gateway installs every file named in ``app.json`` -> ``agents``. A spec it
refuses (unsafe name, unresolved ``{PLACEHOLDER}``, invalid JSON) is skipped
with only a log line, so these checks are the one place the failure is loud.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "app.json").read_text(encoding="utf-8"))
AGENT_FILES = [ROOT / p for p in MANIFEST["agents"]]
PLACEHOLDER_RE = re.compile(r"\{[A-Z][A-Z0-9_]*\}")
FORBIDDEN = ("/home/", "/local/", "mingweic", "raymond", "aim mcp", "meshclaw", "brazil", "amazon")
EXPECTED = {
    "trip-tour-leader", "trip-itinerary-planner", "trip-risk-pod", "trip-briefing",
    "trip-destination-analyst", "trip-transport-analyst", "trip-lodging-food-analyst",
    "trip-intel-analyst", "trip-advocate-packed", "trip-advocate-slow",
    "trip-risk-budget", "trip-risk-safety", "trip-risk-stamina",
}


def test_manifest_lists_all_thirteen_agents():
    assert {p.stem for p in AGENT_FILES} == EXPECTED
    for path in AGENT_FILES:
        assert path.is_file(), path


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.stem)
def test_agent_spec_is_registrable(path: Path):
    text = path.read_text(encoding="utf-8")
    spec = json.loads(text)
    assert spec["name"] == path.stem
    assert "/" not in spec["name"] and "\\" not in spec["name"]
    assert isinstance(spec["prompt"], str) and len(spec["prompt"]) > 800
    assert spec["tools"] and spec["allowedTools"] == ["*"]
    assert spec["includeMcpJson"] is False
    assert not PLACEHOLDER_RE.search(text), "an {UPPER} token makes the gateway skip the agent"
    low = text.lower()
    for bad in FORBIDDEN:
        assert bad not in low, f"{path.name} contains {bad!r}"
    # the prompt tells the agent how to find the desk at runtime
    assert 'apps/travel-desk/engine/orchestrate.py' in spec["prompt"]
    assert "whoami" in spec["prompt"]
    # every @server grant is either host-managed or declared inline
    inline = set((spec.get("mcpServers") or {}).keys())
    for tool in spec["tools"]:
        if tool.startswith("@"):
            name = tool[1:].split("/")[0]
            assert name in inline or name in ("kirocrew-core", "kirocrew-dashboard"), tool


def test_only_managers_get_host_tools():
    for path in AGENT_FILES:
        spec = json.loads(path.read_text(encoding="utf-8"))
        tools = set(spec["tools"])
        if path.stem == "trip-tour-leader":
            assert {"@kirocrew-core", "@kirocrew-dashboard"} <= tools
        elif path.stem in ("trip-itinerary-planner", "trip-risk-pod", "trip-briefing"):
            assert "@kirocrew-core" in tools and "@kirocrew-dashboard" not in tools
        else:
            assert not tools & {"@kirocrew-core", "@kirocrew-dashboard"}, path.stem


def test_generated_specs_match_prompts():
    """``scripts/build_agents.py --check`` is the sync gate; run it as a subprocess."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_agents.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_prompts_have_no_personal_or_machine_references():
    for path in sorted((ROOT / "agents" / "prompts").glob("*.md")):
        if path.name == "README.md":
            continue
        low = path.read_text(encoding="utf-8").lower()
        for bad in FORBIDDEN:
            assert bad not in low, f"{path.name} contains {bad!r}"


def test_roster_matches_agents_and_session_titles():
    roster = json.loads((ROOT / "desk" / "members.json").read_text(encoding="utf-8"))["members"]
    assert {m["agent"] for m in roster} == EXPECTED
    assert len(roster) == 13
    sys.path.insert(0, str(ROOT / "engine"))
    import orchestrate  # noqa: E402

    titles = {m["slot_hint"]["title"] for m in roster if m.get("resident") and m["slot_hint"].get("title")}
    assert titles == set(orchestrate.SESSION_TITLES.values())
    leader = next(m for m in roster if m["id"] == "leader")
    assert leader["slot_hint"] == {"slot_key": "travel-desk-leader"}
    for m in roster:
        for key in ("title", "duty", "title_en", "duty_en", "avatar_letter", "avatar_letter_en"):
            assert m.get(key), f"{m['id']} missing {key}"
        assert "trek" not in (m["duty"] + m["duty_en"]).lower(), m["id"]
