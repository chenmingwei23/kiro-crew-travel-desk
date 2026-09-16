"""Filesystem reads over the travel desk root (desk/CONTRACT.md §5/§7/§8.2).

Pure, synchronous helpers — the routes call them via ``asyncio.to_thread``. Every
optional input (``crews/members.json``, ``trips/<slug>/...``) may be absent while
a sibling track is still writing it, so each reader degrades to an empty result
rather than raising.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# §5: every artifact a trip directory can hold, in a stable order.
ARTIFACT_FILES = (
    "request.md",
    "research/destination.md",
    "research/transport.md",
    "research/lodging-food.md",
    "research/intel.md",
    "debate/packed-1.md",
    "debate/slow-1.md",
    "debate/packed-2.md",
    "debate/slow-2.md",
    "debate/verdict.md",
    "itinerary.json",
    "risk/budget.md",
    "risk/safety.md",
    "risk/stamina.md",
    "risk/summary.md",
    "brief.md",
    "trek.json",
)

# §4 member-id -> kinds that mean "actively working".
WORKING_KINDS = ("dispatched", "stage")
BLOCKED_KINDS = ("failed",)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def load_members(app_root: Path) -> list[dict[str, Any]]:
    """``desk/members.json`` (list of member dicts), or [] if absent/malformed.

    Accepts both a bare list and the ``{"members": [...]}`` envelope shape.
    """
    parsed = _read_json(app_root / "desk" / "members.json")
    if isinstance(parsed, list):
        return [m for m in parsed if isinstance(m, dict)]
    if isinstance(parsed, dict):
        members = parsed.get("members")
        if isinstance(members, list):
            return [m for m in members if isinstance(m, dict)]
    return []


def trips_dir(root: Path) -> Path:
    return root / "trips"


def list_local_trips(root: Path) -> list[dict[str, Any]]:
    """Every ``trips/<slug>/`` with its title, mtime and pushed record (§8.2)."""
    base = trips_dir(root)
    out: list[dict[str, Any]] = []
    if not base.is_dir():
        return out
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        req = child / "request.md"
        title = child.name
        try:
            first = req.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
            if first:
                title = first
        except (OSError, IndexError, UnicodeDecodeError):
            pass
        try:
            updated = req.stat().st_mtime if req.is_file() else child.stat().st_mtime
        except OSError:
            updated = 0.0
        out.append(
            {
                "slug": child.name,
                "title": title,
                "updated_at": updated,
                "trek": _read_json(child / "trek.json"),
            }
        )
    out.sort(key=lambda t: t["updated_at"], reverse=True)
    return out


def events_path(root: Path, slug: str) -> Path:
    return trips_dir(root) / slug / "runs" / "events.jsonl"


def read_events(root: Path, slug: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Parse ``trips/<slug>/runs/events.jsonl`` (one JSON object per line)."""
    path = events_path(root, slug)
    events: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return events
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    if limit is not None and len(events) > limit:
        return events[-limit:]
    return events


def default_slug(root: Path) -> str | None:
    """The trip whose ``runs/events.jsonl`` was modified most recently (§8.2)."""
    base = trips_dir(root)
    if not base.is_dir():
        return None
    best: tuple[float, str] | None = None
    for child in base.iterdir():
        if not child.is_dir():
            continue
        ev = child / "runs" / "events.jsonl"
        try:
            mtime = ev.stat().st_mtime
        except OSError:
            continue
        if best is None or mtime > best[0]:
            best = (mtime, child.name)
    return best[1] if best else None


#: A "working" state older than this without a newer event reads as idle: a leaf
#: that wrote its file but never logged its final event must not look busy forever.
STALE_WORKING_SECS = 30 * 60


def _event_age(ev: dict[str, Any], now: float) -> float | None:
    raw = ev.get("at")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        from datetime import datetime, timezone

        stamp = datetime.fromisoformat(raw)
        if stamp.tzinfo is None:
            stamp = stamp.astimezone()
        return now - stamp.astimezone(timezone.utc).timestamp()
    except ValueError:
        return None


def infer_states(events: list[dict[str, Any]], now: float | None = None) -> dict[str, dict[str, str]]:
    """Per member-id, ``{"state", "state_msg"}`` from its LAST event (§8.2).

    ``dispatched|stage`` -> working (unless older than ``STALE_WORKING_SECS``),
    ``failed`` -> blocked, anything else -> idle.
    """
    import time

    now = time.time() if now is None else now
    last: dict[str, dict[str, Any]] = {}
    for ev in events:
        who = ev.get("who")
        if isinstance(who, str) and who:
            last[who] = ev
    states: dict[str, dict[str, str]] = {}
    for who, ev in last.items():
        kind = str(ev.get("kind") or "")
        if kind in WORKING_KINDS:
            age = _event_age(ev, now)
            state = "idle" if age is not None and age > STALE_WORKING_SECS else "working"
        elif kind in BLOCKED_KINDS:
            state = "blocked"
        else:
            state = "idle"
        states[who] = {"state": state, "state_msg": str(ev.get("msg") or "")}
    return states


def read_request_head(root: Path, slug: str, limit: int = 800) -> str:
    try:
        text = (trips_dir(root) / slug / "request.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    return text[:limit]


def artifact_table(root: Path, slug: str) -> dict[str, bool]:
    """``{relative_path: exists}`` for every §5 artifact of a trip."""
    trip = trips_dir(root) / slug
    return {rel: (trip / rel).is_file() for rel in ARTIFACT_FILES}
