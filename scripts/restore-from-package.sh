#!/usr/bin/env bash
# Put module files back from dist/finns-realm, then wipe player records.
# Use this when live WCCMMUD/data vanished. Packaged toons are ghosts —
# given names stay reserved with no BBS login. Do not copy them.
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
# shellcheck source=common.sh
source "$ROOT/scripts/common.sh"

DEST="$ROOT/dist/finns-realm"
SRC="$DEST/modules/WCCMMUD"
MODULE="$ROOT/modules/WCCMMUD"
DATA="$ROOT/data"
PORT="${TELNET_PORT:-2323}"

if [[ ! -f "$SRC/WCCMMUD.DLL" ]]; then
  echo "No packaged MajorMUD at $SRC"
  exit 1
fi

echo "Finn's Realm — restore modules, wipe characters"

if emulator_running || python3 -c "import socket; s=socket.socket(); s.settimeout(0.4); s.connect(('127.0.0.1', $PORT)); s.close()" 2>/dev/null; then
  echo "Stop the board first (Stop Finn's Realm), then run this."
  exit 1
fi

mkdir -p "$MODULE" "$DATA"
echo "Copying module files from the package (not player DBs)..."
rsync -a \
  --exclude 'MBBSEmu/' \
  --exclude '.git/' \
  --exclude '*.bak' \
  --exclude 'WCCUSERS.DB' \
  --exclude 'WCCUSERS.db' \
  --exclude 'WCCUSERS.DAT' \
  --exclude 'WCCGANGS.DB' \
  --exclude 'WCCGANGS.db' \
  --exclude 'WCCBANKS.DB' \
  --exclude 'WCCBANKS.db' \
  "$SRC/" "$MODULE/"

echo "Wiping characters — virgin users/gangs/banks, no packaged ghosts."
wipe_player_records "$MODULE" "$DATA"

echo "Restoring DEMO activation..."
if [[ -f "$MODULE/WCCMMUD.MSG.original" ]]; then
  cp -a "$MODULE/WCCMMUD.MSG.original" "$MODULE/WCCMMUD.MSG"
fi
python3 - "$MODULE/WCCMMPLS.MSG" <<'PY'
from pathlib import Path
import re, sys
p = Path(sys.argv[1])
if not p.is_file():
    raise SystemExit(0)
text = p.read_text(errors="replace")
text2, n = re.subn(r"(ACTIVATE \{)[^}]*(\})", r"\1DEMO\2", text, count=1)
if n == 1:
    p.write_text(text2)
    print("Plus ACTIVATE -> DEMO")
PY
wipe_license_leftovers "$MODULE" "$DATA"

write_runtime_modules
printf 'demo\n' > "$DATA/finns-stage"
ensure_play_accounts "$DATA/mbbsemu.db"

echo
echo "Characters are empty. Create klymacks on sysop, Matt on --matt."
echo "Start with: ./scripts/reboot-board.sh"
