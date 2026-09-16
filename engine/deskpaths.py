#!/usr/bin/env python3
"""Where the Travel Desk keeps things — the one place that knows the layout.

Every engine script, the app backend and every agent prompt resolve paths
through this module (or its ``whoami`` output), so nothing anywhere carries a
machine-specific absolute path.

Layout (an installed app lives at ``<gateway home>/apps/travel-desk``)::

    <app root>/                    this repository, copied by the gateway on install
      engine/                      these scripts
      desk/                        charter, contract, roster, templates, example itinerary
      data/config.json             per-machine settings written by the app (never in git)

    <desk root>/                   user data; default <gateway home>/workspace/travel-desk
      trek.env                     ADMIN_EMAIL / ADMIN_PASSWORD / ENCRYPTION_KEY (chmod 600)
      .trek_token                  cached login token
      memory/traveler_profile.md   long-term traveller preferences (append-only)
      memory/lessons.md            lessons learned after trips (append-only)
      trips/<slug>/                one directory per trip (see desk/CONTRACT.md)
      trek/data, trek/uploads      the trip service's own state when the app runs it in Docker
      backups/                     archives written by the backup action

Resolution order for the desk root: ``TRAVEL_DESK_ROOT`` env, then
``deskRoot`` in ``data/config.json``, then the default above. The gateway home
is ``KIROCREW_HOME`` when set, else the grandparent of the app root when the
app is installed under ``<home>/apps/``, else ``~/.kiro/crew`` (or the legacy
``~/.kirocrew`` when only that exists).

Python 3.10+ standard library only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

APP_NAME = "travel-desk"
DEFAULT_TREK_URL = "http://127.0.0.1:3000"
DEFAULT_TREK_CONTAINER = "travel-desk-trek"
DEFAULT_TREK_IMAGE = "mauriceboe/trek"

#: Chat slot the leader lives in, per interface language (the UI mirrors this).
LEADER_SLOT = "travel-desk-leader"
LEADER_SLOT_EN = "travel-desk-leader-en"
LEADER_AGENT = "trip-tour-leader"

#: Sidebar folder the resident manager sessions are filed under.
SESSION_FOLDER = "Travel Desk"


def app_root() -> Path:
    """The directory holding ``app.json`` (parent of ``engine/``)."""
    return Path(__file__).resolve().parents[1]


def gateway_home() -> Path:
    """The KiroCrew data home this install belongs to (see module docstring)."""
    env = os.environ.get("KIROCREW_HOME")
    if env:
        return Path(env).expanduser()
    root = app_root()
    if root.parent.name == "apps":
        return root.parent.parent
    home = Path.home()
    modern = home / ".kiro" / "crew"
    legacy = home / ".kirocrew"
    if not modern.is_dir() and legacy.is_dir():
        return legacy
    return modern


def config_path() -> Path:
    return app_root() / "data" / "config.json"


def load_config() -> dict[str, Any]:
    """``data/config.json`` as a dict; missing or malformed reads as ``{}``."""
    try:
        raw = config_path().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def save_config(updates: dict[str, Any]) -> dict[str, Any]:
    """Merge ``updates`` into ``data/config.json`` (created if needed). Returns the result."""
    merged = {**load_config(), **{k: v for k, v in updates.items() if v is not None}}
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return merged


def desk_root() -> Path:
    env = os.environ.get("TRAVEL_DESK_ROOT") or os.environ.get("DESK_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    configured = load_config().get("deskRoot")
    if configured:
        return Path(str(configured)).expanduser().resolve()
    return (gateway_home() / "workspace" / APP_NAME).resolve()


def trips_dir() -> Path:
    return desk_root() / "trips"


def memory_dir() -> Path:
    return desk_root() / "memory"


def trek_url() -> str:
    env = os.environ.get("TREK_URL")
    if env:
        return env.rstrip("/")
    return str(load_config().get("trekUrl") or DEFAULT_TREK_URL).rstrip("/")


def trek_container() -> str:
    return str(load_config().get("trekContainer") or DEFAULT_TREK_CONTAINER)


def trek_image() -> str:
    return str(load_config().get("trekImage") or DEFAULT_TREK_IMAGE)


def trek_env_path() -> Path:
    env = os.environ.get("TREK_ENV")
    if env:
        return Path(env).expanduser()
    return desk_root() / "trek.env"


def trek_data_dir() -> Path:
    """Where the app-managed Docker container keeps the trip service's own state."""
    return desk_root() / "trek"


def token_path() -> Path:
    return desk_root() / ".trek_token"


def charter_path() -> Path:
    return app_root() / "desk" / "CHARTER.md"


def contract_path() -> Path:
    return app_root() / "desk" / "CONTRACT.md"


def profile_path() -> Path:
    return memory_dir() / "traveler_profile.md"


def lessons_path() -> Path:
    return memory_dir() / "lessons.md"


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a ``KEY=VALUE`` file. Callers never print the values."""
    env: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return env
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def trek_credentials() -> dict[str, str]:
    """The trip service login from ``trek.env`` (or ``TREK_ADMIN_EMAIL``/``TREK_ADMIN_PASSWORD`` env)."""
    creds = load_env_file(trek_env_path())
    email = os.environ.get("TREK_ADMIN_EMAIL") or creds.get("ADMIN_EMAIL", "")
    password = os.environ.get("TREK_ADMIN_PASSWORD") or creds.get("ADMIN_PASSWORD", "")
    return {"ADMIN_EMAIL": email, "ADMIN_PASSWORD": password}


def ensure_desk(root: Path | None = None) -> dict[str, Any]:
    """Create the desk root skeleton (idempotent). Returns what exists afterwards.

    ``memory/`` files are seeded from ``desk/templates`` only when absent — they
    are append-only user memory and are never overwritten.
    """
    root = (root or desk_root()).resolve()
    created: list[str] = []
    for sub in ("trips", "memory", "backups"):
        target = root / sub
        if not target.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            created.append(str(target))
    templates = app_root() / "desk" / "templates"
    for name in ("traveler_profile.md", "lessons.md"):
        target = root / "memory" / name
        source = templates / name
        if not target.exists() and source.is_file():
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            created.append(str(target))
    return {"desk_root": str(root), "created": created}


def describe() -> dict[str, Any]:
    """Every path an agent or operator needs, as plain data (``whoami``)."""
    root = desk_root()
    return {
        "app_root": str(app_root()),
        "engine": str(app_root() / "engine"),
        "desk_root": str(root),
        "trips_dir": str(root / "trips"),
        "charter": str(charter_path()),
        "contract": str(contract_path()),
        "traveler_profile": str(profile_path()),
        "lessons": str(lessons_path()),
        "trek_url": trek_url(),
        "trek_env": str(trek_env_path()),
        "trek_env_present": trek_env_path().is_file(),
        "gateway_home": str(gateway_home()),
        "python": sys.executable,
    }


if __name__ == "__main__":  # pragma: no cover - convenience
    print(json.dumps(describe(), ensure_ascii=False, indent=2))
