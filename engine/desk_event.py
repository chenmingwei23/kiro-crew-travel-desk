#!/usr/bin/env python3
"""Append-only run-event log for the Travel Desk.

One JSON object per line, appended to `trips/<slug>/runs/events.jsonl`. The
resident manager sessions (leader / itinerary-planner / risk-pod / briefing) and
the leaf workers call this right after each key action, so the Travel Desk app
can draw a run from a real record instead of inferring one from file mtimes.

Event schema (authoritative: desk/CONTRACT.md §4):

    at     ISO-8601 local timestamp, second resolution
    trip   the trip slug this event belongs to
    who    member id (see MEMBERS below) or a free label
    kind   dispatched | stage | delivered | failed | note
    msg    one plain sentence, written for a reader
    stage  optional {"name": str, "done": int, "total": int}

Usage:

    python3 engine/desk_event.py append --trip 202610-demo --who planner \
        --kind stage --msg "4 research files are in" --stage-name research --done 4 --total 4

    python3 engine/desk_event.py append --trip 202610-demo --who leader \
        --kind delivered --msg "Pushed to the trip service" --dry-run

Leaf workers append in parallel. Each call takes an exclusive lock and writes
exactly one whole line in append mode, so lines never interleave and no existing
line is ever rewritten -- the log is append-only by construction.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

KINDS = ("dispatched", "stage", "delivered", "failed", "note")
MEMBERS = (
    "leader", "planner", "risk", "briefing",
    "destination", "transport", "lodging", "intel",
    "packed", "slow", "budget", "safety", "stamina",
)
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


try:
    from . import deskpaths  # imported as part of a package (the app backend)
except ImportError:  # run as a script from the engine directory
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import deskpaths  # noqa: E402


def desk_root() -> Path:
    """Desk data root (see deskpaths.py; TRAVEL_DESK_ROOT overrides it for tests)."""
    return deskpaths.desk_root()


def events_path(slug: str) -> Path:
    return desk_root() / "trips" / slug / "runs" / "events.jsonl"


def build_stage(name: str | None, done, total) -> dict | None:
    if name is None and done is None and total is None:
        return None
    if name is None or done is None or total is None:
        raise ValueError("--stage-name, --done and --total must be given together")
    done = int(done)
    total = int(total)
    if total <= 0:
        raise ValueError(f"--total must be greater than 0, got {total}")
    if done < 0 or done > total:
        raise ValueError(f"--done ({done}) must be between 0 and --total ({total})")
    name = name.strip()
    if not name:
        raise ValueError("--stage-name must not be empty")
    return {"name": name, "done": done, "total": total}


def build_event(
    trip: str,
    who: str,
    kind: str,
    msg: str,
    stage: dict | None = None,
    at: str | None = None,
) -> dict:
    """Validate the inputs and return one event object."""
    trip = trip.strip()
    if not SLUG_RE.match(trip):
        raise ValueError(f"--trip must be a slug like 202610-sydney, got {trip!r}")
    if kind not in KINDS:
        raise ValueError(f"--kind must be one of {'|'.join(KINDS)}, got {kind!r}")
    who = who.strip()
    msg = msg.strip()
    if not who:
        raise ValueError("--who must not be empty")
    if not msg:
        raise ValueError("--msg must not be empty")

    event = {
        "at": at or datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "trip": trip,
        "who": who,
        "kind": kind,
        "msg": msg,
    }
    if stage is not None:
        event["stage"] = stage
    return event


def append_event(event: dict) -> Path:
    """Append one event as a single line. Returns the file written."""
    line = json.dumps(event, ensure_ascii=False) + "\n"
    path = events_path(event["trip"])
    path.parent.mkdir(parents=True, exist_ok=True)

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    return path


def cmd_append(args: argparse.Namespace) -> int:
    stage = build_stage(args.stage_name, args.done, args.total)
    event = build_event(args.trip, args.who, args.kind, args.msg, stage=stage)
    line = json.dumps(event, ensure_ascii=False)
    if args.dry_run:
        print(line)
        return 0
    path = append_event(event)
    print(f"{path}: {line}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="desk_event.py",
        description="Append one run event to trips/<slug>/runs/events.jsonl.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    ap = sub.add_parser("append", help="append one event")
    ap.add_argument("--trip", required=True, help="trip slug")
    ap.add_argument("--who", required=True, help="member id or free label")
    ap.add_argument("--kind", required=True, choices=KINDS, help="event kind")
    ap.add_argument("--msg", required=True, help="one plain sentence for a reader")
    ap.add_argument("--stage-name", help="progress stage name, e.g. 分析")
    ap.add_argument("--done", help="progress: items done so far")
    ap.add_argument("--total", help="progress: total items in the stage")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print the event line without writing it",
    )
    ap.set_defaults(func=cmd_append)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError) as exc:
        print(f"desk_event.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
