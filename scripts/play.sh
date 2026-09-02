#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

if ! emulator_running; then
  "$ROOT/scripts/start.sh"
fi

cols="$(tput cols 2>/dev/null || echo 0)"
rows="$(tput lines 2>/dev/null || echo 0)"
in_cursor=0
if [[ "${TERM_PROGRAM:-}" == "vscode" || -n "${CURSOR_TRACE_ID:-}" || -n "${VSCODE_INJECTION:-}" ]]; then
  in_cursor=1
fi

if [[ "$in_cursor" -eq 1 || "$cols" -lt 80 || "$rows" -lt 24 ]]; then
  echo "Opening Newhaven in its own window. Click that window."
  exec "$ROOT/scripts/play-window.sh" "$@"
fi

exec python3 "$ROOT/scripts/bbs_client.py" 127.0.0.1 "$TELNET_PORT" "$@"
