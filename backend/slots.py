"""Resolve a member's ``slot_hint`` to a live chat slot (CONTRACT.md §7/§8.2).

``crews/members.json`` gives a LOCATOR, not a key — ``{"folder": "Travel Desk",
"title": "行程师 · itinerary-planner"}`` — because the slot key is assigned by
the gateway when the session is created. This module takes the one snapshot of
the gateway's sidebar that ``/org`` needs (live slots plus each folder's human
path) so the assembly stays a pure function over plain data.

Both reads are the gateway's public ones (``serialize_slots``, ``read_folders``),
and every one is guarded: with no gateway state — a test, or a state that has
moved on — the snapshot is simply empty and every resident member reads without
a slot key, instead of the page failing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SlotView:
    """What ``/org`` needs to know about the gateway's live sessions."""

    slots: list[dict[str, Any]] = field(default_factory=list)
    folder_paths: dict[str, str] = field(default_factory=dict)

    def by_folder_and_title(self, folder: str, title: str) -> dict[str, Any] | None:
        """The slot filed under ``folder`` with exactly this title."""
        for slot in self.slots:
            if slot.get("title") != title:
                continue
            if self.folder_paths.get(str(slot.get("folder_id") or "")) == folder:
                return slot
        return None

    def by_unique_title(self, title: str) -> dict[str, Any] | None:
        """The only slot with this title, if it is the only one."""
        matches = [s for s in self.slots if s.get("title") == title]
        return matches[0] if len(matches) == 1 else None

    def by_key(self, key: str) -> dict[str, Any] | None:
        return next((s for s in self.slots if s.get("key") == key), None)


def _folder_path_map(folders: list[dict[str, Any]]) -> dict[str, str]:
    """``{folder_id: "Parent/Child"}`` for every folder in the sidebar tree."""
    by_id = {str(f.get("id")): f for f in folders if isinstance(f, dict) and f.get("id")}

    def path_of(folder_id: str, seen: frozenset[str] = frozenset()) -> str:
        folder = by_id.get(folder_id)
        if folder is None or folder_id in seen:
            return ""
        name = str(folder.get("name") or "")
        parent = str(folder.get("parent_id") or "")
        if not parent:
            return name
        above = path_of(parent, seen | {folder_id})
        return f"{above}/{name}" if above else name

    return {fid: path_of(fid) for fid in by_id}


async def snapshot(gw_state: Any) -> SlotView:
    """One read of the gateway's live slots and folder tree."""
    if gw_state is None:
        return SlotView()

    slots: list[dict[str, Any]] = []
    serialize = getattr(gw_state, "serialize_slots", None)
    if callable(serialize):
        try:
            raw = serialize()
            slots = [s for s in raw if isinstance(s, dict)] if isinstance(raw, list) else []
        except Exception:  # noqa: BLE001 — a snapshot must never break the page
            slots = []

    folder_paths: dict[str, str] = {}
    read_folders = getattr(gw_state, "read_folders", None)
    if callable(read_folders):
        try:
            folder_paths = await read_folders(_folder_path_map)
        except Exception:  # noqa: BLE001
            folder_paths = {}

    return SlotView(slots=slots, folder_paths=folder_paths)


def resolve_slot_key(view: SlotView, member: dict[str, Any]) -> str | None:
    """The live slot key for a member, from its ``slot_hint`` (CONTRACT.md §7).

    - leader: the fixed ``slot_key`` in the hint.
    - resident: matched by folder+title, else by a unique title.
    - leaf: no hint -> None.
    """
    hint = member.get("slot_hint")
    if not isinstance(hint, dict):
        return None
    fixed = hint.get("slot_key")
    if fixed:
        return str(fixed)
    folder = hint.get("folder")
    title = hint.get("title")
    if not title:
        return None
    if folder:
        slot = view.by_folder_and_title(str(folder), str(title))
        if slot and slot.get("key"):
            return str(slot["key"])
    slot = view.by_unique_title(str(title))
    return str(slot["key"]) if slot and slot.get("key") else None
