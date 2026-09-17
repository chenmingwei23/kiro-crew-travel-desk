"""Desk-root resolution, config, and constants for the Travel Desk backend.

Every filesystem read this backend performs is anchored at ``deskRoot``. The
layout itself is defined ONCE in ``engine/deskpaths.py`` (shared with the
engine scripts the agents run); this module only adds the ``ctx``-scoped
config read the gateway hands us and the path-safety helpers the routes need.

Resolution: ``TRAVEL_DESK_ROOT`` env, then ``deskRoot`` in the app's
``data/config.json`` (``ctx.data_dir``), then ``<gateway home>/workspace/travel-desk``.
Anything resolving outside that tree is refused — both sides are ``resolve()``d
before comparison, so a symlink inside the tree that points out of it is caught too.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_APP_ROOT = Path(__file__).resolve().parent.parent


def engine_module(name: str) -> ModuleType:
    """``engine/<name>.py`` of THIS checkout.

    Inside the gateway this package is loaded under a per-app namespace
    (``<app root>.backend``), and the namespace root's search path is the app
    directory, so ``..engine`` resolves to our own ``engine/`` under the same
    namespace -- unloaded with the app on uninstall/disable, re-imported fresh on
    the next enable. A plain ``import engine`` would instead land in
    ``sys.modules["engine"]``, survive a reinstall, and serve the PREVIOUS
    version's code to the new backend. Tests and tooling import ``backend`` as a
    top-level package, where a relative parent does not exist: they fall back to
    the app root on ``sys.path``."""
    try:
        return importlib.import_module(f"..engine.{name}", __package__)
    except ImportError:
        if str(_APP_ROOT) not in sys.path:
            sys.path.insert(0, str(_APP_ROOT))
        return importlib.import_module(f"engine.{name}")


deskpaths = engine_module("deskpaths")

APP_NAME = deskpaths.APP_NAME
DEFAULT_TREK_URL = deskpaths.DEFAULT_TREK_URL
LEADER_SLOT = deskpaths.LEADER_SLOT
LEADER_SLOT_EN = deskpaths.LEADER_SLOT_EN
LEADER_AGENT = deskpaths.LEADER_AGENT

#: A slug is a path segment (``trips/{slug}``), validated as data first.
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

#: Trip-service container action allowlist. Unknown action -> 400.
SERVICE_ACTIONS = ("create", "start", "stop", "restart", "upgrade", "backup")


class OutOfRoot(Exception):
    """A requested path resolves outside deskRoot. Handlers turn this into 403."""


class BadInput(Exception):
    """A query parameter is malformed. Handlers turn this into 400."""


def app_root() -> Path:
    """This app's own root — the parent of ``backend/``.

    Works both in the source repo and in the installed copy under
    ``<gateway home>/apps/travel-desk``.
    """
    return _APP_ROOT


def data_dir(ctx: Any) -> Path:
    raw = getattr(ctx, "data_dir", None)
    return Path(raw).resolve() if raw else (app_root() / "data")


def app_config(ctx: Any) -> dict[str, Any]:
    """Read ``data/config.json``. A missing or corrupt file is an empty config."""
    try:
        raw = (data_dir(ctx) / "config.json").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def save_config(ctx: Any, updates: dict[str, Any]) -> dict[str, Any]:
    """Merge ``updates`` into ``data/config.json`` (created if needed). Returns the result."""
    merged = {**app_config(ctx), **{k: v for k, v in updates.items() if v is not None}}
    target = data_dir(ctx) / "config.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
    return merged


def desk_root(ctx: Any) -> Path:
    """Absolute, resolved deskRoot. Resolution does not require the path to exist."""
    env = os.environ.get("TRAVEL_DESK_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    configured = app_config(ctx).get("deskRoot")
    if configured:
        return Path(str(configured)).expanduser().resolve()
    return (deskpaths.gateway_home() / "workspace" / APP_NAME).resolve()


def trek_url(ctx: Any) -> str:
    return str(os.environ.get("TREK_URL") or app_config(ctx).get("trekUrl") or DEFAULT_TREK_URL).rstrip("/")


def trek_container(ctx: Any) -> str:
    return str(app_config(ctx).get("trekContainer") or deskpaths.DEFAULT_TREK_CONTAINER)


def trek_image(ctx: Any) -> str:
    return str(app_config(ctx).get("trekImage") or deskpaths.DEFAULT_TREK_IMAGE)


def trek_env_path(ctx: Any) -> Path:
    env = os.environ.get("TREK_ENV")
    return Path(env).expanduser() if env else desk_root(ctx) / "trek.env"


def trek_data_dir(ctx: Any) -> Path:
    return desk_root(ctx) / "trek"


def valid_slug(value: str | None) -> bool:
    """True for a safe trip slug (no path separators, no traversal)."""
    return bool(value) and bool(_SLUG_RE.match(value or ""))


def within(root: Path, candidate: Path) -> bool:
    """True when ``candidate`` resolves inside ``root``."""
    try:
        return candidate.resolve().is_relative_to(root.resolve())
    except (OSError, ValueError):
        return False


def slug_dir(root: Path, slug: str) -> Path:
    """``trips/<slug>`` under deskRoot, refusing a slug that escapes the tree."""
    if not valid_slug(slug):
        raise BadInput("slug is malformed")
    candidate = (root / "trips" / slug)
    if not within(root, candidate):
        raise OutOfRoot("trip is outside the desk root")
    return candidate
