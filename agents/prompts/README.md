# Writing the agent prompts

`agents/prompts/<agent>.md` is the source of truth for each agent's system
prompt. `python3 scripts/build_agents.py` inlines them into
`agents/<agent>.json`, which is what `app.json` ships and the gateway installs.
Edit the `.md`, run the build, commit both. `tests/test_agents.py` fails when
they drift apart.

## Shape (same for all 13)

```
# <Role name> · <agent-name>

## Locate the desk (first action, every session)
<the standard block below, verbatim>

## Desk charter
Read the charter file named by `whoami` before anything else ...

## Self-awareness card
Identity · position in the org tree (ascii tree) · who dispatches me ·
who I deliver to · what I do NOT do

## Duties / inputs / outputs
... with the fixed section headings and the sentinel line

## Rules
```

## The standard "Locate the desk" block

Nothing in a prompt may carry an absolute path: the app is installed under the
gateway's data home, which differs per machine. Every prompt starts by resolving
it, in this exact form:

    for H in "$KIROCREW_HOME" "$HOME/.kiro/crew" "$HOME/.kirocrew"; do
      [ -n "$H" ] && [ -f "$H/apps/travel-desk/engine/orchestrate.py" ] && break
    done
    TD="$H/apps/travel-desk"
    python3 "$TD/engine/orchestrate.py" whoami

`whoami` prints JSON with `desk_root`, `engine`, `charter`, `contract`,
`traveler_profile`, `lessons`, `trips_dir`. After that, refer to paths as
`$TD/engine/…`, `<desk_root>/trips/<slug>/…`, `<charter>`. Task prompts the
orchestrator generates already contain the resolved absolute paths.

## Vocabulary that must not change

- Agent names: `trip-tour-leader`, `trip-itinerary-planner`, `trip-risk-pod`,
  `trip-briefing`, `trip-destination-analyst`, `trip-transport-analyst`,
  `trip-lodging-food-analyst`, `trip-intel-analyst`, `trip-advocate-packed`,
  `trip-advocate-slow`, `trip-risk-budget`, `trip-risk-safety`, `trip-risk-stamina`.
- Member ids for `desk_event.py --who`: `leader planner risk briefing destination
  transport lodging intel packed slow budget safety stamina`.
- Sentinels (last line of a reply): `ITINERARY DRAFTED: <path>`, `ITINERARY
  REVISED: <path>`, `RISK REVIEW WRITTEN: <path> | VERDICT: PASS|REVISE`,
  `BRIEF WRITTEN: <path>`, `DESTINATION DONE`, `TRANSPORT DONE`, `LODGING DONE`,
  `INTEL DONE`, `PACKED DONE`, `SLOW DONE`, `BUDGET DONE`, `SAFETY DONE`,
  `STAMINA DONE` (each `: <path>`).
- Artifact paths under `trips/<slug>/`: `request.md`, `research/destination.md`,
  `research/transport.md`, `research/lodging-food.md`, `research/intel.md`,
  `debate/packed-1.md`, `debate/slow-1.md`, `debate/packed-2.md`,
  `debate/slow-2.md`, `debate/verdict.md`, `itinerary.json`, `risk/budget.md`,
  `risk/safety.md`, `risk/stamina.md`, `risk/summary.md`, `brief.md`, `trek.json`,
  `runs/events.jsonl`.
- Resident session titles: `Travel Desk · Itinerary Planner`, `Travel Desk ·
  Risk Review`, `Travel Desk · Briefing`; sidebar folder `Travel Desk`.
- Orchestrator commands: `whoami`, `init`, `new --slug`, `plan --trip --intent
  full|draft|risk|revise|brief`, `leaf-plan --trip --stage
  analysts|debate-1|debate-2|risk`, `status --trip`.

## Rules for the text

- English. The rule "content follows the language of the request" is stated in
  every prompt: a Chinese request yields Chinese notes and titles, an English
  request English ones; paths, commands, JSON keys stay English; addresses stay
  in the local language; place names keep their official spelling.
- The person is "the traveller" or "the user", never a name.
- No product name in what the traveller reads: say "the trip planner" for the
  backing service. (Commands and file names may say `trek`.)
- No `{UPPER_CASE}` tokens anywhere in a prompt (the gateway treats them as
  unresolved template placeholders and refuses to register the agent). Write
  `<slug>`, `<path>`, `HH:MM` instead.
- No absolute paths, no `/home/...`, no machine names.
- Keep the section headings the orchestrator's task text gives; do not restate
  them in a second language.
