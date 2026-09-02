#!/usr/bin/env bash
# Double-click Check Finn's Realm, or: ./scripts/check-board.sh
set -euo pipefail
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
if [[ -d "$HERE/../modules/WCCMMUD" ]]; then
  ROOT="$(cd "$HERE/.." && pwd)"
elif [[ -d "$HERE/modules/WCCMMUD" ]]; then
  ROOT="$HERE"
else
  echo "Finn's Realm: cannot find the board folder."
  read -rp "Enter to close" || true
  exit 1
fi
PREFLIGHT="$ROOT/scripts/preflight.py"
if [[ ! -f "$PREFLIGHT" ]]; then
  echo "Missing $PREFLIGHT"
  read -rp "Enter to close" || true
  exit 1
fi
set +e
python3 "$PREFLIGHT" "$ROOT"
rc=$?
set -e
echo
if [[ "$rc" -eq 0 ]]; then
  echo "Safe to click Finn's Realm."
elif [[ "$rc" -eq 2 ]]; then
  echo "Launch is allowed, but read the WARNs above."
else
  echo "Do not launch. ./scripts/reset-game.sh to start clean."
fi
echo "Instructions: $ROOT/scripts/PREFLIGHT.md"
read -rp "Enter to close" || true
exit "$rc"
