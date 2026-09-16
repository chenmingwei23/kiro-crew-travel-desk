#!/usr/bin/env python3
"""Offline harness for the 旅行规划 UI.

Serves ``ui/`` behind an import map (React from esm.sh) with a stubbed
``@kirocrew/app-sdk`` (a fake ChatEmbed), and answers the app's API. Reads
(``/trips``, ``/trip``, ``/photos``, ``/org``) use the real backend modules
against a trip planner at ``TREK_URL``; the connection routes (``/status``,
``/setup``, ``/service/*``) are honest stubs so the setup flow can be driven
with no live service. Nothing here touches the gateway.

Environment:
    TREK_URL       trip planner address (default http://127.0.0.1:3000)
    TD_DESK_ROOT   desk root for roster/events reads (default: a temp dir; never
                   real user data unless you set it)

    python3 dev/harness.py [--port 8765] [--empty] [--setup] [--data DIR]

``--empty`` shows the empty state; ``--setup`` forces first-run setup. Then open
http://127.0.0.1:8765/ (or run dev/shoot.py for screenshots).
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TREK_URL = os.environ.get("TREK_URL", "http://127.0.0.1:3000").rstrip("/")
# Never point at real user data by default: a throwaway temp dir unless TD_DESK_ROOT is set.
DESK_ROOT = Path(os.environ.get("TD_DESK_ROOT") or (Path(tempfile.gettempdir()) / "td-harness-desk")).expanduser()
DESK_ROOT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(DESK_ROOT))

from backend import deskdata, photos, trekdata  # noqa: E402
from engine import trek_api  # noqa: E402

API_PREFIX = "/api/apps/travel-desk"
UI_PREFIX = "/apps/travel-desk/ui/"


def _port_of(url: str) -> int:
    m = re.search(r":(\d+)(/|$)", url)
    return int(m.group(1)) if m else (443 if url.startswith("https://") else 80)

INDEX_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>旅行规划 · harness</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script type="importmap">
{"imports": {
  "react": "https://esm.sh/react@18.3.1",
  "react/jsx-runtime": "https://esm.sh/react@18.3.1/jsx-runtime?external=react",
  "react-dom/client": "https://esm.sh/react-dom@18.3.1/client?external=react"
}}
</script>
<style>
  /* Mimic the DASHBOARD host, not a blank page: its dark theme tokens and its
     body font (the dashboard runs CLI mode = monospace body). The real
     ChatEmbed is styled with Tailwind utilities that resolve these variables,
     so a stub that reads the same variables reproduces the theme leak the app
     must neutralise (theme.mjs ".td-embed"). Values are the dashboard's plain
     dark theme + a rose accent, close to the screenshot the bug was filed from. */
  :root {
    --font-body: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
    --mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
    --bg: #12141a; --bg-accent: #14161d; --bg-elevated: #1a1d25; --bg-hover: #262a35;
    --card: #1a1d25; --card-fg: #e4e4e7; --text: #d4d4d8; --text-strong: #fafafa; --muted: #8b8b94;
    --border: #2a2e3a; --border-strong: #3f4452; --accent: #e0447c; --accent-fg: #fff; --accent-subtle: rgba(224,68,124,.16);
    --ok: #22c55e; --warn: #f59e0b; --radius-md: 8px; --radius-lg: 12px;
  }
  html, body { margin: 0; height: 100%; background: var(--bg); }
  body { font: 400 0.875rem/1.55 var(--font-body); color: var(--text); }
  /* the dashboard's own global rules that reach into a transcript */
  .msg-content code { font-family: var(--mono); font-size: .9em; }
  .msg-content :not(pre) > code { background: rgba(0,0,0,.15); padding: .15em .4em; border-radius: 4px; }
  .msg-content pre { background: rgba(0,0,0,.15); border-radius: 6px; padding: 10px 12px; font-family: var(--mono); font-size: .8125rem; }
  .font-mono { font-family: var(--mono); }
  .user-bubble { background: var(--card); color: var(--card-fg); }
  /* mimic the dashboard: an icon rail on the left, the app panel fills the rest */
  #shell { display: flex; height: 100vh; }
  #rail { width: 48px; background: #101116; border-right: 1px solid #23242c; flex-shrink: 0; }
  #app { flex: 1; min-width: 0; height: 100vh; }
</style>
</head><body>
<div id="shell"><div id="rail"></div><div id="app"></div></div>
<script type="module">
import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
const h = React.createElement

// A stand-in for the host's ChatEmbed. Same DOM grammar as app-sdk/ChatEmbed.tsx:
// a flex column, rows whose colours come from the theme VARIABLES (var(--text),
// var(--bg-elevated), var(--accent) ...), a `.user-bubble.msg-content` user row,
// a `.font-mono` tool pill, `.msg-content` assistant prose with inline code, and
// a composer of <input type="text"> + <button>. Inline styles stand in for the
// Tailwind utilities; the variables they read are the point.
function ChatEmbed({ placeholder }) {
  const [draft, setDraft] = useState('')
  // The transcript follows the app's own language preference, so an English
  // capture never shows a Chinese conversation (the real leader answers in the
  // language of the request; this stub reproduces that).
  let en = false
  try { en = window.localStorage.getItem('travel-desk.lang') === 'en' } catch (err) { /* private mode */ }
  const rowsEn = [
    ['me', 'Oct 17–19, Great Ocean Road from Melbourne, 3 days by car, 2 people'],
    ['tools', '30 tool calls'],
    ['leader', 'Kickoff done. Your traveller profile has no pace, budget or diet on file yet, so I am assuming mid-range and writing every assumption down. Building the skeleton now.'],
    ['leader', ['Research in, debate settled, risk review passed: budget, safety and stamina all clear. Pushed to ', h('code', { key: 'c' }, 'trip #6'), ' — 14 stops across 3 days plus 2 nights booked, recorded in ', h('code', { key: 'c2' }, 'trek.json'), '.']],
    ['leader', 'Two calls for you: the Cape Otway lighthouse on Day 2 is an optional 1.5 h detour, skip it if you are tight on time; the new Twelve Apostles visitor centre may need booking from late 2026 — I will confirm before you leave.'],
  ]
  const rows = location.port === '8766' ? [
    ['leader', '你好，我是团长。说一句去哪、几号到几号、几个人、自驾还是公交，团队就开始排。'],
  ] : en ? rowsEn : [
    ['me', '帮我规划 10 月 17 到 19 日墨尔本大洋路 3 天自驾，2 个人，墨尔本市区取车，不用再问我，缺的你假设并写明。'],
    ['tools', '30 tool calls'],
    ['leader', '开场仪式完成。旅行者档案里节奏/预算/饮食都还是空的，我会按常识假设并写明。现在建骨架。'],
    ['leader', ['推送成功：', h('code', { key: 'c' }, 'trip #5'), '，14 个 place（5+5+4）+ 2 段住宿，', h('code', { key: 'c2' }, 'trek.json'), ' 已记录。']],
    ['leader', '两处要你拍板：Day2 的 Cape Otway 灯塔是可选支线（往返约 1.5h），赶时间可跳；十二门徒新游客中心 2026 年底或需预约，出行前我再帮你确认。'],
  ]
  const chips = en
    ? ['Add the safety notes to the itinerary timeline', 'Swap Night 2 for a cheaper option']
    : ['把风控安全便签也加到 TREK 时间线', '帮我把 Night 2 换成预算内的备选住宿']
  return h('div', { style: { display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, overflow: 'hidden' } },
    h('div', { style: { flex: 1, minHeight: 0, overflow: 'auto', padding: '16px 0', display: 'flex', flexDirection: 'column', gap: 4 } },
      ...rows.map(([who, body], i) => {
        if (who === 'tools') return h('div', { key: i, style: { padding: '4px 16px' } },
          h('span', { className: 'font-mono', style: { display: 'inline-flex', gap: 8, fontSize: 13, lineHeight: '20px', padding: '2px 8px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', color: 'var(--muted)', background: 'var(--bg-elevated)' } }, '\u203a ' + body))
        if (who === 'me') return h('div', { key: i, style: { padding: '4px 16px', display: 'flex', justifyContent: 'flex-end' } },
          h('div', { className: 'user-bubble msg-content', style: { padding: '8px 16px', fontSize: 14, lineHeight: '24px', borderRadius: 12, maxWidth: 'min(550px, 100%)' } }, body))
        return h('div', { key: i, style: { padding: '4px 16px' } },
          h('div', { className: 'msg-content', style: { fontSize: 14, lineHeight: '24px', color: 'var(--text)', borderLeft: '2px solid color-mix(in srgb, var(--accent) 70%, transparent)', paddingLeft: 12, margin: '4px 0 8px' } }, ...[].concat(body)))
      })),
    h('div', { style: { padding: '4px 12px 0', display: 'flex', gap: 6, overflowX: 'auto' } },
      ...chips.map((c) => h('button', { key: c, style: { padding: '6px 12px', fontSize: 13, borderRadius: 'var(--radius-lg)', border: '1px solid var(--border)', color: 'var(--muted)', background: 'var(--bg-elevated)', whiteSpace: 'nowrap', cursor: 'pointer' } }, c))),
    h('div', { style: { display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px' } },
      h('input', { type: 'text', value: draft, onChange: (e) => setDraft(e.target.value), placeholder,
        style: { flex: 1, minWidth: 0, padding: '8px 12px', fontSize: 14, background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', color: 'var(--text)', outline: 'none' } }),
      h('button', { style: { padding: 8, borderRadius: 'var(--radius-md)', border: 0, background: 'var(--accent)', color: 'var(--accent-fg)', cursor: 'pointer', display: 'inline-flex' } },
        h('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }, h('path', { d: 'm5 12 7-7 7 7' }), h('path', { d: 'M12 19V5' })))))
}
window.__kirocrew_modules = { '@kirocrew/app-sdk': { ChatEmbed } }

const mod = await import('/apps/travel-desk/ui/index.mjs')
createRoot(document.getElementById('app')).render(h(mod.default))
</script>
</body></html>
"""


class State:
    def __init__(self, data_dir: Path, empty: bool, setup: bool):
        self.data_dir = data_dir
        self.empty = empty
        self.setup = setup  # force first-run setup (setup_needed:true) until a connection is saved
        self._api = None
        self._lock = threading.Lock()
        # Chat slots the gateway would know. The Chinese leader conversation
        # exists (it has history); the English one is created by its first
        # message, exactly like the real POST /api/chat does.
        self.slots: set[str] = {"travel-desk-leader"}

    def api(self):
        with self._lock:
            if self._api is None:
                a = trek_api.TrekAPI()
                a.ensure_login()
                self._api = a
            return self._api

    def bundle(self, trip_id: int) -> dict:
        return self.api().bundle(trip_id).get("bundle") or {}


def _json(handler: BaseHTTPRequestHandler, payload, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # quieter
            if "/photo/" in str(args[0]) if args else False:
                return
            sys.stderr.write("harness: " + (fmt % args) + "\n")

        def do_GET(self):  # noqa: N802
            u = urlparse(self.path)
            path = u.path
            q = parse_qs(u.query)
            if path == "/":
                body = INDEX_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path.startswith(UI_PREFIX):
                rel = path[len(UI_PREFIX):]
                f = (ROOT / "ui" / rel).resolve()
                if not f.is_relative_to((ROOT / "ui").resolve()) or not f.is_file():
                    self.send_error(404)
                    return
                ct = "application/javascript" if f.suffix == ".mjs" else (mimetypes.guess_type(str(f))[0] or "application/octet-stream")
                data = f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            if path.startswith(API_PREFIX):
                self.handle_api(path[len(API_PREFIX):], q)
                return
            if path.startswith("/api/chat/slots/"):
                slot = path[len("/api/chat/slots/"):].split("/")[0]
                if slot in state.slots:
                    _json(self, {"messages": [], "running": False, "title": slot, "has_more": False})
                else:
                    _json(self, {"error": "not found"}, 404)
                return
            self.send_error(404)

        def do_POST(self):  # noqa: N802
            u = urlparse(self.path)
            if u.path == "/api/chat":
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if length else {}
                slot = str(body.get("slot") or "")
                if slot:
                    state.slots.add(slot)
                _json(self, {"ok": True, "slot": slot})
                return
            if u.path == API_PREFIX + "/setup":
                self.handle_post_setup()
                return
            if u.path.startswith(API_PREFIX + "/service/"):
                action = u.path[len(API_PREFIX + "/service/"):].split("/")[0]
                self.handle_post_service(action)
                return
            self.send_error(404)

        def _read_json_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return {}
            return data if isinstance(data, dict) else {}

        def handle_post_setup(self) -> None:
            """Honest stub of POST /setup: validate like the backend, then (offline)
            report the connection as reachable + authenticated so the flow completes."""
            body = self._read_json_body()
            email = str(body.get("email") or "").strip()
            password = str(body.get("password") or "")
            url = str(body.get("trek_url") or body.get("url") or "").strip()
            test_only = bool(body.get("test_only"))
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                _json(self, {"error": "a valid admin email is required"}, 400)
                return
            if password and len(password) < 8:
                _json(self, {"error": "the admin password must be at least 8 characters"}, 400)
                return
            result = {"reachable": True, "authenticated": True, "error": ""}
            if not test_only:
                state.setup = False  # connection saved -> leave setup on the next status poll
                _json(self, {"ok": True, "saved": True, **result})
            else:
                _json(self, {"ok": True, "saved": False, **result})

        def handle_post_service(self, action: str) -> None:
            if action == "create":
                body = self._read_json_body()
                email = str(body.get("email") or "").strip()
                password = str(body.get("password") or "")
                port = int(body.get("port") or 3000)
                if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                    _json(self, {"error": "a valid admin email is required"}, 400)
                    return
                if len(password) < 8:
                    _json(self, {"error": "the admin password must be at least 8 characters"}, 400)
                    return
                state.setup = False
                _json(self, {"ok": True, "action": action, "url": f"http://127.0.0.1:{port}", "reachable": True})
                return
            if action in ("start", "stop", "restart", "upgrade", "backup"):
                _json(self, {"ok": True, "action": action})
                return
            _json(self, {"error": f"unknown action: {action}"}, 400)

        def handle_api(self, route: str, q: dict) -> None:
            try:
                if route == "/status":
                    if state.setup:
                        trek = {"url": TREK_URL, "reachable": False, "configured": False,
                                "authenticated": None, "auth_error": "", "running": False,
                                "healthy": False, "managed": False,
                                "container": {"name": "travel-desk-trek", "running": None, "docker": False}}
                    else:
                        trek = {"url": TREK_URL, "reachable": True, "configured": True,
                                "authenticated": True, "auth_error": "", "running": True,
                                "healthy": True, "managed": True,
                                "container": {"name": "travel-desk-trek", "running": True, "docker": True}}
                    _json(self, {"trek": trek, "setup_needed": bool(state.setup),
                                 "desk_root": str(DESK_ROOT), "leader_slot": "travel-desk-leader",
                                 "leader_slot_en": "travel-desk-leader-en",
                                 "leader_agent": "trip-tour-leader", "version": "1.0.0"})
                elif route == "/setup":
                    _json(self, {"trek_url": TREK_URL,
                                 "email": "" if state.setup else "admin@example.com",
                                 "has_password": not state.setup, "managed": not state.setup,
                                 "container": "travel-desk-trek", "image": "mauriceboe/trek",
                                 "desk_root": str(DESK_ROOT), "data_dir": str(state.data_dir),
                                 "port": _port_of(TREK_URL), "docker_available": True,
                                 "reachable": not state.setup})
                elif route == "/trips":
                    if state.empty or state.setup:
                        _json(self, {"trips": [], "error": ""})
                        return
                    raw = state.api().list_trips()
                    out = []
                    for t in raw if isinstance(raw, list) else []:
                        out.append({"id": t.get("id"), "title": t.get("title") or "", "start_date": t.get("start_date"),
                                    "end_date": t.get("end_date"), "day_count": t.get("day_count"), "place_count": t.get("place_count"),
                                    "url": f"{TREK_URL}/trips/{t.get('id')}"})
                    _json(self, {"trips": out, "error": ""})
                elif route == "/trip":
                    tid = int(q.get("id", ["0"])[0])
                    view = trekdata.build_trip_view(
                        state.bundle(tid),
                        lambda pid: photos.photo_url_for(state.data_dir, pid),
                        TREK_URL,
                        lambda pid: photos.is_confirmed_miss(state.data_dir, pid),
                    )
                    _json(self, view)
                elif route == "/photos":
                    tid = int(q.get("id", ["0"])[0])
                    places = [p for p in (state.bundle(tid).get("places") or []) if isinstance(p, dict)]
                    _json(self, photos.resolve_photos(state.data_dir, places))
                elif route.startswith("/photo/"):
                    pid = route[len("/photo/"):]
                    if not pid.isdigit():
                        self.send_error(400)
                        return
                    f = photos.cached_photo_path(state.data_dir, int(pid))
                    if not f:
                        self.send_error(404)
                        return
                    data = f.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", photos.content_type_for(f))
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.end_headers()
                    self.wfile.write(data)
                elif route == "/org":
                    # Roster lives in the app's own desk/members.json (like the backend);
                    # live state comes from the desk root's events, absent by default.
                    members = deskdata.load_members(ROOT)
                    slug = deskdata.default_slug(DESK_ROOT)
                    events = deskdata.read_events(DESK_ROOT, slug) if slug else []
                    states = deskdata.infer_states(events)
                    out = []
                    for m in members:
                        st = states.get(str(m.get("id")), {"state": "idle", "state_msg": ""})
                        e = dict(m)
                        e["state"] = st["state"]
                        e["state_msg"] = st["state_msg"]
                        out.append(e)
                    _json(self, {"members": out})
                else:
                    self.send_error(404)
            except Exception as exc:  # noqa: BLE001 — harness: show the error in the UI
                _json(self, {"error": f"{type(exc).__name__}: {exc}"}, 502)

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--empty", action="store_true", help="pretend there are no trips (empty state)")
    ap.add_argument("--setup", action="store_true", help="force first-run setup (setup_needed:true)")
    ap.add_argument("--data", default=os.environ.get("TD_HARNESS_DATA") or str(Path(os.environ.get("KIROCREW_SCRATCH", "/tmp")) / "td-harness-data"))
    args = ap.parse_args()
    data_dir = Path(args.data)
    data_dir.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(State(data_dir, args.empty, args.setup)))
    print(f"harness on http://127.0.0.1:{args.port}/  desk_root={DESK_ROOT}  trek={TREK_URL}  "
          f"empty={args.empty}  setup={args.setup}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
