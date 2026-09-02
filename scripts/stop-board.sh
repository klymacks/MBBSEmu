#!/usr/bin/env bash
# Graceful shutdown of Finn's Realm (SIGTERM, then SIGKILL if it hangs).
# Double-click the desktop shortcut, or: ./scripts/stop-board.sh
set -euo pipefail

HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

if [[ -x "$HERE/bin/MBBSEmu" ]]; then
  ROOT="$HERE"
elif [[ -d "$HERE/../data" ]]; then
  ROOT="$(cd "$HERE/.." && pwd)"
else
  echo "Finn's Realm: cannot find the board folder."
  read -rp "Enter to close" || true
  exit 1
fi

DATA="$ROOT/data"
PID_FILE="$DATA/mbbsemu.pid"
PORT="${TELNET_PORT:-2323}"

port_up() {
  python3 -c "import socket; s=socket.socket(); s.settimeout(0.4); s.connect(('127.0.0.1', $PORT)); s.close()" 2>/dev/null
}

listener_pids() {
  ss -H -tlnp "sport = :$PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u
}

emu_pids() {
  {
    listener_pids
    pgrep -x MBBSEmu || true
    if [[ -f "$PID_FILE" ]]; then
      cat "$PID_FILE"
    fi
    if [[ -f "$ROOT/dist/finns-realm/data/mbbsemu.pid" ]]; then
      cat "$ROOT/dist/finns-realm/data/mbbsemu.pid"
    fi
  } | tr -d ' ' | grep -E '^[0-9]+$' | sort -u
}

echo "Finn's Realm — shutdown"
mapfile -t pids < <(emu_pids)
if [[ ${#pids[@]} -eq 0 ]]; then
  echo "Board is already down."
  rm -f "$PID_FILE"
  read -rp "Enter to close" || true
  exit 0
fi

echo "Stopping the board..."
for pid in "${pids[@]}"; do
  if [[ -d "/proc/$pid" ]]; then
    echo "  SIGTERM $pid"
    kill -TERM "$pid" 2>/dev/null || true
  fi
done
for _ in $(seq 1 20); do
  still=0
  for pid in "${pids[@]}"; do
    if [[ -d "/proc/$pid" ]]; then
      still=1
    fi
  done
  if [[ "$still" == 0 ]]; then
    break
  fi
  sleep 1
done
for pid in "${pids[@]}"; do
  if [[ -d "/proc/$pid" ]]; then
    echo "  SIGKILL $pid"
    kill -KILL "$pid" 2>/dev/null || true
  fi
done
rm -f "$PID_FILE"

for _ in $(seq 1 10); do
  port_up || break
  sleep 1
done
if port_up; then
  echo "Port $PORT is still in use."
  read -rp "Enter to close" || true
  exit 1
fi

# Leftover lock from SIGTERM (MajorMUD only clears this in finrou).
rm -f "$ROOT/modules/WCCMMUD/WCCRECOV.FLG"

echo "Board is down."
read -rp "Enter to close" || true
