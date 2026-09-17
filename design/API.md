# Travel Desk app — backend API

The UI reads everything from this backend; the backend reads the trip planner
(TREK) through `engine.trek_api.TrekAPI` and the desk root from disk. Nothing is
iframed — the UI renders the trip inline — so there is no proxy and no second
port.

All paths are relative to `/api/apps/travel-desk`. Unauthenticated callers get
401. Errors return `{"error": "<message>"}`. Every response is JSON except
`/photo/{place_id}`. Every filesystem read is anchored at `deskRoot`
(`data/config.json`, or the default `<gateway home>/workspace/travel-desk`); a
slug or path that escapes that tree is refused.

Routes: `GET /status`, `GET /setup`, `POST /setup`,
`POST /service/{action}`, `GET /trips`, `GET /trip`, `GET /photos`,
`GET /photo/{place_id}`, `GET /org`, `GET /run`, `GET /local-trips`.

The config read endpoint `/api/apps/{name}/config` is owned by the gateway and
is not declared here.

## GET /status

```json
{"trek": {"url": "http://127.0.0.1:3000", "reachable": true, "configured": true,
          "login_source": "detected", "adopted_container": "trek",
          "authenticated": true, "auth_error": "", "connected": true,
          "running": true, "healthy": true,
          "managed": false, "container": {"name": "travel-desk-trek", "running": true,
                                          "docker": true, "exists": true}},
 "setup_needed": false,
 "desk_root": "<desk root>",
 "leader_slot": "travel-desk-leader",
 "leader_slot_en": "travel-desk-leader-en",
 "leader_agent": "trip-tour-leader",
 "version": "1.1.0"}
```

`connected` = reachable and the app can act on the service. `configured` = a
login is on file in `trek.env`. `login_source` says how the app logs in:

- `env` — the login on file.
- `detected` — no login was on file, the address is loopback, and a Docker
  container on this machine publishing that port carried `ADMIN_EMAIL` /
  `ADMIN_PASSWORD` in its environment. The probe tested that login, saved it to
  `trek.env` exactly like a typed one, and reports the container in
  `adopted_container` on the request that adopted it (afterwards `env`). A
  refused or absent container is remembered for a minute before Docker is asked
  again; a remote address never triggers `docker` at all.
- `ticket` — no login, but a ticket the service issued earlier
  (`<desk root>/.trek_token`) still validates against `/api/auth/me`. The app
  works with it until it expires; then `auth_error` names the Settings page.
- `none` — nothing to try.

`setup_needed` is simply `not connected`. The UI does not gate on it: it shows
the connect page (one-click Docker run + a pointer to the Settings row) while
nothing connects, and the trip page as soon as something does. `running` /
`healthy` are the legacy names for `reachable` / `connected`. Container state
comes from `docker inspect`; `running` is `null` when Docker is not available.

## GET /setup

Connection settings the settings page may show — never the password, the
encryption key, or the ticket.

```json
{"trek_url": "http://127.0.0.1:3000", "email": "admin@example.com", "has_password": true,
 "has_ticket": false, "managed": false, "container": "travel-desk-trek",
 "image": "mauriceboe/trek", "desk_root": "<desk root>", "env_path": "<desk root>/trek.env",
 "data_dir": "<desk root>/trek", "port": 3000, "docker_available": true, "reachable": true}
```

## POST /setup

Body `{"trek_url" | "url", "email", "password", "test_only"?}`. Tests the login;
unless `test_only`, saves the URL to `data/config.json` and the login to
`<desk root>/trek.env` (mode 600). An empty password reuses the stored one.

- authenticated → `{"ok": true, "saved": <bool>, "reachable": true, "authenticated": true, "error": ""}`
- auth failure → 502 `{"ok": false, "reachable": ..., "authenticated": false, "error": "..."}`
- bad input → 400 `{"error": "..."}`

The password is never echoed.

## POST /service/{action}

`action` ∈ `create | start | stop | restart | upgrade | backup`. Every step is
an argv list (no shell string), 300 s timeout. Unknown action → 400.

- `create` — body `{"port", "email", "password"}`; `email` and `password` may
  both be omitted, in which case the app generates the admin login
  (`admin@travel-desk.local` + a random password). Writes `trek.env` (generating
  an at-rest encryption key), then runs the official image bound to loopback with
  its state under `<desk root>/trek/`. Returns `{"ok": true, "action": "create",
  "url", "reachable", "email", "env_path", "output"}` — the email in use, never
  the password.
- `start | stop | restart` — drive the app-managed container.
- `upgrade` — `docker pull` → `docker rm -f` → run again (state kept by the two
  `-v` mounts).
- `backup` — tar `<desk root>/trek/{data,uploads}` to
  `<desk root>/backups/trek-<UTC>.tgz`; only offered for the app-managed service
  (else 400).

Success → `{"ok": true, "action": "<action>", "output": "<stdout tail, 2000 chars>"}`.
A non-zero step → 502 `{"ok": false, "action", "error", "output"}`.

## GET /trips

```json
{"trips": [{"id": 5, "title": "…", "start_date": "2026-10-17", "end_date": "2026-10-19",
            "day_count": 3, "place_count": 16, "url": "http://127.0.0.1:3000/trips/5"}],
 "error": ""}
```

The service unreachable → `{"trips": [], "error": "<message>"}` at 200. `url`
points at the trip planner itself.

## GET /trip?id=5

The service's `GET /api/trips/5/bundle` shaped into a view model:

```json
{
 "trip": {"id": 5, "title": "…", "description": "…", "start": "2026-10-17", "end": "2026-10-19",
          "currency": "AUD", "days": 3, "nights": 2, "url": "http://127.0.0.1:3000/trips/5",
          "cover_place_id": 35},
 "days": [
   {"id": 8, "day": 1, "date": "2026-10-17", "weekday": "…", "title": null, "notes": "…",
    "transport": "driving",
    "items": [
      {"kind": "card", "time": "09:30", "text": "…", "icon": "⛽"},
      {"kind": "stop", "place_id": 26, "time": "11:00", "end": "11:30", "order": 1}
    ]}
 ],
 "places": {"26": {"id": 26, "name": "…", "address": "…", "lat": -38.37, "lng": 144.25,
                   "notes": "…", "price": null, "currency": null, "website": null, "phone": null,
                   "category": null, "duration_minutes": 30,
                   "photo": "/api/apps/travel-desk/photo/26"}},
 "stays": [{"place_id": 40, "name": "…", "address": "…", "lat": -38.75, "lng": 143.66,
            "check_in": "15:00", "check_out": "10:00", "notes": "…", "start_day": 1, "end_day": 2,
            "photo": null}],
 "photos_pending": 6,
 "totals": {"cost": 112.0, "stops": 14, "stays": 2}
}
```

Rules:

- `items` are stably sorted by `time` (`HH:MM`); items with no time go last in
  original order; a card at the same time sorts before a stop. `order` is the
  stop's number within the day, from 1, counting stops only.
- `nights = days - 1` (min 0).
- `places` holds only the places that appear in `items` / `stays`.
- `photo` is `/api/apps/travel-desk/photo/<place_id>` when a photo is cached,
  else `null`; `photos_pending` counts the `null`s (not the confirmed misses).
- `cover_place_id` falls back, when the trip has no cover image, to a place whose
  name matches the title, else the first place with a photo, else `null`.
- `totals.cost` is the sum of the shown places' `price` (0 when none).
- Non-integer id → 400; service 404 → 404; unreachable → 502 `{"error": "…"}`.

## GET /photos?id=5

Resolves and caches photos for every place of the trip that has none yet:

```json
{"photos": {"26": "/api/apps/travel-desk/photo/26", "40": null}, "resolved": 5, "missing": 1}
```

Resolution per place: the place's own image if any, else a Wikipedia page image
by name, else a Wikipedia geosearch near its coordinates; a place with nothing
is recorded as a miss and not retried for 24 h. Cached files and index live under
the app's `data_dir`. The photo work is bounded (short total budget, small
concurrency); a failure only affects that place. Bad id → 400 / 404 / 502.

## GET /photo/{place_id}

The cached image bytes, `Content-Type` by extension,
`Cache-Control: public, max-age=86400`. `place_id` must be numeric (else 400);
no cache → 404.

## GET /org

```json
{"members": [{"id": "leader", "name": "trip-tour-leader", "title": "…", "title_en": "…",
              "layer": "lead", "avatar_letter": "…", "avatar_letter_en": "…", "duty": "…", "duty_en": "…",
              "state": "idle", "state_msg": "", "slot_key": "travel-desk-leader"}]}
```

Each entry is the `desk/members.json` object plus `state`
(`idle | working | blocked`), `state_msg` and `slot_key`. State is inferred from
the current trip's events (`?trip=<slug>`, default = the most recently modified
`runs/events.jsonl`): a member's last event `dispatched|stage` → working,
`failed` → blocked, else idle. `slot_key`: the leader's fixed slot; residents
resolved from the gateway sidebar by folder + title; leaves `null`.

## GET /run?trip=<slug>

```json
{"trip": "<slug>", "request": "<head of request.md>",
 "artifacts": {"request.md": true, "itinerary.json": false, "…": false},
 "trek": {"trip_id": 5, "url": "…", "pushed_at": "…", "places": 14, "days": 3},
 "events": [{"at": "…", "trip": "<slug>", "who": "planner", "kind": "stage", "msg": "…"}]}
```

`artifacts` is the boolean table of the §5 files; `trek` is `trips/<slug>/trek.json`
or `null`; `events` is the last 200. No slug → an empty shape. A malformed slug
→ 400.

## GET /local-trips

```json
{"trips": [{"slug": "202610-demo", "title": "…", "updated_at": "…",
            "trek": {"trip_id": 5, "url": "…"}}]}
```

The `trips/<slug>` directories on disk, `title` from the first line of
`request.md`, `trek` from `trek.json` when present.
