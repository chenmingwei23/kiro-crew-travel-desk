"""First-run setup for the Travel Desk: connect to, or run, the trip service.

Two ways a user gets a trip service (TREK, https://github.com/liketrek/TREK):

1. **Connect** to one they already run: URL + admin email + password. We test the
   login, then write the URL to ``data/config.json`` and the login to
   ``<desk root>/trek.env`` (mode 600).
2. **Run it for them** with Docker: we generate an at-rest encryption key, write
   ``trek.env`` (ENCRYPTION_KEY / ADMIN_EMAIL / ADMIN_PASSWORD), and start the
   official image bound to loopback with its state under ``<desk root>/trek/``.

Secrets are written to disk once and never returned by any route. Every
subprocess is an argv list — no shell strings — and ``trek.env`` is passed to
Docker by path (``--env-file``), never read into the command line.
"""
from __future__ import annotations

import os
import re
import secrets
from pathlib import Path
from typing import Any

from engine import trek_api

from . import paths

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://[^\s/]+(:\d+)?(/.*)?$")


class SetupError(ValueError):
    """User-facing setup problem (400)."""


def normalize_url(raw: str) -> str:
    url = (raw or "").strip().rstrip("/")
    if not url:
        raise SetupError("service address is required")
    if "://" not in url:
        url = "http://" + url
    if not _URL_RE.match(url):
        raise SetupError("service address must look like http://host:port")
    return url


def validate_login(email: str, password: str) -> None:
    if not email or not _EMAIL_RE.match(email.strip()):
        raise SetupError("a valid admin email is required")
    if not password or len(password) < 8:
        raise SetupError("the admin password must be at least 8 characters")


def read_env(ctx: Any) -> dict[str, str]:
    return paths.deskpaths.load_env_file(paths.trek_env_path(ctx))


def write_env(ctx: Any, updates: dict[str, str]) -> Path:
    """Merge ``updates`` into ``trek.env`` and chmod it 600. Values are never logged."""
    target = paths.trek_env_path(ctx)
    current = paths.deskpaths.load_env_file(target) if target.exists() else {}
    current.update({k: v for k, v in updates.items() if v})
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".env.tmp")
    body = "".join(f"{k}={v}\n" for k, v in current.items())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(body)
    os.replace(tmp, target)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target


def forget_token(ctx: Any) -> None:
    try:
        (paths.desk_root(ctx) / ".trek_token").unlink()
    except OSError:
        pass


def test_login(url: str, email: str, password: str) -> dict[str, Any]:
    """Probe health then log in with the given credentials (nothing is cached)."""
    reachable = trek_api.health(url)
    if not reachable:
        return {"reachable": False, "authenticated": False,
                "error": f"no trip service answered at {url}"}
    api = trek_api.TrekAPI(url, email=email, password=password)
    try:
        api.login(force=True)
    except trek_api.TrekError as exc:
        if exc.status in (400, 401, 403):
            return {"reachable": True, "authenticated": False,
                    "error": "the service refused that email/password"}
        return {"reachable": True, "authenticated": False, "error": str(exc)}
    except (OSError, KeyError, ValueError) as exc:
        return {"reachable": True, "authenticated": False, "error": str(exc)}
    return {"reachable": True, "authenticated": True, "error": ""}


def save_connection(ctx: Any, url: str, email: str, password: str | None) -> None:
    """Persist a tested connection: URL to config, login to trek.env; drop the old token."""
    paths.save_config(ctx, {"trekUrl": url})
    updates = {"ADMIN_EMAIL": email.strip()}
    if password:
        updates["ADMIN_PASSWORD"] = password
    write_env(ctx, updates)
    forget_token(ctx)


def port_of(url: str) -> int:
    m = re.search(r":(\d+)(/|$)", url)
    return int(m.group(1)) if m else (443 if url.startswith("https://") else 80)


def docker_run_argv(ctx: Any, port: int) -> list[str]:
    """The ``docker run`` for the app-managed service (state under the desk root)."""
    data = paths.trek_data_dir(ctx)
    return [
        "docker", "run", "-d", "--name", paths.trek_container(ctx),
        "--restart", "unless-stopped",
        "-p", f"127.0.0.1:{int(port)}:3000",
        "--env-file", str(paths.trek_env_path(ctx)),
        "-v", f"{data / 'data'}:/app/data",
        "-v", f"{data / 'uploads'}:/app/uploads",
        paths.trek_image(ctx),
    ]


def prepare_managed_service(ctx: Any, email: str, password: str, port: int) -> None:
    """Write everything ``docker run`` needs: env file with a fresh key, data dirs, config."""
    validate_login(email, password)
    if not (1024 <= int(port) <= 65535):
        raise SetupError("port must be between 1024 and 65535")
    current = read_env(ctx)
    updates = {"ADMIN_EMAIL": email.strip(), "ADMIN_PASSWORD": password}
    if not current.get("ENCRYPTION_KEY"):
        updates["ENCRYPTION_KEY"] = secrets.token_hex(32)
    write_env(ctx, updates)
    data = paths.trek_data_dir(ctx)
    (data / "data").mkdir(parents=True, exist_ok=True)
    (data / "uploads").mkdir(parents=True, exist_ok=True)
    paths.save_config(ctx, {"trekUrl": f"http://127.0.0.1:{int(port)}", "trekManaged": True})
    forget_token(ctx)


def public_state(ctx: Any) -> dict[str, Any]:
    """What the settings page may know — never the password or the key."""
    env = read_env(ctx)
    cfg = paths.app_config(ctx)
    return {
        "trek_url": paths.trek_url(ctx),
        "email": env.get("ADMIN_EMAIL", ""),
        "has_password": bool(env.get("ADMIN_PASSWORD")),
        "managed": bool(cfg.get("trekManaged")),
        "container": paths.trek_container(ctx),
        "image": paths.trek_image(ctx),
        "desk_root": str(paths.desk_root(ctx)),
        "data_dir": str(paths.trek_data_dir(ctx)),
        "port": port_of(paths.trek_url(ctx)),
    }
