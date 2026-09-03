#!/usr/bin/env bash
# Full MajorMUD reset: virgin databases, DEMO activation, empty addons.
# Put real codes in LAST after the board is playing.
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
MODULE="$ROOT/modules/WCCMMUD"
DATA="$ROOT/data"
EMU="$ROOT/MBBSEmu/bin/Release/net10.0/MBBSEmu"
SETTINGS="$ROOT/config/appsettings.json"
MODULES_JSON="$DATA/modules.json"
LOG="$DATA/mbbsemu.log"
PID_FILE="$DATA/mbbsemu.pid"
PORT="${TELNET_PORT:-2323}"

port_up() {
  python3 -c "import socket; s=socket.socket(); s.settimeout(0.4); s.connect(('127.0.0.1', $PORT)); s.close()" 2>/dev/null
}

echo "Finn's Realm — start from scratch (DEMO, codes later)"

echo "Stopping the board..."
if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE")"
  if [[ -n "$pid" && -d "/proc/$pid" ]]; then
    kill -TERM "$pid" 2>/dev/null || true
  fi
fi
mapfile -t pids < <(ss -H -tlnp "sport = :$PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)
for pid in "${pids[@]:-}"; do
  [[ -n "$pid" && -d "/proc/$pid" ]] && kill -TERM "$pid" 2>/dev/null || true
done
for _ in $(seq 1 20); do
  port_up || break
  sleep 1
done
mapfile -t pids < <(ss -H -tlnp "sport = :$PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)
for pid in "${pids[@]:-}"; do
  [[ -n "$pid" && -d "/proc/$pid" ]] && kill -KILL "$pid" 2>/dev/null || true
done
rm -f "$PID_FILE"
port_up && { echo "Port $PORT still in use."; exit 1; }

mkdir -p "$DATA"
python3 - "$MODULE" "$DATA/activation-later.txt" <<'PY'
from pathlib import Path
import re, sys
mod = Path(sys.argv[1])
out = Path(sys.argv[2])
def act(p):
    m = re.search(r'ACTIVATE \{([^}]*)\}', p.read_text(errors='replace'))
    return m.group(1) if m else '(none)'
addon = (mod / 'WCCADDON.SYS').read_text(errors='replace').strip()
saved = (Path(sys.argv[2]).parent / 'wccaddon.sys.saved')
if saved.exists() and not addon:
    addon = saved.read_text(errors='replace').strip()
out.write_text(
    "Put these in LAST, after DEMO is playing and C/CP are done.\n\n"
    f"MajorMUD ACTIVATE: {act(mod / 'WCCMMUD.MSG')}\n"
    f"MajorMUD Plus ACTIVATE: {act(mod / 'WCCMMPLS.MSG')}\n\n"
    "Addon codes (WCCADDON.SYS), one per line:\n"
    f"{addon or '(none saved)'}\n"
)
print(f"Saved codes for later: {out}")
PY

echo "Restoring DEMO activation..."
cp -a "$MODULE/WCCMMUD.MSG.original" "$MODULE/WCCMMUD.MSG"
python3 - "$MODULE/WCCMMPLS.MSG" <<'PY'
from pathlib import Path
import re, sys
p = Path(sys.argv[1])
text = p.read_text(errors='replace')
text2, n = re.subn(r'(ACTIVATE \{)[^}]*(\})', r'\1DEMO\2', text, count=1)
if n != 1:
    raise SystemExit(f'could not reset Plus ACTIVATE ({n})')
p.write_text(text2)
print('Plus ACTIVATE -> DEMO')
PY
rm -f "$MODULE/WCCADDON.SYS"

echo "Restoring virgin game databases..."
shopt -s nullglob
for vir in "$MODULE"/*.VIR; do
  base="$(basename "$vir" .VIR)"
  cp -a "$vir" "$MODULE/${base}.DAT"
  rm -f "$MODULE/${base}.DB"
done
rm -f "$MODULE/WCCRECOV.FLG"

echo "Starting the board..."
cd "$DATA"
setsid "$EMU" -CLI -S "$SETTINGS" -C "$MODULES_JSON" -DBREBUILD BBSUSR >>"$LOG" 2>&1 &
echo $! >"$PID_FILE"
ok=0
for _ in $(seq 1 45); do
  if port_up; then
    ok=1
    break
  fi
  sleep 1
done
if [[ "$ok" != 1 ]]; then
  echo "Board did not come up. Last log lines:"
  tail -n 40 "$LOG"
  exit 1
fi

echo "Clearing evil points and saved profiles (must happen before any character)..."
python3 - <<'PY'
import re, select, socket, sys, time

HOST, PORT = "127.0.0.1", 2323
IAC, DO, DONT, WILL, WONT, SB, SE = 255, 253, 254, 251, 252, 250, 240
ANSI_RE = re.compile(rb"\x1b\[[0-9;?]*[A-Za-z]")

def filt(data, sock, pending):
    pending.extend(data)
    out = bytearray()
    i = 0
    buf = pending
    while i < len(buf):
        b = buf[i]
        if b != IAC:
            out.append(b)
            i += 1
            continue
        if i + 1 >= len(buf):
            break
        c = buf[i + 1]
        if c in (DO, DONT, WILL, WONT):
            if i + 2 >= len(buf):
                break
            sock.sendall(bytes((IAC, WONT if c in (DO, DONT) else DONT, buf[i + 2])))
            i += 3
            continue
        if c == SB:
            j = i + 2
            while j + 1 < len(buf) and not (buf[j] == IAC and buf[j + 1] == SE):
                j += 1
            if j + 1 >= len(buf):
                break
            i = j + 2
            continue
        i += 2 if c == IAC else 2
    del pending[:i]
    return bytes(out)

def visible(data):
    return ANSI_RE.sub(b"", data).decode("latin1", "replace").lower()

def wait_for(sock, pending, needles, timeout):
    hay = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        ready, _, _ = select.select([sock], [], [], min(0.3, max(0.05, deadline - time.time())))
        if sock not in ready:
            continue
        data = sock.recv(4096)
        if not data:
            break
        out = filt(data, sock, pending)
        hay += visible(out)
        if any(n in hay for n in needles):
            return hay
    return hay

def send_line(sock, text):
    sock.sendall(text.encode("ascii") + b"\r")
    time.sleep(0.25)

sock = socket.create_connection((HOST, PORT), timeout=8)
sock.settimeout(None)
pending = bytearray()
try:
    wait_for(sock, pending, ["username:"], 10)
    send_line(sock, "sysop")
    hay = wait_for(sock, pending, ["password:", "already logged"], 8)
    if "already logged" in hay:
        raise SystemExit("sysop already logged in — close that window and re-run")
    send_line(sock, "sysop")
    wait_for(sock, pending, ["make your selection"], 12)
    send_line(sock, "M")
    wait_for(sock, pending, ["[majormud]", "enter the realm"], 10)
    send_line(sock, "SYSOP")
    wait_for(sock, pending, ["sysop menu", "clear all saved"], 8)
    send_line(sock, "C")
    time.sleep(0.6)
    send_line(sock, "Y")
    time.sleep(0.6)
    send_line(sock, "CP")
    time.sleep(0.6)
    send_line(sock, "Y")
    time.sleep(0.8)
    send_line(sock, "X")
    time.sleep(0.4)
    print("C / CP sent")
finally:
    sock.close()
PY

echo
grep -aE 'DEMO MODE|users\]|Module Added|CNF options' "$LOG" | tail -8
echo
echo "Board is up in DEMO. Do not enter activation codes yet."
echo "Play first. Codes to paste later: $DATA/activation-later.txt"
if [[ -f "$ROOT/scripts/preflight.py" ]]; then
  echo
  python3 "$ROOT/scripts/preflight.py" "$ROOT" || true
fi
