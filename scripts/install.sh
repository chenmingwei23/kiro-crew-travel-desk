#!/usr/bin/env bash
# Travel Desk install accelerator.
#
# Optional. The backend self-initialises the desk root the first time it loads
# (backend/routes.py::_ensure_install_state), so the app works without ever
# running this. Running it just does that one step now instead of on first load.
#
# It resolves the gateway home, then creates the desk root skeleton with
# `orchestrate.py init`. It writes nothing else; connecting or starting the trip
# planner is done in the app's Settings page.
#
# Env note: the gateway runs lifecycle scripts with a minimal env allowlist, so
# KIROCREW_HOME may not be passed through. When absent, the home is derived from
# the script's own location (this app under <home>/apps/), then from $HOME.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

resolve_home() {
  if [ -n "${KIROCREW_HOME:-}" ]; then
    printf '%s\n' "${KIROCREW_HOME}"
  elif [ "$(basename "$(dirname "${APP_DIR}")")" = "apps" ]; then
    # Installed at <gateway home>/apps/travel-desk — the home is two levels up.
    printf '%s\n' "$(cd "${APP_DIR}/../.." && pwd)"
  elif [ -d "${HOME:-}/.kiro/crew" ]; then
    printf '%s\n' "${HOME}/.kiro/crew"
  else
    printf '%s\n' "${HOME:-}/.kirocrew"
  fi
}

CREW_HOME="$(resolve_home)"
echo "travel-desk: gateway home ${CREW_HOME}"

# Create the desk root skeleton (idempotent). deskpaths resolves the desk root
# the same way the backend does, honouring TRAVEL_DESK_ROOT and data/config.json;
# passing KIROCREW_HOME keeps this run consistent with the home resolved above.
KIROCREW_HOME="${CREW_HOME}" python3 "${APP_DIR}/engine/orchestrate.py" init

echo "travel-desk: desk root ready. Connect or start the trip planner from the app's Settings page."
