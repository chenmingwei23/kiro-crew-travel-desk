"""First-run setup for the Travel Desk: connect to, or run, the trip service.

Three ways a user gets a trip service (TREK, https://github.com/liketrek/TREK):

1. **Already running in Docker on this machine**: nothing to type. The status
   probe finds the container publishing the configured port, reads the admin
   login the container was started with (``docker inspect`` -> ``Config.Env``),
   tests it, and saves it exactly as a typed login would be saved.
2. **Connect** to one they run elsewhere: URL + admin email + password, from the
   Settings page. We test the login, then write the URL to ``data/config.json``
   and the login to ``<desk root>/trek.env`` (mode 600).
3. **Run it for them** with Docker: one click. We generate an at-rest encryption
   key and (unless the user typed one) an admin login, write ``trek.env``
   (ENCRYPTION_KEY / ADMIN_EMAIL / ADMIN_PASSWORD), and start the official image
   bound to loopback with its state under ``<desk root>/trek/``.

A login ticket the service already issued (``<desk root>/.trek_token``) is used
as-is while it is valid, so an existing installation keeps working before any
login is on file.

Secrets are written to disk once and never returned by any route. Every
subprocess is an argv list — no shell strings — and ``trek.env`` is passed to
Docker by path (``--env-file``), never read into the command line.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from . import paths

trek_api = paths.engine_module("trek_api")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://[^\s/]+(:\d+)?(/.*)?$")

#: Hosts that mean "this machine" — the only place a Docker container can be adopted from.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})

#: The admin login "Run it for me" generates when the user leaves the fields blank.
GENERATED_EMAIL = "admin@travel-desk.local"


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


def is_local_url(url: str) -> bool:
    """True when the service address points at this machine (loopback only)."""
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return False
    return host in LOOPBACK_HOSTS


#: ``docker inspect -f`` template: name, image and the env list on one short line,
#: because the subprocess helper keeps only the tail of a command's output and a
#: full ``docker inspect`` JSON document is several times longer than that.
INSPECT_FORMAT = "{{.Name}}\t{{.Config.Image}}\t{{json .Config.Env}}"


def _login_from_env(env_items: list[Any], name: str, image: str) -> dict[str, str] | None:
    env: dict[str, str] = {}
    for item in env_items or []:
        if isinstance(item, str) and "=" in item:
            k, _, v = item.partition("=")
            env[k] = v
    email, password = env.get("ADMIN_EMAIL", "").strip(), env.get("ADMIN_PASSWORD", "")
    if not (email and password):
        return None
    return {"container": name.lstrip("/"), "image": image, "email": email, "password": password}


def login_from_inspect(raw: str) -> dict[str, str] | None:
    """The admin login a local container was started with, from ``docker inspect``
    output: either one ``INSPECT_FORMAT`` line per container, or the full JSON
    list. None unless a container carries both ADMIN_EMAIL and ADMIN_PASSWORD.
    The password is returned to the caller only so it can be tested and saved;
    it is never logged or sent to the browser."""
    text = (raw or "").strip()
    if not text:
        return None
    if text[0] in "[{":  # full `docker inspect` JSON
        try:
            records = json.loads(text)
        except ValueError:
            return None
        if isinstance(records, dict):
            records = [records]
        for rec in records if isinstance(records, list) else []:
            if not isinstance(rec, dict):
                continue
            config = rec.get("Config") if isinstance(rec.get("Config"), dict) else {}
            found = _login_from_env(config.get("Env") or [], str(rec.get("Name") or ""),
                                    str(config.get("Image") or ""))
            if found:
                return found
        return None
    for line in text.splitlines():  # INSPECT_FORMAT lines
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        try:
            env_items = json.loads(parts[2])
        except ValueError:
            continue
        found = _login_from_env(env_items if isinstance(env_items, list) else [], parts[0], parts[1])
        if found:
            return found
    return None


def generate_login() -> tuple[str, str]:
    """An admin login for a service this app starts itself: fixed local email, random password."""
    return GENERATED_EMAIL, secrets.token_urlsafe(18)


def ticket_path(ctx: Any) -> Path:
    return paths.desk_root(ctx) / ".trek_token"


def has_ticket(ctx: Any) -> bool:
    """Whether a login ticket the service once issued is on disk (validity is probed, not assumed)."""
    try:
        return ticket_path(ctx).stat().st_size > 0
    except OSError:
        return False


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


def prepare_managed_service(ctx: Any, email: str, password: str, port: int) -> str:
    """Write everything ``docker run`` needs: env file with a fresh key, data dirs, config.

    Blank email AND password mean "generate the login for me" (the app is the
    only thing that logs in, so the user never needs to know it). A partly typed
    login is validated like a typed one. Returns the admin email in use."""
    if not email.strip() and not password:
        email, password = generate_login()
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
    return email.strip()


def public_state(ctx: Any) -> dict[str, Any]:
    """What the settings page may know — never the password, the key, or the ticket."""
    env = read_env(ctx)
    cfg = paths.app_config(ctx)
    return {
        "trek_url": paths.trek_url(ctx),
        "email": env.get("ADMIN_EMAIL", ""),
        "has_password": bool(env.get("ADMIN_PASSWORD")),
        "has_ticket": has_ticket(ctx),
        "managed": bool(cfg.get("trekManaged")),
        "container": paths.trek_container(ctx),
        "image": paths.trek_image(ctx),
        "desk_root": str(paths.desk_root(ctx)),
        "env_path": str(paths.trek_env_path(ctx)),
        "data_dir": str(paths.trek_data_dir(ctx)),
        "port": port_of(paths.trek_url(ctx)),
    }
