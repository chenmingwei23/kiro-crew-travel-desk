---
name: travel-desk
description: Hand a trip request to the Travel Desk app — a 13-agent crew that researches, debates and risk-checks a day-by-day itinerary and stores it in a self-hosted trip planner. Use when the user wants to plan a trip, build an itinerary, or asks for a travel plan or 攻略.
triggers:
  - plan a trip
  - trip plan
  - itinerary
  - 规划行程
  - 行程
  - 攻略
---

# Travel Desk

The Travel Desk app owns trip planning. Do not plan the trip yourself: hand the
request to the app's Tour Leader and let the crew work.

## Hand off a request

Preferred: tell the user to open **Travel Desk** in the sidebar and say one
sentence to the Tour Leader (where, which dates, how many people, driving or
transit).

Programmatic: post the sentence into the leader's chat slot with
`POST /api/chat`. The content language follows the request — Chinese in, Chinese
out.

```
POST /api/chat
{ "message": "<the user's one sentence>",
  "slot": "travel-desk-leader",        // use "travel-desk-leader-en" for English
  "agent": "trip-tour-leader" }
```

Use `travel-desk-leader-en` when the request is in English, `travel-desk-leader`
otherwise. The trip and map appear on the Travel Desk page a few minutes later.

## Drive the engine by hand

The engine scripts live in the installed app. Locate the desk first, then read
the resolved paths from `whoami`:

```
for H in "$KIROCREW_HOME" "$HOME/.kiro/crew" "$HOME/.kirocrew"; do
  [ -n "$H" ] && [ -f "$H/apps/travel-desk/engine/orchestrate.py" ] && break
done
TD="$H/apps/travel-desk"
python3 "$TD/engine/orchestrate.py" whoami
```

`whoami` prints JSON with `desk_root`, `engine`, `charter`, `contract`,
`traveler_profile`, `lessons`, `trips_dir`.

Then, if you must drive it manually:

- `python3 "$TD/engine/orchestrate.py" init` — create the desk root skeleton.
- `python3 "$TD/engine/orchestrate.py" new --slug <slug>` — start a trip; fill
  in the generated `request.md`.
- `python3 "$TD/engine/orchestrate.py" plan --trip <slug> --intent full|draft|risk|revise|brief`
  — the leader's resident-report tasks.
- `python3 "$TD/engine/orchestrate.py" leaf-plan --trip <slug> --stage analysts|debate-1|debate-2|risk`
  — the parallel leaf tasks for the analysts, advocates and risk officers.
- `python3 "$TD/engine/orchestrate.py" status --trip <slug>` — which products
  exist plus recent events.
- `python3 "$TD/engine/push_trip.py"` — push a finished itinerary into the trip
  planner.
- `python3 "$TD/engine/trek_api.py"` — talk to the trip planner's REST API.

## Where data lives

User data is at the desk root, default `<gateway home>/workspace/travel-desk`:
`trips/<slug>/` per trip, `memory/` for long-term traveller notes, `backups/`,
`trek.env` (mode 600), and the trip planner's own state when the app runs it.
The app resolves all of this through `orchestrate.py whoami`; never hard-code a
path.
