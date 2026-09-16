#!/usr/bin/env bash
# Travel Desk uninstall.
#
# Stops background work and removes only what this app created outside its own
# directory:
#   1. The app-managed trip planner Docker container — ONLY when the config says
#      the app runs it (trekManaged=true). A planner you run yourself is left
#      alone.
#   2. The desk root (all trip data) — ONLY when PURGE_DATA=1. Otherwise it is
#      kept, and this prints where it is.
# It touches nothing else.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

resolve_home() {
  if [ -n "${KIROCREW_HOME:-}" ]; then
    printf '%s\n' "${KIROCREW_HOME}"
  elif [ "$(basename "$(dirname "${APP_DIR}")")" = "apps" ]; then
    printf '%s\n' "$(cd "${APP_DIR}/../.." && pwd)"
  elif [ -d "${HOME:-}/.kiro/crew" ]; then
    printf '%s\n' "${HOME}/.kiro/crew"
  else
    printf '%s\n' "${HOME:-}/.kirocrew"
  fi
}

CREW_HOME="$(resolve_home)"

# Resolve the container name, whether the app manages it, and the desk root the
# same way the backend does. Falls back to reading data/config.json directly.
CFG="$(KIROCREW_HOME="${CREW_HOME}" python3 - "${APP_DIR}" <<'PY'
import json, sys
from pathlib import Path

app = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(app / "engine"))
try:
    import deskpaths
    cfg = deskpaths.load_config()
    container = deskpaths.trek_container()
    desk = str(deskpaths.desk_root())
except Exception:
    cfg = {}
    try:
        cfg = json.loads((app / "data" / "config.json").read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    container = cfg.get("trekContainer") or "travel-desk-trek"
    desk = cfg.get("deskRoot") or ""

managed = "1" if cfg.get("trekManaged") else "0"
print(container)
print(managed)
print(desk)
PY
)"

CONTAINER="$(printf '%s\n' "${CFG}" | sed -n '1p')"
MANAGED="$(printf '%s\n' "${CFG}" | sed -n '2p')"
DESK_ROOT="$(printf '%s\n' "${CFG}" | sed -n '3p')"

# 1. App-managed trip planner container.
if [ "${MANAGED}" = "1" ]; then
  if command -v docker >/dev/null 2>&1; then
    echo "travel-desk: stopping and removing the trip planner container ${CONTAINER}"
    docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
  else
    echo "travel-desk: docker not found; leaving container ${CONTAINER} (if any) alone"
  fi
else
  echo "travel-desk: the trip planner is not app-managed; leaving it running"
fi

# 2. User data at the desk root.
if [ "${PURGE_DATA:-0}" = "1" ]; then
  if [ -n "${DESK_ROOT}" ] && [ -d "${DESK_ROOT}" ]; then
    echo "travel-desk: PURGE_DATA=1 — deleting all trip data at ${DESK_ROOT}"
    rm -rf "${DESK_ROOT}"
  else
    echo "travel-desk: PURGE_DATA=1 but no desk root was found to delete"
  fi
else
  echo "travel-desk: keeping all trip data at ${DESK_ROOT:-<desk root>} (set PURGE_DATA=1 to remove it)"
fi

echo "travel-desk: uninstall complete"
