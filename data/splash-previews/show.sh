#!/usr/bin/env bash
# Open the three splash previews. Does not touch the live play window or login.
set -euo pipefail
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
python3 "$HERE/render.py"
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
    -bg '#000000' -fg '#c0c0c0' \
    -fa "$face" -fs "$size" \
    -b 8 \
    -title "$title" \
    -n "$title" \
    -xrm 'XTerm*scrollBar: false' \
    -xrm 'XTerm*XftAntialias: false' \
    -e bash -c "cat '$file'; read -r -n 1" &
}
show "$HERE/A-ice-chrome.utf8.ans" "Finn's Realm splash A — iCE chrome"
show "$HERE/B-acid-fire.utf8.ans" "Finn's Realm splash B — ACiD fire"
show "$HERE/C-sauce-dos.utf8.ans" "Finn's Realm splash C — SAUCE / DOS"
echo "opened 3 preview xterms from $HERE"
echo "plain dumps: $HERE/*.txt"
echo "cp437 .ans: $HERE/*.ans"
