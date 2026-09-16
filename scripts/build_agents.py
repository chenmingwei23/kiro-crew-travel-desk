#!/usr/bin/env python3
"""Render ``agents/<name>.json`` from ``agents/prompts/<name>.md``.

The gateway installs the JSON files listed in ``app.json`` → ``agents`` into the
user's Kiro agents directory (namespaced ``travel-desk--<name>.json``; the
``name`` field stays the dispatchable name). A prompt has to travel INSIDE the
JSON because a ``file://`` prompt path is absolute and unknown at packaging
time, so this script inlines it.

    python3 scripts/build_agents.py          # write agents/*.json
    python3 scripts/build_agents.py --check  # exit 1 when any file is stale

Host-managed MCP servers (``@kirocrew-core`` for spawn_run, ``@kirocrew-dashboard``
for session_create/session_send) are referenced in ``tools`` only: the gateway
fills in their launch spec when it registers the agent. Public MCP servers the
research agents use are declared inline.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "agents" / "prompts"
OUT = ROOT / "agents"

BASIC = ["execute_bash", "fs_read", "fs_write", "web_fetch", "web_search"]
MANAGER = ["execute_bash", "fs_read", "fs_write", "grep", "glob", "web_fetch", "web_search", "@kirocrew-core"]

HTTP = lambda url: {"type": "http", "url": url, "autoApprove": ["*"]}  # noqa: E731

AGENTS: dict[str, dict] = {
    "trip-tour-leader": {
        "description": "Tour Leader: the desk's conductor. Takes the traveller's one-sentence request, "
                       "runs the planner, risk review and briefing, pushes the itinerary into the trip planner "
                       "and reports back.",
        "tools": ["execute_bash", "fs_read", "fs_write", "grep", "glob", "web_fetch",
                  "@kirocrew-core", "@kirocrew-dashboard"],
    },
    "trip-itinerary-planner": {
        "description": "Itinerary Planner: runs four research analysts and a two-round pace debate, then writes "
                       "the day-by-day itinerary with real coordinates.",
        "tools": MANAGER,
    },
    "trip-risk-pod": {
        "description": "Risk Review: runs the budget, safety and stamina officers and merges their findings into "
                       "one verdict with must-change items.",
        "tools": MANAGER,
    },
    "trip-briefing": {
        "description": "Pre-trip Briefing: the day-before checklist — 24-hour to-dos, one line per day, live weather "
                       "and roads, booking checks, emergency contacts.",
        "tools": ["execute_bash", "fs_read", "fs_write", "web_fetch", "web_search", "@kirocrew-core"],
    },
    "trip-destination-analyst": {
        "description": "Destination Analyst: candidate sights with time, tickets, hours, a one-line reason and a "
                       "source for each; grouped by area.",
        "tools": BASIC,
    },
    "trip-transport-analyst": {
        "description": "Transport Analyst: long-haul options, local transport, a drive-time table, parking and fuel.",
        "tools": BASIC + ["@kiwi", "@skiplagged", "@ferryhopper"],
        "mcpServers": {
            "kiwi": HTTP("https://mcp.kiwi.com"),
            "skiplagged": HTTP("https://mcp.skiplagged.com/mcp"),
            "ferryhopper": HTTP("https://mcp.ferryhopper.com/mcp"),
        },
    },
    "trip-lodging-food-analyst": {
        "description": "Lodging & Food Analyst: where to sleep each night and where to eat, with prices, reasons "
                       "and booking reminders.",
        "tools": BASIC + ["@trivago", "@airbnb"],
        "mcpServers": {
            "trivago": HTTP("https://mcp.trivago.com/mcp"),
            "airbnb": {
                "command": "npx",
                "args": ["-y", "@openbnb/mcp-server-airbnb@0.3.0", "--ignore-robots-txt"],
                "autoApprove": ["*"],
            },
        },
    },
    "trip-intel-analyst": {
        "description": "Intel Analyst: weather, holidays and crowds, closures and alerts, what visitors say, "
                       "documents and insurance.",
        "tools": BASIC,
    },
    "trip-advocate-packed": {
        "description": "Packed Advocate: argues the see-more, dense day plan across two debate rounds.",
        "tools": ["fs_read", "fs_write", "execute_bash", "web_fetch"],
    },
    "trip-advocate-slow": {
        "description": "Slow Advocate: argues the relaxed, slow-paced day plan across two debate rounds.",
        "tools": ["fs_read", "fs_write", "execute_bash", "web_fetch"],
    },
    "trip-risk-budget": {
        "description": "Budget Officer: reviews the plan on cost and returns PASS or CHANGE with must-fix items.",
        "tools": BASIC,
    },
    "trip-risk-safety": {
        "description": "Safety Officer: reviews the plan on safety and returns PASS or CHANGE with must-fix items.",
        "tools": BASIC,
    },
    "trip-risk-stamina": {
        "description": "Stamina Officer: reviews the plan on pacing and fatigue and returns PASS or CHANGE "
                       "with must-fix items.",
        "tools": BASIC,
    },
}

#: The gateway refuses an agent whose file carries an unresolved template token.
PLACEHOLDER_RE = re.compile(r"\{[A-Z][A-Z0-9_]*\}")
FORBIDDEN = ("/home/", "/local/", "/Users/", "aim mcp", "amazon")


def render(name: str) -> dict:
    spec = AGENTS[name]
    prompt = (PROMPTS / f"{name}.md").read_text(encoding="utf-8").rstrip() + "\n"
    agent = {
        "name": name,
        "description": spec["description"],
        "prompt": prompt,
        "tools": list(spec["tools"]),
        "allowedTools": ["*"],
        "includeMcpJson": False,
        "toolsSettings": {"execute_bash": {"autoAllowReadonly": True}},
    }
    if spec.get("mcpServers"):
        agent["mcpServers"] = spec["mcpServers"]
    return agent


def check_text(name: str, text: str) -> list[str]:
    problems = []
    m = PLACEHOLDER_RE.search(text)
    if m:
        problems.append(f"{name}: template-looking token {m.group(0)} would block registration")
    for bad in FORBIDDEN:
        if bad.lower() in text.lower():
            problems.append(f"{name}: forbidden text {bad!r}")
    return problems


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale: list[str] = []
    problems: list[str] = []
    for name in AGENTS:
        rendered = json.dumps(render(name), ensure_ascii=False, indent=2) + "\n"
        problems += check_text(name, rendered)
        target = OUT / f"{name}.json"
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current != rendered:
            stale.append(target.name)
            if not check:
                target.write_text(rendered, encoding="utf-8")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    if check:
        if stale:
            print("stale agent files (run scripts/build_agents.py): " + ", ".join(stale), file=sys.stderr)
            return 1
        print(f"{len(AGENTS)} agent files up to date")
        return 0
    print(f"wrote {len(stale)} changed of {len(AGENTS)} agent files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
