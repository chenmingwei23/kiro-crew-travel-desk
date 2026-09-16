"""Travel Desk backend — in-process routes for an EXTERNAL KiroCrew app.

``register_routes(ctx)`` returns ``list[AppRoute]`` with paths relative to
``/api/apps/travel-desk``; each handler takes ``(request, ctx)``. The manifest
declares this through ``backend.hooks.routes`` only — setting ``backend.routes``
would switch the gateway to the standalone-process proxy, whose stubs shadow
these handlers.

Routes (design/API.md):

    GET  /status               trip-service health, desk root, leader slot/agent, setup_needed
    GET  /setup                connection settings the UI may show (never the password)
    POST /setup                test (and unless test_only, save) a connection: url/email/password
    POST /service/{action}     create|start|stop|restart|upgrade|backup the app-managed Docker service
    GET  /trips                trips in the service (empty + error on failure, 200)
    GET  /trip?id=             one trip's view model
    GET  /photos?id=           resolve + cache photos for a trip's places
    GET  /photo/{place_id}     serve a cached photo (Content-Type by extension)
    GET  /org                  desk roster + live state + chat slot
    GET  /run?trip=            one trip: request head, artifact table, trek, events
    GET  /local-trips          trips/<slug> directories on disk

Every read is anchored at deskRoot from ``data/config.json``. Unauthenticated
callers get 401. The config READ endpoint the gateway owns
(``/api/apps/{name}/config``) is not re-declared here.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from aiohttp import web

from kiro_crew.apps.route_registry import AppRoute

from . import deskdata, paths, photos, setup, slots, trekdata  # paths puts the app root on sys.path
from engine import trek_api  # noqa: E402,I001 — needs the sys.path entry above
from .paths import (
    LEADER_AGENT,
    LEADER_SLOT,
    LEADER_SLOT_EN,
    SERVICE_ACTIONS,
    BadInput,
    desk_root,
    trek_url,
    valid_slug,
)
from .respond import err, guarded, log, ok

_SUBPROCESS_TIMEOUT = 300.0
_AUTH_PROBE_TTL = 60.0
_auth_cache: dict[str, tuple[float, bool | None, str]] = {}


# ---------------------------------------------------------------------------
# subprocess helper — argv only, never a shell string
# ---------------------------------------------------------------------------


async def _run(argv: list[str], timeout: float = _SUBPROCESS_TIMEOUT) -> tuple[int, str, str]:
    """Run ``argv`` with no shell. Returns ``(rc, stdout_tail, stderr_tail)``."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (FileNotFoundError, OSError) as exc:
        return 127, "", str(exc)
    try:
        out, errb = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return 124, "", f"timed out after {timeout:.0f}s"
    rc = proc.returncode if proc.returncode is not None else -1
    return rc, out.decode("utf-8", "replace")[-2000:], errb.decode("utf-8", "replace")[-2000:]


# ---------------------------------------------------------------------------
# trip-service client + status
# ---------------------------------------------------------------------------


def _trek_client(ctx: Any):
    """A logged-in client for the configured service. Raises on failure."""
    env = setup.read_env(ctx)
    api = trek_api.TrekAPI(
        trek_url(ctx),
        email=env.get("ADMIN_EMAIL") or None,
        password=env.get("ADMIN_PASSWORD") or None,
        token_file=desk_root(ctx) / ".trek_token",
    )
    api.ensure_login()
    return api


def _http_status_of(exc: Exception) -> int | None:
    status = getattr(exc, "status", None)
    if isinstance(status, int) and status:
        return status
    import re

    m = re.search(r"HTTP (\d{3})", str(exc))
    return int(m.group(1)) if m else None


async def _container_state(ctx: Any) -> dict[str, Any]:
    """``docker inspect`` the app-managed container. ``running`` is None without Docker."""
    name = paths.trek_container(ctx)
    rc, out, errb = await _run(["docker", "inspect", "-f", "{{.State.Running}}", name], timeout=10.0)
    if rc == 127:
        return {"name": name, "running": None, "docker": False}
    if rc != 0:
        return {"name": name, "running": False, "docker": True, "exists": False}
    return {"name": name, "running": out.strip() == "true", "docker": True, "exists": True}


async def _auth_probe(ctx: Any, reachable: bool, configured: bool) -> tuple[bool | None, str]:
    """Whether the saved login works, cached for a minute. None when it cannot be known."""
    if not reachable or not configured:
        return None, ""
    key = trek_url(ctx)
    now = time.monotonic()
    hit = _auth_cache.get(key)
    if hit and now - hit[0] < _AUTH_PROBE_TTL:
        return hit[1], hit[2]

    def _probe() -> tuple[bool, str]:
        try:
            _trek_client(ctx)
            return True, ""
        except Exception as exc:  # noqa: BLE001 — reported, never raised
            return False, str(exc)

    try:
        okay, message = await asyncio.wait_for(asyncio.to_thread(_probe), timeout=8.0)
    except asyncio.TimeoutError:
        okay, message = False, "login timed out"
    _auth_cache[key] = (now, okay, message)
    return okay, message


async def _trek_status(ctx: Any) -> dict[str, Any]:
    url = trek_url(ctx)
    reachable = await asyncio.to_thread(trek_api.health, url)
    env = setup.read_env(ctx)
    configured = bool(env.get("ADMIN_EMAIL") and env.get("ADMIN_PASSWORD"))
    authenticated, auth_error = await _auth_probe(ctx, reachable, configured)
    container = await _container_state(ctx)
    return {
        "url": url,
        "reachable": reachable,
        "configured": configured,
        "authenticated": authenticated,
        "auth_error": auth_error,
        # legacy keys the first UI read: running = answers HTTP, healthy = usable
        "running": reachable,
        "healthy": bool(reachable and (authenticated is True)),
        "managed": bool(paths.app_config(ctx).get("trekManaged")),
        "container": container,
    }


def _app_version() -> str:
    try:
        return str(json.loads((paths.app_root() / "app.json").read_text(encoding="utf-8")).get("version") or "")
    except (OSError, ValueError):
        return ""


@guarded
async def get_status(request: web.Request, ctx: Any) -> web.Response:
    trek = await _trek_status(ctx)
    setup_needed = not (trek["reachable"] and trek["configured"] and trek["authenticated"] is True)
    return ok(
        {
            "trek": trek,
            "setup_needed": setup_needed,
            "desk_root": str(desk_root(ctx)),
            "leader_slot": LEADER_SLOT,
            "leader_slot_en": LEADER_SLOT_EN,
            "leader_agent": LEADER_AGENT,
            "version": _app_version(),
        }
    )


# ---------------------------------------------------------------------------
# setup / connection
# ---------------------------------------------------------------------------


@guarded
async def get_setup(request: web.Request, ctx: Any) -> web.Response:
    state = setup.public_state(ctx)
    rc, _, _ = await _run(["docker", "--version"], timeout=5.0)
    state["docker_available"] = rc == 0
    state["reachable"] = await asyncio.to_thread(trek_api.health, state["trek_url"])
    return ok(state)


async def _json_body(request: web.Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 — malformed body is a 400, not a 500
        raise BadInput("body must be JSON")
    if not isinstance(body, dict):
        raise BadInput("body must be a JSON object")
    return body


@guarded
async def post_setup(request: web.Request, ctx: Any) -> web.Response:
    """Test a connection; save it unless ``test_only``. The password is never echoed."""
    body = await _json_body(request)
    try:
        url = setup.normalize_url(str(body.get("trek_url") or body.get("url") or ""))
        email = str(body.get("email") or "").strip()
        password = str(body.get("password") or "")
        if not password:  # re-test / change URL while keeping the stored password
            password = setup.read_env(ctx).get("ADMIN_PASSWORD", "")
        setup.validate_login(email, password)
    except setup.SetupError as exc:
        return err(str(exc), 400)
    result = await asyncio.to_thread(setup.test_login, url, email, password)
    if not result["authenticated"]:
        return web.json_response({"ok": False, **result}, status=502)
    if not body.get("test_only"):
        await asyncio.to_thread(setup.save_connection, ctx, url, email, password)
        _auth_cache.pop(url, None)
    return ok({"ok": True, "saved": not bool(body.get("test_only")), **result})


# ---------------------------------------------------------------------------
# app-managed trip service (Docker)
# ---------------------------------------------------------------------------


def _service_argv(action: str, ctx: Any) -> list[list[str]]:
    """The argv list(s) for a service action. Never a shell string."""
    name = paths.trek_container(ctx)
    if action == "start":
        return [["docker", "start", name]]
    if action == "stop":
        return [["docker", "stop", name]]
    if action == "restart":
        return [["docker", "restart", name]]
    if action == "upgrade":
        # pull -> remove -> run again (state kept via the two -v mounts).
        return [
            ["docker", "pull", paths.trek_image(ctx)],
            ["docker", "rm", "-f", name],
            setup.docker_run_argv(ctx, setup.port_of(trek_url(ctx))),
        ]
    if action == "backup":
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        root = desk_root(ctx)
        dest = str(root / "backups" / f"trek-{stamp}.tgz")
        return [
            ["mkdir", "-p", str(root / "backups")],
            ["tar", "czf", dest, "-C", str(paths.trek_data_dir(ctx)), "data", "uploads"],
        ]
    return []


async def _wait_healthy(url: str, seconds: float = 90.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if await asyncio.to_thread(trek_api.health, url):
            return True
        await asyncio.sleep(2.0)
    return False


@guarded
async def post_service(request: web.Request, ctx: Any) -> web.Response:
    action = str(request.match_info.get("action") or "")
    if action not in SERVICE_ACTIONS:
        return err(f"unknown action: {action}", 400)

    if action == "create":
        body = await _json_body(request)
        try:
            port = int(body.get("port") or 3000)
            email = str(body.get("email") or "").strip()
            password = str(body.get("password") or "")
            await asyncio.to_thread(setup.prepare_managed_service, ctx, email, password, port)
        except (setup.SetupError, ValueError) as exc:
            return err(str(exc), 400)
        steps = [["docker", "rm", "-f", paths.trek_container(ctx)], setup.docker_run_argv(ctx, port)]
        tails: list[str] = []
        for i, argv in enumerate(steps):
            rc, out, errb = await _run(argv)
            if i == 0 and rc != 0:
                continue  # nothing to remove yet: not an error, not worth reporting
            tails.append((out + ("\n" + errb if errb else "")).strip())
            if rc != 0:
                return web.json_response(
                    {"ok": False, "action": action, "error": f"command exited {rc}",
                     "output": "\n".join(tails)[-2000:]},
                    status=502,
                )
        url = f"http://127.0.0.1:{port}"
        healthy = await _wait_healthy(url)
        _auth_cache.pop(url, None)
        return ok({"ok": True, "action": action, "url": url, "reachable": healthy,
                   "output": "\n".join(tails)[-2000:]})

    if action == "backup" and not paths.trek_data_dir(ctx).is_dir():
        return err("backup is only available for the service this app runs itself", 400)

    tails = []
    for argv in _service_argv(action, ctx):
        rc, out, errb = await _run(argv)
        tail = (out + ("\n" + errb if errb else "")).strip()
        tails.append(tail)
        if rc != 0:
            return web.json_response(
                {"ok": False, "action": action, "error": f"command exited {rc}",
                 "output": "\n".join(tails)[-2000:]},
                status=502,
            )
    if action in ("start", "restart", "upgrade"):
        await _wait_healthy(trek_url(ctx), seconds=60.0)
    _auth_cache.pop(trek_url(ctx), None)
    return ok({"ok": True, "action": action, "output": "\n".join(tails)[-2000:]})


# ---------------------------------------------------------------------------
# trips
# ---------------------------------------------------------------------------


@guarded
async def get_trips(request: web.Request, ctx: Any) -> web.Response:
    """Trips in the service, each linking to it. Unreachable -> empty + error, 200."""
    base = trek_url(ctx)

    def _fetch() -> list[dict[str, Any]]:
        api = _trek_client(ctx)
        raw = api.list_trips()
        out: list[dict[str, Any]] = []
        for t in raw if isinstance(raw, list) else []:
            if not isinstance(t, dict):
                continue
            tid = t.get("id")
            out.append(
                {
                    "id": tid,
                    "title": t.get("title") or t.get("name") or "",
                    "start_date": t.get("start_date"),
                    "end_date": t.get("end_date"),
                    "day_count": t.get("day_count"),
                    "place_count": t.get("place_count"),
                    "url": f"{base}/trips/{tid}",
                }
            )
        return out

    try:
        trips = await asyncio.to_thread(_fetch)
    except Exception as exc:  # noqa: BLE001 — import or network failure -> graceful
        log.info("travel-desk /trips degraded: %s", exc)
        return ok({"trips": [], "error": str(exc)})
    return ok({"trips": trips, "error": ""})


# ---------------------------------------------------------------------------
# trip view model + photos
# ---------------------------------------------------------------------------


def _int_param(request: web.Request, name: str) -> int:
    raw = request.query.get(name)
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        raise BadInput(f"{name} must be an integer")


def _fetch_bundle(ctx: Any, trip_id: int) -> dict:
    api = _trek_client(ctx)
    wrapped = api.bundle(trip_id)
    bundle = wrapped.get("bundle") if isinstance(wrapped, dict) else None
    return bundle if isinstance(bundle, dict) else {}


def _bundle_error(exc: Exception, what: str) -> web.Response:
    status = _http_status_of(exc)
    if status == 404:
        return err(str(exc), 404)
    log.info("travel-desk %s unreachable: %s", what, exc)
    return err(str(exc), 502)


@guarded
async def get_trip(request: web.Request, ctx: Any) -> web.Response:
    """One trip's view model. Bad id -> 400, service 404 -> 404, unreachable -> 502."""
    trip_id = _int_param(request, "id")
    base = trek_url(ctx)
    data_dir = paths.data_dir(ctx)
    try:
        bundle = await asyncio.to_thread(_fetch_bundle, ctx, trip_id)
    except Exception as exc:  # noqa: BLE001 — turned into 404/502
        return _bundle_error(exc, "/trip")
    view = trekdata.build_trip_view(
        bundle,
        lambda pid: photos.photo_url_for(data_dir, pid),
        base,
        lambda pid: photos.is_confirmed_miss(data_dir, pid),
    )
    return ok(view)


def _trip_places(bundle: dict) -> list[dict]:
    raw = bundle.get("places") if isinstance(bundle, dict) else None
    return [p for p in raw if isinstance(p, dict)] if isinstance(raw, list) else []


@guarded
async def get_photos(request: web.Request, ctx: Any) -> web.Response:
    """Resolve + cache photos for every place of a trip. Bad id 400 / 404 / 502."""
    trip_id = _int_param(request, "id")
    data_dir = paths.data_dir(ctx)
    try:
        bundle = await asyncio.to_thread(_fetch_bundle, ctx, trip_id)
    except Exception as exc:  # noqa: BLE001
        return _bundle_error(exc, "/photos")
    places = _trip_places(bundle)
    result = await asyncio.to_thread(photos.resolve_photos, data_dir, places)
    return ok(result)


@guarded
async def get_photo(request: web.Request, ctx: Any) -> web.Response:
    """Serve a cached photo. Non-numeric id -> 400, no cache -> 404."""
    raw = str(request.match_info.get("place_id") or "")
    if not raw.isdigit():
        return err("place_id must be numeric", 400)
    place_id = int(raw)
    data_dir = paths.data_dir(ctx)
    path = await asyncio.to_thread(photos.cached_photo_path, data_dir, place_id)
    if path is None:
        return err("not found", 404)
    body = await asyncio.to_thread(path.read_bytes)
    return web.Response(
        body=body,
        content_type=photos.content_type_for(path),
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ---------------------------------------------------------------------------
# org / roster
# ---------------------------------------------------------------------------


def _build_org(members: list[dict[str, Any]], view: slots.SlotView,
               events: list[dict[str, Any]]) -> dict[str, Any]:
    states = deskdata.infer_states(events)
    out: list[dict[str, Any]] = []
    for member in members:
        mid = str(member.get("id") or "")
        state = states.get(mid, {"state": "idle", "state_msg": ""})
        entry = dict(member)
        entry["state"] = state["state"]
        entry["state_msg"] = state["state_msg"]
        entry["slot_key"] = slots.resolve_slot_key(view, member)
        out.append(entry)
    return {"members": out}


@guarded
async def get_org(request: web.Request, ctx: Any) -> web.Response:
    root = desk_root(ctx)
    members = await asyncio.to_thread(deskdata.load_members, paths.app_root())
    slug = request.query.get("trip") or await asyncio.to_thread(deskdata.default_slug, root)
    if slug is not None and not valid_slug(slug):
        raise BadInput("trip must be a valid slug")
    events = (
        await asyncio.to_thread(deskdata.read_events, root, slug) if slug else []
    )
    view = await slots.snapshot(request.app.get("state"))
    payload = await asyncio.to_thread(_build_org, members, view, events)
    return ok(payload)


# ---------------------------------------------------------------------------
# run / local-trips
# ---------------------------------------------------------------------------


@guarded
async def get_run(request: web.Request, ctx: Any) -> web.Response:
    root = desk_root(ctx)
    slug = request.query.get("trip") or await asyncio.to_thread(deskdata.default_slug, root)
    if not slug:
        return ok({"trip": None, "request": "", "artifacts": {}, "trek": None, "events": []})
    if not valid_slug(slug):
        raise BadInput("trip must be a valid slug")

    def _assemble() -> dict[str, Any]:
        trip = deskdata.trips_dir(root) / slug
        return {
            "trip": slug,
            "request": deskdata.read_request_head(root, slug),
            "artifacts": deskdata.artifact_table(root, slug),
            "trek": deskdata._read_json(trip / "trek.json"),
            "events": deskdata.read_events(root, slug, limit=200),
        }

    return ok(await asyncio.to_thread(_assemble))


@guarded
async def get_local_trips(request: web.Request, ctx: Any) -> web.Response:
    root = desk_root(ctx)
    return ok({"trips": await asyncio.to_thread(deskdata.list_local_trips, root)})


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------


def _ensure_install_state(ctx: Any) -> None:
    """Idempotent first-run work: default config + desk skeleton + memory templates."""
    try:
        cfg = paths.app_config(ctx)
        if "deskRoot" not in cfg:
            paths.save_config(ctx, {"deskRoot": str(desk_root(ctx)), "trekUrl": trek_url(ctx)})
        paths.deskpaths.ensure_desk(desk_root(ctx))
    except OSError as exc:
        log.warning("travel-desk: could not prepare the desk root: %s", exc)


def register_routes(ctx: Any) -> list[AppRoute]:
    """Declare this app's HTTP surface. Called once per enable / gateway start."""
    _ensure_install_state(ctx)
    routes = [
        AppRoute("GET", "/status", get_status),
        AppRoute("GET", "/setup", get_setup),
        AppRoute("POST", "/setup", post_setup),
        AppRoute("POST", "/service/{action}", post_service),
        AppRoute("GET", "/trips", get_trips),
        AppRoute("GET", "/trip", get_trip),
        AppRoute("GET", "/photos", get_photos),
        AppRoute("GET", "/photo/{place_id}", get_photo),
        AppRoute("GET", "/org", get_org),
        AppRoute("GET", "/run", get_run),
        AppRoute("GET", "/local-trips", get_local_trips),
    ]
    log.info("travel-desk backend: %d routes, deskRoot=%s", len(routes), desk_root(ctx))
    return routes
