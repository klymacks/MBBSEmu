#!/usr/bin/env bash
# Build a runnable Finn's Realm folder: self-contained MBBSEmu + client + modules.
# Usage:
#   ./scripts/package-finns-realm.sh           # write dist/finns-realm/
#   ./scripts/package-finns-realm.sh --install # also drop a Desktop shortcut
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
DEST="$ROOT/dist/finns-realm"
INSTALL=0
for a in "$@"; do
  case "$a" in
    --install) INSTALL=1 ;;
  esac
done

echo "Packaging Finn's Realm into $DEST"

if [[ ! -f "$ROOT/modules/WCCMMUD/WCCMMUD.DLL" ]]; then
  echo "MajorMUD files are missing from $ROOT/modules/WCCMMUD/" >&2
  exit 1
fi

rm -rf "$DEST"
mkdir -p "$DEST/bin" "$DEST/config" "$DEST/data" "$DEST/modules" "$DEST/scripts" "$DEST/client" "$DEST/share"

echo "Publishing self-contained MBBSEmu (linux-x64)..."
dotnet publish "$ROOT/MBBSEmu/MBBSEmu.csproj" \
  -c Release \
  -r linux-x64 \
  --self-contained true \
  --nologo \
  -o "$DEST/bin"

echo "Copying play client..."
cp -a "$ROOT/scripts/bbs_client.py" "$DEST/scripts/"
cp -a "$ROOT/scripts/preflight.py" "$DEST/scripts/"
cp -a "$ROOT/scripts/PREFLIGHT.md" "$DEST/scripts/"
cp -a "$ROOT/scripts/FinnsRealm" "$DEST/FinnsRealm"
cp -a "$ROOT/scripts/reboot-board.sh" "$DEST/FinnsRealm-reboot"
cp -a "$ROOT/scripts/stop-board.sh" "$DEST/FinnsRealm-stop"
cp -a "$ROOT/scripts/check-board.sh" "$DEST/FinnsRealm-check"
chmod +x "$DEST/FinnsRealm" "$DEST/FinnsRealm-reboot" "$DEST/FinnsRealm-stop" "$DEST/FinnsRealm-check" "$DEST/scripts/bbs_client.py"
cp -a "$ROOT/client/"*.py "$DEST/client/"
  rm -f "$DEST/client/"test_*.py
  mkdir -p "$DEST/client/tdf"
  cp -a "$ROOT/client/tdf/"*.tdf "$DEST/client/tdf/"

echo "Copying config..."
cp -a "$ROOT/config/appsettings.json" "$DEST/config/" 2>/dev/null || true
if [[ ! -f "$DEST/config/appsettings.json" ]]; then
  cat > "$DEST/config/appsettings.json" <<'JSON'
{
  "BBS.Title": "Finn's Realm",
  "BBS.Channels": "32",
  "BBS.CompanyName": "Finn's Realm",
  "BBS.Address1": "-",
  "BBS.Address2": "-",
  "BBS.DataPhone": "-",
  "BBS.VoicePhone": "-",
  "GSBL.BTURNO": "84732615",
  "Cleanup.Time": "03:00",
  "Module.DoLoginRoutine": "True",
  "Telnet.Enabled": "True",
  "Telnet.Port": "2323",
  "Telnet.Heartbeat": "False",
  "Telnet.ConvertCP437ToUTF8": "False",
  "ANSI.Login": "../config/login.ans",
  "Rlogin.Enabled": "False",
  "Database.File": "mbbsemu.db",
  "Btrieve.CacheSize": "32",
  "Timer.Hertz": "36",
  "Account.DefaultKeys": ["DEMO", "NORMAL", "USER", "PAYING"]
}
JSON
fi
# bbs_client paints CP437 itself
python3 - "$DEST/config/appsettings.json" <<'PY'
import json, sys
p = sys.argv[1]
with open(p) as f:
    data = json.load(f)
data["Telnet.ConvertCP437ToUTF8"] = "False"
data["Database.File"] = "mbbsemu.db"
data["ANSI.Login"] = "../config/login.ans"
with open(p, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY
if [[ -f "$ROOT/config/login.ans" ]]; then
  cp -a "$ROOT/config/login.ans" "$DEST/config/"
fi
cp -a "$ROOT/config/sysop.json" "$DEST/config/" 2>/dev/null || true
cp -a "$ROOT/config/player.json" "$DEST/config/" 2>/dev/null || true
cp -a "$ROOT/config/matt.json" "$DEST/config/" 2>/dev/null || true
for ic in finns-realm.png finns-realm-klymacks.png finns-realm-matt.png; do
  [[ -f "$ROOT/config/$ic" ]] && cp -a "$ROOT/config/$ic" "$DEST/share/"
done

echo "Copying MajorMUD (skipping nested source trees)..."
rsync -a \
  --exclude 'MBBSEmu/' \
  --exclude '.git/' \
  --exclude '*.bak' \
  "$ROOT/modules/WCCMMUD/" "$DEST/modules/WCCMMUD/"

if [[ -f "$ROOT/data/mbbsemu.db" ]]; then
  cp -a "$ROOT/data/mbbsemu.db" "$DEST/data/"
fi
cat > "$DEST/data/modules.json" <<EOF
{
  "Modules": [
    {
      "Identifier": "WCCMMUD",
      "Path": "$DEST/modules/WCCMMUD/",
      "MenuOptionKey": "M",
      "Enabled": 1
    }
  ]
}
EOF

cat > "$DEST/HOW-TO-RUN.txt" <<'TXT'
Finn's Realm — packaged

Double-click FinnsRealm, or from a terminal:

  ./FinnsRealm

That starts the board (if it is not up) and opens the 80x25 play window
with the HP/MA footer. Default login is sysop / sysop.

Copy this whole folder to another Linux machine. Keep FinnsRealm, bin/,
config/, client/, scripts/, modules/, and data/ together.

Needs: python3, python3-tk, and xterm (or konsole). No .NET SDK.
TXT

cat > "$DEST/Finn's Realm.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Finn's Realm — klymacks
Comment=MajorMUD on Finn's Realm — klymacks (sysop login)
Exec=$DEST/FinnsRealm --sysop
Path=$DEST
Icon=$DEST/share/finns-realm.png
Terminal=false
Categories=Game;
StartupNotify=true
StartupWMClass=FinnsRealmKlymacks
EOF
chmod +x "$DEST/Finn's Realm.desktop"

cat > "$DEST/Reboot Finn's Realm.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Reboot Finn's Realm
Comment=Stop and restart the Finn's Realm board
Exec=$DEST/FinnsRealm-reboot
Path=$DEST
Icon=$DEST/share/finns-realm.png
Terminal=true
Categories=Game;
StartupNotify=true
EOF
chmod +x "$DEST/Reboot Finn's Realm.desktop"

cat > "$DEST/Stop Finn's Realm.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Stop Finn's Realm
Comment=Shut down the Finn's Realm board
Exec=$DEST/FinnsRealm-stop
Path=$DEST
Icon=$DEST/share/finns-realm.png
Terminal=true
Categories=Game;
StartupNotify=true
EOF
chmod +x "$DEST/Stop Finn's Realm.desktop"

echo "Packaged: $DEST"
echo "Launch with: $DEST/FinnsRealm"

# Copyable archive of the whole folder
( cd "$ROOT/dist" && tar -czf finns-realm.tar.gz finns-realm )
echo "Archive: $ROOT/dist/finns-realm.tar.gz"

if [[ "$INSTALL" == 1 ]]; then
  mkdir -p "$HOME/.local/share/applications"
  DESK="$HOME/Desktop/Finn's Realm.desktop"
  cp -a "$DEST/Finn's Realm.desktop" "$DESK"
  chmod +x "$DESK"
  gio set "$DESK" metadata::trusted true 2>/dev/null || true
  cp -a "$DEST/Finn's Realm.desktop" "$HOME/.local/share/applications/finns-realm.desktop"
  echo "Desktop shortcut: $DESK"

  REBOOT_DESK="$HOME/Desktop/Reboot Finn's Realm.desktop"
  cat > "$REBOOT_DESK" <<EOF
[Desktop Entry]
Type=Application
Name=Reboot Finn's Realm
Comment=Stop and restart the Finn's Realm board
Exec=$ROOT/scripts/reboot-board.sh
Path=$ROOT
Icon=$ROOT/config/finns-realm.png
Terminal=true
Categories=Game;
StartupNotify=true
EOF
  chmod +x "$REBOOT_DESK"
  gio set "$REBOOT_DESK" metadata::trusted true 2>/dev/null || true
  cp -a "$REBOOT_DESK" "$HOME/.local/share/applications/finns-realm-reboot.desktop"
  echo "Desktop shortcut: $REBOOT_DESK"

  STOP_DESK="$HOME/Desktop/Stop Finn's Realm.desktop"
  cat > "$STOP_DESK" <<EOF
[Desktop Entry]
Type=Application
Name=Stop Finn's Realm
Comment=Shut down the Finn's Realm board
Exec=$ROOT/scripts/stop-board.sh
Path=$ROOT
Icon=$ROOT/config/finns-realm.png
Terminal=true
Categories=Game;
StartupNotify=true
EOF
  chmod +x "$STOP_DESK"
  gio set "$STOP_DESK" metadata::trusted true 2>/dev/null || true
  cp -a "$STOP_DESK" "$HOME/.local/share/applications/finns-realm-stop.desktop"
  echo "Desktop shortcut: $STOP_DESK"

  CHECK_DESK="$HOME/Desktop/Check Finn's Realm.desktop"
  cat > "$CHECK_DESK" <<EOF
[Desktop Entry]
Type=Application
Name=Check Finn's Realm
Comment=Preflight: activation, addons, module files
Exec=$ROOT/scripts/check-board.sh
Path=$ROOT
Icon=$ROOT/config/finns-realm.png
Terminal=true
Categories=Game;
StartupNotify=true
EOF
  chmod +x "$CHECK_DESK"
  gio set "$CHECK_DESK" metadata::trusted true 2>/dev/null || true
  cp -a "$CHECK_DESK" "$HOME/.local/share/applications/finns-realm-check.desktop"
  echo "Desktop shortcut: $CHECK_DESK"
fi
