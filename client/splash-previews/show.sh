#!/usr/bin/env bash
# Preview saved splash candidates. Does not change the live client or login.
set -euo pipefail
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
export DISPLAY="${DISPLAY:-:0}"
face='monospace'
size=16
if fc-list 'Px IBM VGA8' family 2>/dev/null | grep -q 'Px IBM VGA8'; then
  face='Px IBM VGA8'
  size=18
fi
show() {
  local file="$1" title="$2"
  xterm +aw +sb \
    -class FinnsRealmSplashPreview \
    -geometry 80x25 \
    -bg '#000000' -fg '#c0c0c8' \
    -fa "$face" -fs "$size" \
    -b 8 \
    -title "$title" \
    -n "$title" \
    -xrm 'XTerm*scrollBar: false' \
    -xrm 'XTerm*XftAntialias: false' \
    -e bash -c "cat '$file'; read -r -n 1" &
}
show "$HERE/FINAL-finns-realm.utf8.ans" "Finn's Realm splash FINAL"
echo "opened FINAL preview from $HERE"
echo "live connect uses this piece"
