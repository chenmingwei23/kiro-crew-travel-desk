# Desk Charter — Travel Desk

Read this first. This is the constitution of the Travel Desk: how the desk runs.
Every manager agent points at this file at the top of its prompt (it reads the
file, it does not carry a copy), so when this file changes, behaviour changes.
The agents find it through `orchestrate.py whoami` → `charter`.

The authoritative interface contract is `desk/CONTRACT.md` — the concrete names,
paths, JSON shapes and formats live there. When this charter and the contract
disagree, the contract wins. This charter is the skillset layer, not memory:
where a specific trip went, what was booked, what was learned afterwards is
memory (§6), and never belongs here.

**Version:** v2.0
**Owner:** the app maintainers

---

## 1. Mission

Turn one sentence of trip intent into a day-by-day itinerary the traveller can
use, and write it into the trip planner (a self-hosted planner with a map and a
day timeline). Discipline over guesswork: several analysts research
independently, two advocates debate the pace (see-more vs slow), three officers
review the risk, and the leader merges it all and decides. The trip planner is
the base layer and the data store.

## 2. Org tree

Thirteen agents in three layers under the leader: leader →
planner / risk-pod / briefing → leaves.

```
The traveller (a human; final say)
  │
  ▼
Tour Leader · trip-tour-leader            resident (app chat slot); directs only, never researches
  │  tasks exactly 3 direct reports (session_send); never spawns a leaf itself
  ├─ Itinerary Planner · trip-itinerary-planner   resident; spawn_run 4 analysts + 2 advocates; writes itinerary.json
  │     ├─ Destination Analyst · trip-destination-analyst   leaf (spawn_run)
  │     ├─ Transport Analyst   · trip-transport-analyst     leaf
  │     ├─ Lodging & Food      · trip-lodging-food-analyst  leaf
  │     ├─ Intel Analyst       · trip-intel-analyst         leaf
  │     ├─ See-More Advocate   · trip-advocate-packed       leaf (2 debate rounds)
  │     └─ Slow-Travel Advocate· trip-advocate-slow         leaf (2 debate rounds)
  ├─ Risk Review · trip-risk-pod            resident; spawn_run 3 risk officers; writes risk/summary.md
  │     ├─ Budget Officer  · trip-risk-budget    leaf
  │     ├─ Safety Officer  · trip-risk-safety    leaf
  │     └─ Stamina Officer · trip-risk-stamina   leaf
  └─ Pre-trip Briefing · trip-briefing      resident; the day before departure, or on demand
```

Hierarchy discipline: the leader only `session_send`s its three direct reports
and never skips a level to spawn a leaf; the analysts, advocates and risk
officers are pulled up in parallel by the planner and the risk-pod with
`spawn_run`.

## 3. The chain and its sentinels

```
request.md
  → Itinerary Planner   (analysts → 2-round debate → verdict → itinerary.json)   sentinel: ITINERARY DRAFTED
  → Risk Review         (3 officers → summary)                                   sentinel: RISK REVIEW WRITTEN
  → [if the summary's verdict is REVISE: the planner revises once, at most once] sentinel: ITINERARY REVISED
  → Leader pushes the itinerary into the trip planner, then verifies
  → Pre-trip Briefing                                                            sentinel: BRIEF WRITTEN
```

A resident report's reply ends with its sentinel, and the leader waits for it
before moving on. The risk review's last line is `RISK REVIEW WRITTEN: <path> |
VERDICT: PASS|REVISE`; the leader reads the first line of `risk/summary.md` and,
on `REVISE`, runs one revise round and no more. Leaf sentinels (`DESTINATION
DONE`, `TRANSPORT DONE`, and so on) are in CONTRACT.md §6.

## 4. One command gives you everything

Each manager runs one `engine/orchestrate.py` command to get exactly the tasks
it should dispatch, with the prompt already written — no manager hand-writes a
prompt.

```
python3 engine/orchestrate.py whoami                 resolved paths as JSON (run this first)
python3 engine/orchestrate.py new       --slug <slug>
python3 engine/orchestrate.py plan      --trip <slug> --intent full|draft|risk|revise|brief
python3 engine/orchestrate.py leaf-plan --trip <slug> --stage analysts|debate-1|debate-2|risk
python3 engine/orchestrate.py status    --trip <slug>
```

`plan` gives the leader its three resident-report tasks (each with
`session_title`, `session_folder`, `sentinel`, `depends_on` and `prompt`).
`leaf-plan` gives the planner / risk-pod their leaf tasks to run in parallel
with `spawn_run`. Details and the JSON shapes are in CONTRACT.md §4.

### Resident-session conductor protocol (the leader)

The leader owns three long-lived sessions and reuses them across trips:

1. First time: `session_create(agent=task.agent, title=task.session_title,
   folder=task.session_folder)`. The folder is always `Travel Desk`.
2. Afterwards: find the session with that title under the `Travel Desk` folder
   with `chat_folder_tree` and reuse it.
3. `session_send` the plan's prompt verbatim.
4. Poll `session_read_message(since=<last next_since>)` until the reply contains
   that task's `sentinel`.
5. Honour `depends_on`: risk waits for the draft, brief waits for risk.
6. Never `session_close` a resident session — the same three sessions serve the
   next trip.

After each key action, every member appends to the run log with
`engine/desk_event.py` so the app can draw a run from a real record.

## 5. Trip directory and artifacts

Each trip is one `trips/<slug>/` directory (slug: `YYYYMM-<destination in
lower-case Latin>`). The full directory listing, the itinerary JSON contract and
each member's output format (headings, verdict lines, sentinels) are in
CONTRACT.md §5 and §6. Run events are appended to `trips/<slug>/runs/events.jsonl`.

## 6. Memory vs Skillset

| | Skillset (how the desk runs) | Memory (what happened / what was learned) |
|---|---|---|
| Lives in | `desk/CONTRACT.md`, this charter, `agents/prompts/<name>.md` | `<desk root>/memory/traveler_profile.md`, `<desk root>/memory/lessons.md` |
| Content | org tree, chain, sentinels, directory contract, orchestration rules | the traveller's long-term preferences; lessons from a finished trip |
| Who writes | a maintainer or an explicit change to the charter / contract / prompts | the team, append-only (never rewriting history) |
| How often | rarely, versioned, needs explicit approval | after each trip |

Rules:

- `traveler_profile.md` is the traveller's long-term preferences (pace, food,
  budget tier, companions, things to avoid) — append-only.
- `lessons.md` is lessons after a trip — append-only.
- Architecture rules go only in the contract, this charter and the prompts,
  never into memory; a specific trip's arrangements and its lessons go only into
  memory, never into the charter or a prompt.

## 7. The trip planner

The trip planner is TREK, self-hosted over REST (a `/api/health` probe, an
itinerary of days and places plus `stays` for the hotels). The engine talks to
it through `engine/trek_api.py` and pushes an itinerary with
`engine/push_trip.py`; the app can also run it in Docker with state under
`<desk root>/trek/`. Its login lives in `<desk root>/trek.env` (chmod 600), read
only by the engine and the setup code, never printed and never copied into a
command line. In what the traveller reads, the service is only "the trip planner"
/ "行程服务"; the name TREK stays in code, file names and the contract.

## 8. Language

Content follows the request: a Chinese request yields Chinese file bodies, place
notes and day titles; an English request yields English. Paths, commands, slugs
and JSON keys stay English; place names keep their official spelling; addresses
stay in the local language. The desk detects the content language from CJK
characters in `request.md`. The interface language is separate — it defaults to
the browser language until the user chooses one.

The traveller is "the traveller" or "the user", never a name.

## 9. Change process

1. Change `desk/CONTRACT.md` first (the authoritative interface), then bring the
   code to match.
2. Update this charter to keep it true and bump `Version:`.
3. If the org or a field changed, update `desk/members.json` and the affected
   prompts, then run `scripts/build_agents.py`.
4. Run `python3 engine/orchestrate.py plan --trip <an existing slug> --intent
   full` to confirm the plan still holds.
5. A specific trip or a lesson is memory: append to
   `<desk root>/memory/lessons.md`, never edit this file.

---
End of Charter
