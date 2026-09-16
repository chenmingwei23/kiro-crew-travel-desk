#!/usr/bin/env python3
"""Travel Desk orchestration — one command gives a manager everything.

Each manager runs ONE command to get exactly the tasks it should dispatch; it
never hand-writes a prompt. See desk/CONTRACT.md §4.

    python3 engine/orchestrate.py whoami                 # resolved paths as JSON (agents run this first)
    python3 engine/orchestrate.py init                   # create the desk root skeleton (idempotent)
    python3 engine/orchestrate.py new       --slug <slug>
    python3 engine/orchestrate.py plan      --trip <slug> --intent full|draft|risk|revise|brief
    python3 engine/orchestrate.py leaf-plan --trip <slug> --stage analysts|debate-1|debate-2|risk
    python3 engine/orchestrate.py status    --trip <slug>

`plan` output is for the LEADER (trip-tour-leader): resident-session tasks its
three direct reports run (conductor protocol). `leaf-plan` output is for the
itinerary-planner / risk-pod: leaf `spawn_run` tasks that run in parallel.

Task prompts are written in English. The CONTENT language (file bodies, place
notes, the day titles that end up in the trip) follows the language of the
trip's request.md: any CJK character in it means Chinese, otherwise English.
Section headings inside the artifacts are chosen from the matching table below
so downstream readers always find the same structure.

Python 3.10+ standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deskpaths  # noqa: E402

SESSION_FOLDER = deskpaths.SESSION_FOLDER


def desk_root() -> Path:
    return deskpaths.desk_root()


def trip_dir(slug: str) -> Path:
    return desk_root() / "trips" / slug


def engine_dir() -> Path:
    return deskpaths.app_root() / "engine"


# ---- §5 trip products (relative paths under trips/<slug>/) -----------------

ARTIFACTS = [
    "request.md",
    "research/destination.md", "research/transport.md",
    "research/lodging-food.md", "research/intel.md",
    "debate/packed-1.md", "debate/slow-1.md",
    "debate/packed-2.md", "debate/slow-2.md", "debate/verdict.md",
    "itinerary.json",
    "risk/budget.md", "risk/safety.md", "risk/stamina.md", "risk/summary.md",
    "brief.md", "trek.json",
    "runs/events.jsonl",
]

# The template is English only ON PURPOSE: the request language is detected by
# the presence of CJK characters, so a Chinese-labelled template would make
# every English request look Chinese.
REQUEST_TEMPLATE = """# Trip request · {slug}

> The leader fills this in; every line is input for the analysts. Leave a line
> blank and the analysts will fill it themselves, marking it as an assumption.

- Destination:
- Dates: (YYYY-MM-DD to YYYY-MM-DD)
- Travellers: (adults / children / seniors)
- Transport: (self-drive / public transport / walking / mixed)
- Budget: (total, or a per-day tier)
- Already booked: (flight numbers, hotel names and check-in dates)
- Preferences: (must-see, must-eat, interests)
- Pace: (packed / slow / balanced)
- Avoid: (places or kinds of places to skip, dislikes)
"""

_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")

LANG_NAME = {"zh": "Chinese (简体中文)", "en": "English"}

#: Fixed section headings per artifact, per content language (CONTRACT §6).
HEADINGS: dict[str, dict[str, list[str]]] = {
    "destination": {
        "zh": ["## 候选景点", "## 按区域分组", "## 不推荐及理由"],
        "en": ["## Candidate sights", "## Grouped by area", "## Not recommended, and why"],
    },
    "transport": {
        "zh": ["## 大交通", "## 当地交通", "## 车程表", "## 停车与加油"],
        "en": ["## Long-haul transport", "## Local transport", "## Drive-time table", "## Parking and fuel"],
    },
    "lodging": {
        "zh": ["## 住宿候选", "## 餐厅候选", "## 预订提醒"],
        "en": ["## Lodging candidates", "## Restaurant candidates", "## Booking reminders"],
    },
    "intel": {
        "zh": ["## 天气", "## 节假日与人流", "## 关闭 / 施工 / 预警", "## 口碑要点", "## 签证 / 证件 / 保险"],
        "en": ["## Weather", "## Holidays and crowds", "## Closures / works / alerts",
               "## What visitors say", "## Visas / documents / insurance"],
    },
    "debate": {
        "zh": ["## 主张", "## 逐日方案", "## 反驳对方"],
        "en": ["## Position", "## Day-by-day plan", "## Rebuttal"],
    },
    "verdict": {
        "zh": ["## 采纳的节奏", "## 每天取舍", "## 理由"],
        "en": ["## Pace adopted", "## Trade-offs per day", "## Reasons"],
    },
    "risk": {
        "zh": ["## 发现", "## 必改", "## 建议", "## 便签卡"],
        "en": ["## Findings", "## Must change", "## Suggestions", "## Note cards"],
    },
    "summary": {
        "zh": ["## 必改（合并去重）", "## 建议", "## 便签卡（合并）", "## 三方分歧与裁决"],
        "en": ["## Must change (merged)", "## Suggestions", "## Note cards (merged)",
               "## Disagreements and rulings"],
    },
    "brief": {
        "zh": ["## 出发前 24h 清单", "## 逐日一句话", "## 天气与路况", "## 预订核对", "## 紧急联络"],
        "en": ["## 24 hours before departure", "## One line per day", "## Weather and roads",
               "## Booking check", "## Emergency contacts"],
    },
}

#: Column headings for the tables the analysts produce.
TABLE_COLUMNS = {
    "destination": {
        "zh": "名称 | 地址 | 建议时长 | 门票 | 开放时间 | 一句话理由 | 来源URL",
        "en": "Name | Address | Suggested time | Tickets | Opening hours | Why go (one line) | Source URL",
    },
    "drive": {
        "zh": "从 | 到 | 公里 | 分钟 | 备注",
        "en": "From | To | km | minutes | Notes",
    },
    "lodging": {
        "zh": "名称 | 区域 | 每晚价 | 理由 | 来源URL",
        "en": "Name | Area | Price per night | Why | Source URL",
    },
}

UNVERIFIED = {"zh": "未核实", "en": "unverified"}
NO_LONG_HAUL = {"zh": "自驾，无大交通", "en": "self-drive, no long-haul transport"}


# ---- helpers ----------------------------------------------------------------

def request_lang(slug: str) -> str:
    """``zh`` when request.md contains any CJK character, else ``en``."""
    try:
        text = (trip_dir(slug) / "request.md").read_text(encoding="utf-8")
    except OSError:
        return "en"
    return "zh" if _CJK_RE.search(text) else "en"


def read_request(slug: str) -> str:
    req = trip_dir(slug) / "request.md"
    if not req.exists():
        raise ValueError(f"trips/{slug}/request.md does not exist; run `new --slug {slug}` first")
    return req.read_text(encoding="utf-8")


def abspath(slug: str, rel: str) -> str:
    return str(trip_dir(slug) / rel)


def headings(kind: str, lang: str) -> str:
    return ", ".join(f"`{h}`" for h in HEADINGS[kind][lang])


def language_rule(lang: str) -> str:
    name = LANG_NAME[lang]
    return (
        f"CONTENT LANGUAGE: write every file body, note and title in {name} — the language "
        "of the request. Place names keep their local/official spelling; addresses stay in "
        "the local language; paths, commands and JSON keys stay English."
    )


def run_events_line(slug: str, member: str) -> str:
    return (
        "RUN EVENTS: after every key action run "
        f"`python3 {engine_dir()}/desk_event.py append --trip {slug} --who {member} "
        "--kind dispatched|stage|delivered|failed|note --msg \"<one plain sentence>\" "
        "[--stage-name <name> --done <n> --total <m>]`. The app draws this run from that log."
    )


def preamble(slug: str, role_line: str) -> str:
    return f"""{role_line}

DESK_ROOT: {desk_root()}
ENGINE: {engine_dir()}
Trip slug: {slug}

Read `{deskpaths.charter_path()}` first (the desk charter) — every rule below comes from it.

## The request (request.md, verbatim)
```
{read_request(slug)}
```
"""


# ---- init / whoami -----------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> int:
    info = deskpaths.ensure_desk()
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def cmd_whoami(args: argparse.Namespace) -> int:
    print(json.dumps(deskpaths.describe(), ensure_ascii=False, indent=2))
    return 0


# ---- new --------------------------------------------------------------------

def cmd_new(args: argparse.Namespace) -> int:
    slug = args.slug.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", slug):
        print(f"orchestrate.py: slug {slug!r} must be [A-Za-z0-9][A-Za-z0-9._-]*", file=sys.stderr)
        return 1
    deskpaths.ensure_desk()
    root = trip_dir(slug)
    if root.exists() and any(root.iterdir()):
        print(f"orchestrate.py: trips/{slug}/ already exists and is not empty", file=sys.stderr)
        return 1
    for sub in ("research", "debate", "risk", "runs"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    req = root / "request.md"
    if not req.exists():
        req.write_text(REQUEST_TEMPLATE.format(slug=slug), encoding="utf-8")
    print(json.dumps({
        "trip": slug,
        "created": str(root),
        "request": str(req),
        "next": f"fill in {req}, then run: plan --trip {slug} --intent full",
    }, ensure_ascii=False, indent=2))
    return 0


# ---- manager prompts (leader -> resident reports) ---------------------------

def draft_prompt(slug: str) -> str:
    lang = request_lang(slug)
    return preamble(slug, "You are the **Itinerary Planner (trip-itinerary-planner)**, a resident "
                          "session. Turn the request into itinerary.json.") + f"""
## The chain you run
1. `python3 {engine_dir()}/orchestrate.py leaf-plan --trip {slug} --stage analysts`
   -> `spawn_run(tasks=[...])` the 4 analysts in parallel; wait for each `<ROLE> DONE`.
   Outputs: `{abspath(slug, 'research/destination.md')}`, `{abspath(slug, 'research/transport.md')}`,
   `{abspath(slug, 'research/lodging-food.md')}`, `{abspath(slug, 'research/intel.md')}`.
2. `leaf-plan --stage debate-1` -> the packed and slow advocates each write round 1 (reading research/*).
   `leaf-plan --stage debate-2` -> each writes round 2 (reading the other side's round 1).
   Outputs: `{abspath(slug, 'debate/packed-1.md')}` and 3 more.
3. You write `{abspath(slug, 'debate/verdict.md')}` with exactly these headings: {headings('verdict', lang)}.
4. You write `{abspath(slug, 'itinerary.json')}` (contract: desk/CONTRACT.md §5; a real example in this
   language is `{deskpaths.app_root()}/desk/example-itinerary.{lang}.json`).
   Hard rules: 3-5 places per day; `time`/`end_time` as `HH:MM`; `transport_mode` is the mode of the leg
   LEAVING that stop; coordinates must be real (resolve with `python3 {engine_dir()}/geocode.py`,
   drop a place you cannot resolve — never guess); `notes` carry why to go / what to order / parking /
   tickets / closing time; `cards` are timeline note cards; add `stays` for the nights.

{language_rule(lang)}

{run_events_line(slug, 'planner')}

When done, the LAST line of your reply must be exactly:
`ITINERARY DRAFTED: {abspath(slug, 'itinerary.json')}`
"""


def risk_prompt(slug: str) -> str:
    lang = request_lang(slug)
    return preamble(slug, "You are the **Risk Review (trip-risk-pod)**, a resident session. Review "
                          "itinerary.json and merge the three risk officers' findings.") + f"""
## The chain you run
1. `python3 {engine_dir()}/orchestrate.py leaf-plan --trip {slug} --stage risk`
   -> `spawn_run(tasks=[...])` the 3 risk officers (budget / safety / stamina) in parallel; each reads
   `{abspath(slug, 'itinerary.json')}` + `{abspath(slug, 'research')}/*`.
   Outputs: `{abspath(slug, 'risk/budget.md')}`, `{abspath(slug, 'risk/safety.md')}`,
   `{abspath(slug, 'risk/stamina.md')}` (first line of each: `VERDICT: PASS` or `VERDICT: CHANGE`).
2. You write `{abspath(slug, 'risk/summary.md')}`: FIRST LINE `VERDICT: PASS` or `VERDICT: REVISE`
   (REVISE when any officer says CHANGE and the change materially affects the plan), then exactly
   these headings: {headings('summary', lang)}. Note cards are one JSON object per line:
   `{{"date":"YYYY-MM-DD","text":"...","time":"HH:MM","icon":"⛽"}}`.

{language_rule(lang)}

{run_events_line(slug, 'risk')}

When done, the LAST line of your reply must be exactly:
`RISK REVIEW WRITTEN: {abspath(slug, 'risk/summary.md')} | VERDICT: PASS|REVISE`
"""


def revise_prompt(slug: str) -> str:
    lang = request_lang(slug)
    return preamble(slug, "You are the **Itinerary Planner (trip-itinerary-planner)**, a resident "
                          "session. The risk review returned REVISE: apply ONE revision round.") + f"""
## What to do
1. Read `{abspath(slug, 'risk/summary.md')}`: the merged must-change list and the merged note cards.
2. Edit `{abspath(slug, 'itinerary.json')}` in place: apply every must-change item to that day's stop;
   merge the requested note cards into that day's `cards`. Coordinates must stay real.
3. Do not widen the scope — only resolve the risk items.

{language_rule(lang)}

{run_events_line(slug, 'planner')}

When done, the LAST line of your reply must be exactly:
`ITINERARY REVISED: {abspath(slug, 'itinerary.json')}`
"""


def brief_prompt(slug: str) -> str:
    lang = request_lang(slug)
    return preamble(slug, "You are the **Pre-trip Briefing (trip-briefing)**, a resident session. "
                          "Produce the one-page checklist for the day before departure.") + f"""
## What to do
Read `{abspath(slug, 'itinerary.json')}`, `{abspath(slug, 'risk/summary.md')}`,
`{abspath(slug, 'research/intel.md')}`; look up the LATEST weather and road conditions with
web_fetch / web_search; write `{abspath(slug, 'brief.md')}` with exactly these headings:
{headings('brief', lang)}.
Never invent prices, opening hours, forecasts or phone numbers; write "{UNVERIFIED[lang]}" instead.

{language_rule(lang)}

{run_events_line(slug, 'briefing')}

When done, the LAST line of your reply must be exactly:
`BRIEF WRITTEN: {abspath(slug, 'brief.md')}`
"""


SESSION_TITLES = {
    "planner": "Travel Desk · Itinerary Planner",
    "risk": "Travel Desk · Risk Review",
    "briefing": "Travel Desk · Briefing",
}

DRAFT_TASK = {
    "id": "draft", "agent": "trip-itinerary-planner", "mode": "resident",
    "session_title": SESSION_TITLES["planner"], "session_folder": SESSION_FOLDER,
    "sentinel": "ITINERARY DRAFTED", "depends_on": [],
}
RISK_TASK = {
    "id": "risk", "agent": "trip-risk-pod", "mode": "resident",
    "session_title": SESSION_TITLES["risk"], "session_folder": SESSION_FOLDER,
    "sentinel": "RISK REVIEW WRITTEN", "depends_on": ["draft"],
}
REVISE_TASK = {
    "id": "revise", "agent": "trip-itinerary-planner", "mode": "resident",
    "session_title": SESSION_TITLES["planner"], "session_folder": SESSION_FOLDER,
    "sentinel": "ITINERARY REVISED", "depends_on": [],
}
BRIEF_TASK = {
    "id": "brief", "agent": "trip-briefing", "mode": "resident",
    "session_title": SESSION_TITLES["briefing"], "session_folder": SESSION_FOLDER,
    "sentinel": "BRIEF WRITTEN", "depends_on": ["risk"],
}


def cmd_plan(args: argparse.Namespace) -> int:
    slug = args.trip.strip()
    intent = args.intent
    try:
        read_request(slug)  # validates the trip exists
    except ValueError as exc:
        print(f"orchestrate.py: {exc}", file=sys.stderr)
        return 1

    def with_prompt(task: dict, prompt: str) -> dict:
        out = dict(task)
        out["prompt"] = prompt
        return out

    if intent == "draft":
        tasks = [with_prompt(DRAFT_TASK, draft_prompt(slug))]
    elif intent == "risk":
        tasks = [with_prompt(RISK_TASK, risk_prompt(slug))]
    elif intent == "revise":
        tasks = [with_prompt(REVISE_TASK, revise_prompt(slug))]
    elif intent == "brief":
        tasks = [with_prompt(BRIEF_TASK, brief_prompt(slug))]
    elif intent == "full":
        tasks = [
            with_prompt(DRAFT_TASK, draft_prompt(slug)),
            with_prompt(RISK_TASK, risk_prompt(slug)),
            with_prompt(BRIEF_TASK, brief_prompt(slug)),
        ]
    else:
        print(f"orchestrate.py: unknown intent {intent!r}", file=sys.stderr)
        return 1

    print(json.dumps({"trip": slug, "intent": intent, "language": request_lang(slug),
                      "tasks": tasks}, ensure_ascii=False, indent=2))
    return 0


# ---- leaf-plan --------------------------------------------------------------

def _leaf_common(slug: str, member: str, reads: list[str], writes: str,
                 heads: list[str], sentinel: str, extra: str = "") -> str:
    lang = request_lang(slug)
    reads_block = "\n".join(f"  - {abspath(slug, r)}" for r in reads) or "  - (none)"
    heads_txt = ", ".join(f"`{h}`" for h in heads)
    return f"""DESK_ROOT: {desk_root()}
Trip slug: {slug}
Read `{deskpaths.charter_path()}` first.

## The request (request.md, verbatim)
```
{read_request(slug)}
```

Files to read (absolute paths):
{reads_block}

File to write (absolute path): {abspath(slug, writes)}
Use exactly these section headings: {heads_txt}
{extra}Rules: coordinates must be real (`python3 {engine_dir()}/geocode.py <query>`; a place you cannot
resolve is left out); give a source URL for every fact; never invent prices or opening hours — write
"{UNVERIFIED[lang]}" when you could not check.

{language_rule(lang)}

{run_events_line(slug, member)}

When done, the LAST line of your reply must be `{sentinel}: {abspath(slug, writes)}`
"""


def leaf_tasks(slug: str, stage: str) -> list[dict]:
    lang = request_lang(slug)
    H = {k: v[lang] for k, v in HEADINGS.items()}
    C = {k: v[lang] for k, v in TABLE_COLUMNS.items()}
    if stage == "analysts":
        return [
            {"agent": "trip-destination-analyst", "task": _leaf_common(
                slug, "destination", [], "research/destination.md", H["destination"],
                "DESTINATION DONE",
                f"Candidate-sights table columns: {C['destination']}.\n")},
            {"agent": "trip-transport-analyst", "task": _leaf_common(
                slug, "transport", [], "research/transport.md", H["transport"],
                "TRANSPORT DONE",
                f"If there is no long-haul leg write \"{NO_LONG_HAUL[lang]}\"; "
                f"drive-time table columns: {C['drive']}.\n")},
            {"agent": "trip-lodging-food-analyst", "task": _leaf_common(
                slug, "lodging", [], "research/lodging-food.md", H["lodging"],
                "LODGING DONE",
                f"Group lodging candidates by night; table columns: {C['lodging']}.\n")},
            {"agent": "trip-intel-analyst", "task": _leaf_common(
                slug, "intel", [], "research/intel.md", H["intel"], "INTEL DONE")},
        ]
    if stage == "debate-1":
        reads = ["research/destination.md", "research/transport.md",
                 "research/lodging-food.md", "research/intel.md"]
        return [
            {"agent": "trip-advocate-packed", "task": _leaf_common(
                slug, "packed", reads, "debate/packed-1.md", H["debate"], "PACKED DONE",
                "Round 1: argue a packed, see-more day-by-day plan (stops + times per day).\n")},
            {"agent": "trip-advocate-slow", "task": _leaf_common(
                slug, "slow", reads, "debate/slow-1.md", H["debate"], "SLOW DONE",
                "Round 1: argue a slow, relaxed day-by-day plan (stops + times per day).\n")},
        ]
    if stage == "debate-2":
        return [
            {"agent": "trip-advocate-packed", "task": _leaf_common(
                slug, "packed", ["debate/slow-1.md", "debate/packed-1.md"],
                "debate/packed-2.md", H["debate"], "PACKED DONE",
                "Round 2: the rebuttal section must answer the slow advocate's round 1 point by point.\n")},
            {"agent": "trip-advocate-slow", "task": _leaf_common(
                slug, "slow", ["debate/packed-1.md", "debate/slow-1.md"],
                "debate/slow-2.md", H["debate"], "SLOW DONE",
                "Round 2: the rebuttal section must answer the packed advocate's round 1 point by point.\n")},
        ]
    if stage == "risk":
        reads = ["itinerary.json", "research/destination.md", "research/transport.md",
                 "research/lodging-food.md", "research/intel.md"]
        risk_head = ["VERDICT: PASS|CHANGE (first line)"] + H["risk"]
        card = ('Note cards are one JSON object per line: '
                '`{"date":"YYYY-MM-DD","text":"...","time":"HH:MM","icon":"⛽"}`.\n')
        return [
            {"agent": "trip-risk-budget", "task": _leaf_common(
                slug, "budget", reads, "risk/budget.md", risk_head, "BUDGET DONE", card)},
            {"agent": "trip-risk-safety", "task": _leaf_common(
                slug, "safety", reads, "risk/safety.md", risk_head, "SAFETY DONE", card)},
            {"agent": "trip-risk-stamina", "task": _leaf_common(
                slug, "stamina", reads, "risk/stamina.md", risk_head, "STAMINA DONE", card)},
        ]
    raise ValueError(f"unknown stage {stage!r}")


def cmd_leaf_plan(args: argparse.Namespace) -> int:
    slug = args.trip.strip()
    try:
        read_request(slug)
    except ValueError as exc:
        print(f"orchestrate.py: {exc}", file=sys.stderr)
        return 1
    try:
        tasks = leaf_tasks(slug, args.stage)
    except ValueError as exc:
        print(f"orchestrate.py: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"trip": slug, "stage": args.stage, "language": request_lang(slug),
                      "tasks": tasks}, ensure_ascii=False, indent=2))
    return 0


# ---- status -----------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> int:
    slug = args.trip.strip()
    root = trip_dir(slug)
    if not root.exists():
        print(f"orchestrate.py: trips/{slug}/ does not exist", file=sys.stderr)
        return 1
    artifacts = {rel: (root / rel).exists() for rel in ARTIFACTS}
    events = []
    ev_path = root / "runs" / "events.jsonl"
    if ev_path.exists():
        lines = ev_path.read_text(encoding="utf-8").splitlines()
        for line in lines[-10:]:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    print(json.dumps({"trip": slug, "artifacts": artifacts,
                      "recent_events": events}, ensure_ascii=False, indent=2))
    return 0


# ---- cli --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orchestrate.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami", help="print every resolved path as JSON").set_defaults(func=cmd_whoami)
    sub.add_parser("init", help="create the desk root skeleton").set_defaults(func=cmd_init)

    p_new = sub.add_parser("new", help="build trips/<slug>/ skeleton")
    p_new.add_argument("--slug", required=True)
    p_new.set_defaults(func=cmd_new)

    p_plan = sub.add_parser("plan", help="leader's resident-report tasks")
    p_plan.add_argument("--trip", required=True)
    p_plan.add_argument("--intent", required=True,
                        choices=["full", "draft", "risk", "revise", "brief"])
    p_plan.set_defaults(func=cmd_plan)

    p_leaf = sub.add_parser("leaf-plan", help="planner/risk-pod leaf tasks")
    p_leaf.add_argument("--trip", required=True)
    p_leaf.add_argument("--stage", required=True,
                        choices=["analysts", "debate-1", "debate-2", "risk"])
    p_leaf.set_defaults(func=cmd_leaf_plan)

    p_status = sub.add_parser("status", help="which products exist + recent events")
    p_status.add_argument("--trip", required=True)
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError) as exc:
        print(f"orchestrate.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
