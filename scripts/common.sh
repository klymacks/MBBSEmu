#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$ROOT/vendor/mbbsemu"
EMULATOR="$ROOT/MBBSEmu/bin/Release/net10.0/MBBSEmu"
if [[ ! -x "$EMULATOR" ]]; then
  EMULATOR="$VENDOR/MBBSEmu"
fi
MODULE_DIR="$ROOT/modules/WCCMMUD"
DATA_DIR="$ROOT/data"
CONFIG_DIR="$ROOT/config"
PID_FILE="$DATA_DIR/mbbsemu.pid"
LOG_FILE="$DATA_DIR/mbbsemu.log"
RUNTIME_MODULES="$DATA_DIR/modules.json"
SYSOP_PASSWORD="${SYSOP_PASSWORD:-sysop}"
TELNET_PORT="${TELNET_PORT:-2323}"
FINN_PORT="${FINN_PORT:-2324}"

export DOTNET_BUNDLE_EXTRACT_BASE_DIR="$DATA_DIR/dotnet-bundle"

mkdir -p "$DATA_DIR" "$VENDOR" "$MODULE_DIR"

write_runtime_modules() {
  cat > "$RUNTIME_MODULES" <<EOF
{
  "Modules": [
    {
      "Identifier": "WCCMMUD",
      "Path": "$MODULE_DIR/",
      "MenuOptionKey": "M",
      "Enabled": 1
    }
  ]
}
EOF
}

require_emulator() {
  if [[ ! -x "$EMULATOR" ]]; then
    echo "MBBSEmu is not installed. Run ./scripts/fetch-mbbsemu.sh first." >&2
    exit 1
  fi
}

require_module() {
  if [[ ! -f "$MODULE_DIR/WCCMMUD.DLL" || ! -f "$MODULE_DIR/WCCMMUD.MDF" ]]; then
    echo "local 1.11p module files are missing from $MODULE_DIR" >&2
    echo "Run ./scripts/fetch-module.sh" >&2
    exit 1
  fi
}

emulator_running() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE")"
    if [[ -n "$pid" && -d "/proc/$pid" ]]; then
      return 0
    fi
    rm -f "$PID_FILE"
  fi
  return 1
}

# Compiled MCV and "save for later" files are how rejected Plus/Mud tokens
# (and addon lists) keep coming back after MSG is restored to DEMO.
wipe_license_leftovers() {
  local module="${1:-$MODULE_DIR}"
  local data="${2:-$DATA_DIR}"
  rm -f \
    "$data/activation-later.txt" \
    "$data/wccaddon.sys.saved" \
    "$module/WCCADDON.SYS" \
    "$module/WCCADDON.SYS.saved" \
    "$module/wccaddon.sys.saved" \
    "$module/WCCMMUD.MCV" \
    "$module/WCCMMPLS.MCV"
}

# Live toons live in these files. A packaged WCCUSERS.DB is a ghost:
# given names stay reserved, but the BBS login is often gone.
wipe_player_records() {
  local module="${1:-$MODULE_DIR}"
  local data="${2:-$DATA_DIR}"
  local base
  shopt -s nullglob
  for base in WCCUSERS WCCGANGS WCCBANKS; do
    if [[ -f "$module/${base}.VIR" ]]; then
      cp -a "$module/${base}.VIR" "$module/${base}.DAT"
    fi
    rm -f "$module/${base}.DB" "$module/${base}.db"
  done
  rm -f "$module/WCCRECOV.FLG"
  rm -rf "$data/finn-saves"
}

# sysop comes from -DBRESET. matt must exist so --matt can create a toon.
ensure_play_accounts() {
  local db="${1:-$DATA_DIR/mbbsemu.db}"
  local create="$ROOT/scripts/create_user.py"
  [[ -f "$db" && -f "$create" ]] || return 0
  python3 "$create" --username matt --password matt \
    --keys NORMAL --keys PAYING --keys USER --dbfile "$db" || true
}
