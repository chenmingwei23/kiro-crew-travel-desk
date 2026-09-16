"""pytest fixtures for the Travel Desk app suite (CONTRACT.md §8.5).

The suite never touches the real desk data root. ``app_ctx`` points the app at a
tmp deskRoot via a hand-built config, and ``call`` invokes a route handler
directly with a fake authenticated request — no gateway needed. The real
``AppRoute``/``AppContext`` types are imported from the kiro_crew package (the
venv the task runs under), so ``register_routes`` returns real AppRoute objects.

Run: ``python3 -m pytest tests -q`` (with the kiro_crew package importable)
(never ``-n auto``; see desk/CONTRACT.md §8)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class FakeAppState:
    """Stand-in for the gateway state object ``request.app['state']`` holds.

    ``None`` slots / folders is the steady state in tests: slots.snapshot then
    returns an empty view and every resident member reads without a slot key.
    """

    def __init__(self, slots: list[dict] | None = None, folders: list[dict] | None = None) -> None:
        self._slots = slots or []
        self._folders = folders or []

    def serialize_slots(self) -> list[dict]:
        return self._slots

    async def read_folders(self, fn):
        return fn(self._folders)


class FakeApp(dict):
    """aiohttp ``request.app`` is a mapping; a dict is enough for the handlers."""


class FakeRequest:
    """Minimal ``web.Request`` surface the handlers touch."""

    def __init__(self, *, query: dict | None = None, match_info: dict | None = None,
                 user: Any = "tester", app: FakeApp | None = None) -> None:
        self.query = query or {}
        self.match_info = match_info or {}
        self._user = user
        self.app = app if app is not None else FakeApp(state=FakeAppState())

    def get(self, key: str, default: Any = None) -> Any:
        if key == "user":
            return self._user
        return default


class Ctx:
    """AppContext-shaped stub: only ``data_dir`` is read by the backend."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.name = "travel-desk"
        self.config: dict = {}


@pytest.fixture
def desk_root(tmp_path: Path) -> Path:
    root = tmp_path / "travel-desk"
    (root / "trips").mkdir(parents=True)
    (root / "backups").mkdir()
    return root


@pytest.fixture
def data_dir(tmp_path: Path, desk_root: Path) -> Path:
    d = tmp_path / "appdata"
    d.mkdir()
    (d / "config.json").write_text(
        json.dumps(
            {
                "deskRoot": str(desk_root),
                "trekUrl": "http://127.0.0.1:3000",
            }
        ),
        encoding="utf-8",
    )
    return d


@pytest.fixture
def app_ctx(data_dir: Path) -> Ctx:
    return Ctx(data_dir)


def _make_trip(desk_root: Path, slug: str, *, title: str = "去哪玩",
               events: list[dict] | None = None, artifacts: list[str] | None = None) -> Path:
    trip = desk_root / "trips" / slug
    trip.mkdir(parents=True, exist_ok=True)
    (trip / "request.md").write_text(f"# {title}\n\n目的地: ...\n", encoding="utf-8")
    for rel in artifacts or []:
        p = trip / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    if events is not None:
        runs = trip / "runs"
        runs.mkdir(exist_ok=True)
        with (runs / "events.jsonl").open("w", encoding="utf-8") as fh:
            for ev in events:
                fh.write(json.dumps(ev) + "\n")
    return trip


@pytest.fixture
def make_trip():
    return _make_trip
