#!/usr/bin/env python3
"""Small REST client for the trip service (TREK) used by the desk and the app.

URL and credentials come from :mod:`deskpaths` (``data/config.json`` +
``<desk root>/trek.env``); the login token is cached at ``<desk root>/.trek_token``
(chmod 600). Python 3.10+ standard library only.

CLI:
    python3 engine/trek_api.py health
    python3 engine/trek_api.py trips
    python3 engine/trek_api.py bundle <id>
    python3 engine/trek_api.py delete <id>

The app backend imports this module directly (see backend/routes.py).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deskpaths  # noqa: E402

USER_AGENT = "travel-desk/1.0 (KiroCrew app)"


def desk_root() -> Path:
    return deskpaths.desk_root()


def token_path() -> Path:
    return deskpaths.token_path()


class TrekError(RuntimeError):
    """An HTTP error from the trip service; ``status`` carries the code."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def health(base: str | None = None, timeout: float = 3.0) -> bool:
    """True when ``GET <base>/api/health`` answers 200."""
    url = (base or deskpaths.trek_url()).rstrip("/") + "/api/health"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


class TrekAPI:
    def __init__(self, base: str | None = None, token: str | None = None,
                 email: str | None = None, password: str | None = None,
                 token_file: Path | None = None):
        """``token_file`` is where a successful login is cached. Default: the desk's
        ``.trek_token`` when the login comes from the desk config; NO cache when an
        ad-hoc email/password is given (a setup test must not leave a token behind)."""
        self.base = (base or deskpaths.trek_url()).rstrip("/")
        self.token = token
        self._email = email
        self._password = password
        if token_file is None and email is None:
            token_file = token_path()
        self._token_file = token_file

    def call(self, method: str, path: str, body=None, timeout: float = 30.0):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", USER_AGENT)
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                out = json.loads(raw) if raw else None
                # The service wraps most payloads in a single-key envelope.
                if (isinstance(out, dict) and len(out) == 1
                        and isinstance(next(iter(out.values())), (dict, list))):
                    return next(iter(out.values()))
                return out
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise TrekError(e.code, f"{method} {path} -> HTTP {e.code}: {detail[:400]}")

    def _credentials(self) -> tuple[str, str]:
        if self._email and self._password:
            return self._email, self._password
        creds = deskpaths.trek_credentials()
        email, password = creds["ADMIN_EMAIL"], creds["ADMIN_PASSWORD"]
        if not email or not password:
            raise TrekError(
                0,
                "no login for the trip service: set it in the app's Settings page "
                f"(writes {deskpaths.trek_env_path()})",
            )
        return email, password

    def login(self, force: bool = False) -> str:
        """Return a token, using the on-disk cache unless ``force``."""
        cache = self._token_file
        if not force and cache is not None and cache.exists():
            tok = cache.read_text().strip()
            if tok:
                self.token = tok
                return tok
        email, password = self._credentials()
        out = self.call("POST", "/api/auth/login", {"email": email, "password": password})
        self.token = out["token"]
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(self.token)
            try:
                os.chmod(cache, 0o600)
            except OSError:
                pass
        return self.token

    def ensure_login(self):
        if not self.token:
            self.login()

    def _authed(self, method: str, path: str, body=None):
        """Call with the cached token; on 401 log in again once and retry."""
        self.ensure_login()
        try:
            return self.call(method, path, body)
        except TrekError as exc:
            if exc.status != 401:
                raise
            self.login(force=True)
            return self.call(method, path, body)

    def list_trips(self) -> list:
        out = self._authed("GET", "/api/trips")
        return out if isinstance(out, list) else []

    def get_trip(self, trip_id) -> dict:
        return self._authed("GET", f"/api/trips/{trip_id}")

    def delete_trip(self, trip_id):
        return self._authed("DELETE", f"/api/trips/{trip_id}")

    def bundle(self, trip_id) -> dict:
        """Full trip bundle; also reports place/day counts for verification."""
        b = self._authed("GET", f"/api/trips/{trip_id}/bundle")
        days = b.get("days", []) if isinstance(b, dict) else []
        places = b.get("places", []) if isinstance(b, dict) else []
        return {"bundle": b, "days": len(days), "places": len(places)}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    try:
        if cmd == "health":
            up = health()
            print(f"{deskpaths.trek_url()}: {'ok' if up else 'unreachable'}")
            return 0 if up else 2
        api = TrekAPI()
        if cmd == "trips":
            for tr in api.list_trips():
                print(f"#{tr.get('id')}  {tr.get('title')}  "
                      f"{tr.get('start_date')}..{tr.get('end_date')}")
        elif cmd == "bundle":
            if len(argv) < 2:
                raise ValueError("bundle needs a trip id")
            info = api.bundle(argv[1])
            print(f"trip {argv[1]}: {info['days']} days, {info['places']} places")
        elif cmd == "delete":
            if len(argv) < 2:
                raise ValueError("delete needs a trip id")
            api.delete_trip(argv[1])
            print(f"deleted trip {argv[1]}")
        else:
            raise ValueError(f"unknown command {cmd!r}")
    except (ValueError, RuntimeError, KeyError, OSError) as exc:
        print(f"trek_api.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
