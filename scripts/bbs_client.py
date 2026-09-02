#!/usr/bin/env python3
"""Telnet client that emulates an 80x25 IBM-PC screen.

MajorMUD's character sheet is a MajorBBS full-screen form. The server
paints field values with cursor-addressed overlays. A modern terminal
that wraps, treats a box glyph as two cells, or ignores CSI ... f
leaves the ???? template on screen and eats keystrokes into the wrong
field — or into a 2/3-byte input buffer FSD then ignores.

This client keeps an 80x25 cell grid (one CP437 byte = one cell, no
wrap), redraws that grid, and sends keys one at a time so FSD sees
either a single ASCII byte or a complete ESC[A / ESC[B packet.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import select
import shutil
import socket
import sys
import termios
import time
import tkinter
import traceback
import tty
from pathlib import Path

IAC, DONT, DO, WONT, WILL = 255, 254, 253, 252, 251
SB, SE = 250, 240
ECHO, SGA, TTYPE, NAWS = 1, 3, 24, 31

COLS, ROWS = 80, 25
CHROME = 5
KEY_GAP = 0.1
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from client.brain import Brain
from client.localnet import LOOPBACK_HOSTS, is_loopback_host
from client.parse import events_from_payload, harvest_screen, parse_events
from client.paths import attack_line
from client.pvp import clear_lock, is_locked
from client.realm_map import DEFAULT_PATH, Atlas
from client.state import WorldState
from client.transcript import Transcript

LOCAL_HOSTS = LOOPBACK_HOSTS
KEY_F1 = b"\x00F1"
KEY_F2 = b"\x00F2"
KEY_F3 = b"\x00F3"
KEY_F4 = b"\x00F4"
KEY_F5 = b"\x00F5"
KEY_F6 = b"\x00F6"
KEY_F7 = b"\x00F7"
KEY_F8 = b"\x00F8"
KEY_F9 = b"\x00F9"
KEY_F10 = b"\x00F10"
KEY_F11 = b"\x00F11"
KEY_UP = bytes((0x1B, ord("["), 65))
KEY_DN = bytes((0x1B, ord("["), 66))
HOLD_SNAPSHOT = ROOT / "data" / "screen-hold.txt"
_CLIP_ROOT: tkinter.Tk | None = None

# Peek only — never takeover. Inventory/Invite/Invoke share `inv` in 1.11p.
PEEK_COMMANDS = {
    KEY_F2: "look",
    KEY_F3: "health",
    KEY_F4: "inventory",
    KEY_F5: "exp",
    KEY_F6: "who",
}

# F1–F10 chrome. One table: footer tip, help overlay, and HOLD all read this.
# on = live/active; off = the other state; held = frozen header word.
FKEYS: dict[int, dict[str, str]] = {
    1: {"on": "panic"},
    2: {"on": "look"},
    3: {"on": "health", "short": "hp"},
    4: {"on": "inv"},
    5: {"on": "exp"},
    6: {"on": "who"},
    7: {"on": "hunt", "off": "hunt off"},
    8: {"on": "ambush", "off": "walk", "note": "(ninja)"},
    9: {"on": "join", "off": "join off"},
    10: {"on": "hold", "off": "live", "held": "HOLD"},
    11: {"on": "train", "off": "live", "held": "SHEET"},
}


def fkey_label(
    n: int,
    *,
    style: str = "tip",
    active: bool | None = None,
    word: str | None = None,
    short: bool = False,
    held: bool = False,
    copied: bool = False,
) -> str:
    """One F-key formatter. Flags pick tip, help, HOLD header, or HOLD tip."""
    spec = FKEYS[n]
    if style == "hold_tip":
        tag = fkey_label(n, held=True)
        live = fkey_label(n, active=False)
        if copied:
            return f"{tag}  copied — Ctrl+V to paste    {live}"
        return f"{tag}  {live}  open data/screen-hold.txt"
    if style == "sheet_tip":
        tag = fkey_label(n, held=True)
        live = fkey_label(n, active=False)
        return f"{tag}  {live}  no health/exp/hunt until SAVE"
    if held and spec.get("held"):
        return spec["held"]
    if word is not None:
        action = word
    elif short and spec.get("short"):
        action = spec["short"]
    elif active is False:
        action = spec.get("off") or spec["on"]
    elif style == "help" and spec.get("off"):
        action = f"{spec['on']} / {spec['off']}"
        if spec.get("note"):
            action = f"{action} {spec['note']}"
    else:
        action = spec["on"]
    if style == "word":
        return action
    if style == "help":
        return f"F{n:<11}{action}"
    return f"F{n} {action}"

# SS3 / 8-bit SS3: P–S are F1–F4; T–W are F5–F8 on some terms.
_SS3_FKEYS = {
    80: KEY_F1,
    81: KEY_F2,
    82: KEY_F3,
    83: KEY_F4,
    84: KEY_F5,
    85: KEY_F6,
    86: KEY_F7,
    87: KEY_F8,
    88: KEY_F9,
    89: KEY_F10,
}
# Linux console ESC [[ A–E is F1–F5.
_LINUX_FKEYS = {
    65: KEY_F1,
    66: KEY_F2,
    67: KEY_F3,
    68: KEY_F4,
    69: KEY_F5,
}
# CSI n~  (xterm F5+; also F1–F4 in VT220 mode). 16 is unused.
_CSI_FKEYS = {
    11: KEY_F1,
    12: KEY_F2,
    13: KEY_F3,
    14: KEY_F4,
    15: KEY_F5,
    17: KEY_F6,
    18: KEY_F7,
    19: KEY_F8,
    20: KEY_F9,
    21: KEY_F10,
    23: KEY_F11,
}
_CSI_SS3 = {
    b"\x1b[OP": KEY_F1,
    b"\x1b[OQ": KEY_F2,
    b"\x1b[OR": KEY_F3,
    b"\x1b[OS": KEY_F4,
}


class Telnet:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self._iac = bytearray()

    def feed(self, data: bytes) -> bytes:
        out = bytearray()
        i = 0
        buf = self._iac + data
        self._iac.clear()
        while i < len(buf):
            b = buf[i]
            if b != IAC:
                out.append(b)
                i += 1
                continue
            if i + 1 >= len(buf):
                self._iac.append(IAC)
                break
            cmd = buf[i + 1]
            if cmd == IAC:
                out.append(IAC)
                i += 2
                continue
            if cmd in (WILL, WONT, DO, DONT):
                if i + 2 >= len(buf):
                    self._iac.extend(buf[i:])
                    break
                self._negotiate(cmd, buf[i + 2])
                i += 3
                continue
            if cmd == SB:
                end = buf.find(bytes((IAC, SE)), i + 2)
                if end < 0:
                    self._iac.extend(buf[i:])
                    break
                i = end + 2
                continue
            i += 2
        return bytes(out)

    def _negotiate(self, cmd: int, opt: int) -> None:
        if cmd == WILL and opt in (ECHO, SGA):
            self.sock.sendall(bytes((IAC, DO, opt)))
        elif cmd == DO and opt == SGA:
            self.sock.sendall(bytes((IAC, WILL, SGA)))
        elif cmd == DO and opt == TTYPE:
            self.sock.sendall(bytes((IAC, WILL, TTYPE)))
            self.sock.sendall(
                bytes((IAC, SB, TTYPE, 0)) + b"ANSI" + bytes((IAC, SE))
            )
        elif cmd == DO and opt == NAWS:
            self.sock.sendall(bytes((IAC, WILL, NAWS)))
            self.sock.sendall(bytes((IAC, SB, NAWS, 0, 80, 0, 25, IAC, SE)))
        elif cmd == DO:
            self.sock.sendall(bytes((IAC, WONT, opt)))
        elif cmd == WILL:
            self.sock.sendall(bytes((IAC, DONT, opt)))

    def send(self, data: bytes) -> None:
        self.sock.sendall(data)


class Cell:
    __slots__ = ("ch", "fg", "bg", "bold", "rev")

    def __init__(self) -> None:
        self.ch = " "
        self.fg = 7
        self.bg = 0
        self.bold = False
        self.rev = False

    def style_key(self) -> tuple[int, int, bool, bool]:
        return (self.fg, self.bg, self.bold, self.rev)


def _blank() -> Cell:
    return Cell()


class AnsiScreen:
    """80x25 CP437 screen. One incoming byte is one cell. Wrap stays off."""

    def __init__(self, cols: int = COLS, rows: int = ROWS) -> None:
        self.cols = cols
        self.rows = rows
        self.buf = [[_blank() for _ in range(cols)] for _ in range(rows)]
        self.cx = 0
        self.cy = 0
        self.saved = (0, 0)
        self.fg = 7
        self.bg = 0
        self.bold = False
        self.rev = False
        self._esc = bytearray()
        self.generation = 0

    def feed(self, data: bytes) -> None:
        if not data:
            return
        i = 0
        while i < len(data):
            if self._esc:
                self._esc.append(data[i])
                i += 1
                if self._esc_complete():
                    self._apply_esc(bytes(self._esc))
                    self._esc.clear()
                elif len(self._esc) > 48:
                    self._esc.clear()
                continue
            b = data[i]
            if b == 0x1B:
                self._esc.append(b)
                i += 1
                continue
            i = self._put_from(data, i)
        self.generation += 1

    def _esc_complete(self) -> bool:
        e = self._esc
        if len(e) == 1:
            return False
        if e[1] == ord("["):
            return len(e) >= 3 and 0x40 <= e[-1] <= 0x7E
        if e[1] in (ord("]"),):
            return e[-1] in (7, ord("\\"))
        return True

    def _apply_esc(self, seq: bytes) -> None:
        if seq in (b"\x1b7", b"\x1b[s"):
            self.saved = (self.cx, self.cy)
            return
        if seq in (b"\x1b8", b"\x1b[u"):
            self.cx, self.cy = self.saved
            return
        if not seq.startswith(b"\x1b["):
            return
        body = seq[2:-1]
        final = seq[-1]
        priv = False
        if body.startswith(b"?"):
            priv = True
            body = body[1:]
        params = []
        if body:
            for part in body.split(b";"):
                if part.isdigit():
                    params.append(int(part))
                elif part == b"":
                    params.append(0)
                else:
                    return
        self._csi(priv, params, final)

    def _csi(self, priv: bool, params: list[int], final: int) -> None:
        if priv:
            return

        def p(idx: int, default: int) -> int:
            if idx < len(params) and params[idx]:
                return params[idx]
            return default

        if final in (ord("H"), ord("f")):
            y = p(0, 1)
            x = p(1, 1)
            self.cy = min(self.rows - 1, max(0, y - 1))
            self.cx = min(self.cols - 1, max(0, x - 1))
            return
        if final == ord("A"):
            self.cy = max(0, self.cy - p(0, 1))
            return
        if final == ord("B"):
            self.cy = min(self.rows - 1, self.cy + p(0, 1))
            return
        if final == ord("C"):
            self.cx = min(self.cols - 1, self.cx + p(0, 1))
            return
        if final == ord("D"):
            self.cx = max(0, self.cx - p(0, 1))
            return
        if final == ord("J"):
            mode = p(0, 0)
            if mode == 2:
                self.buf = [[_blank() for _ in range(self.cols)] for _ in range(self.rows)]
                self.cx = 0
                self.cy = 0
            elif mode == 0:
                self._erase(self.cx, self.cy, self.cols, self.cy)
                for y in range(self.cy + 1, self.rows):
                    self._erase(0, y, self.cols, y)
            elif mode == 1:
                for y in range(0, self.cy):
                    self._erase(0, y, self.cols, y)
                self._erase(0, self.cy, self.cx + 1, self.cy)
            return
        if final == ord("K"):
            mode = p(0, 0)
            if mode == 0:
                self._erase(self.cx, self.cy, self.cols, self.cy)
            elif mode == 1:
                self._erase(0, self.cy, self.cx + 1, self.cy)
            else:
                self._erase(0, self.cy, self.cols, self.cy)
            return
        if final == ord("m"):
            self._sgr(params or [0])

    def _erase(self, x0: int, y: int, x1: int, _y1: int) -> None:
        row = self.buf[y]
        for x in range(x0, min(x1, self.cols)):
            row[x] = _blank()

    def _sgr(self, params: list[int]) -> None:
        if not params:
            params = [0]
        for n in params:
            if n == 0:
                self.fg, self.bg, self.bold, self.rev = 7, 0, False, False
            elif n == 1:
                self.bold = True
            elif n == 7:
                self.rev = True
            elif n == 22:
                self.bold = False
            elif n == 27:
                self.rev = False
            elif 30 <= n <= 37:
                self.fg = n - 30
            elif 40 <= n <= 47:
                self.bg = n - 40
            elif 90 <= n <= 97:
                self.fg = n - 90
                self.bold = True
            elif 100 <= n <= 107:
                self.bg = n - 100

    def _put_from(self, data: bytes, i: int) -> int:
        b = data[i]
        if b in (0, 7):
            return i + 1
        if b == 8:
            self.cx = max(0, self.cx - 1)
            return i + 1
        if b == 9:
            self.cx = min(self.cols - 1, (self.cx + 8) & ~7)
            return i + 1
        if b == 10:
            if self.cy < self.rows - 1:
                self.cy += 1
            else:
                self.buf.pop(0)
                self.buf.append([_blank() for _ in range(self.cols)])
            return i + 1
        if b == 13:
            self.cx = 0
            return i + 1
        self._put_char(bytes((b,)).decode("cp437", "replace"))
        return i + 1

    def _put_char(self, ch: str) -> None:
        if self.cx >= self.cols:
            self.cx = self.cols - 1
        cell = Cell()
        cell.ch = ch
        cell.fg = self.fg
        cell.bg = self.bg
        cell.bold = self.bold
        cell.rev = self.rev
        self.buf[self.cy][self.cx] = cell
        if self.cx < self.cols - 1:
            self.cx += 1

    def line(self, y: int) -> str:
        return "".join(c.ch for c in self.buf[y])

    def text(self) -> str:
        return "\n".join(self.line(y) for y in range(self.rows))

    def looks_like_creation(self) -> bool:
        """FSD sheet (create or TRAIN STATS). [HP=] means the form is gone."""
        blob = self.text()
        if "[HP=" in blob:
            return False
        if "Given Name" not in blob:
            return False
        return (
            "Character Creation" in blob
            or "TRAIN STATS" in blob
            or "Point Cost Chart" in blob
        )

    def leave_form(self) -> None:
        """Drop leftover FSD field style — same defaults as a new screen."""
        self.fg, self.bg, self.bold, self.rev = 7, 0, False, False
        self._esc.clear()
        self.generation += 1

    def render(self) -> bytes:
        out = bytearray(b"\x1b[?25l")
        prev: tuple[int, int, bool, bool] | None = None
        for y in range(self.rows):
            out += f"\x1b[{y + 1};1H".encode()
            for cell in self.buf[y]:
                key = cell.style_key()
                if key != prev:
                    out += _sgr_bytes(cell)
                    prev = key
                ch = cell.ch if cell.ch.isprintable() or cell.ch == " " else " "
                out += ch.encode("utf-8", "replace")
        out += _sgr_bytes(Cell())
        out += f"\x1b[{self.cy + 1};{self.cx + 1}H".encode()
        out += b"\x1b[?25h"
        return bytes(out)


def _sgr_bytes(cell: Cell) -> bytes:
    fg, bg = cell.fg, cell.bg
    if cell.rev:
        fg, bg = bg, fg
    parts = ["0"]
    if cell.bold:
        parts.append("1")
    parts.append(str(30 + fg))
    parts.append(str(40 + bg))
    return f"\x1b[{';'.join(parts)}m".encode()


def realm_line(text: str) -> str:
    """Visible swing is `k` (kill). `a name` is speech; `at acid` becomes `a id slime`."""
    raw = text.strip()
    low = raw.lower()
    if low in {"attack", "kill"}:
        return attack_line()
    if low.startswith("attack "):
        return attack_line(raw[7:])
    if low.startswith("kill "):
        return attack_line(raw[5:])
    return raw


class KeyPacer:
    """FSD only accepts one ASCII byte or one 3-byte arrow per poll."""

    def __init__(self) -> None:
        self._q: collections.deque[bytes] = collections.deque()
        self._ready_at = 0.0

    def push(self, key: bytes) -> None:
        if key:
            self._q.append(key)

    def push_text(self, text: str, *, wipe: bool = True) -> None:
        """One line, one CR. Do not prefix backspaces — extras eat `at giant rat`."""
        line = realm_line(text) if wipe else text
        if line:
            self._q.append(line.encode("ascii", "replace") + b"\r")

    def pending(self) -> bool:
        return bool(self._q)

    def clear(self) -> None:
        self._q.clear()

    def take(self, now: float) -> bytes | None:
        if not self._q or now < self._ready_at:
            return None
        key = self._q.popleft()
        self._ready_at = now + KEY_GAP
        return key


class Autopilot:
    """BBS login and enter the realm. Character creation is yours."""

    def __init__(self, player: dict[str, object], play: bool) -> None:
        self.username = str(player.get("username", "klymacks"))
        self.password = str(player.get("password", "klymacks1"))
        self.play = play
        self.phase = "user"
        self._until = 0.0

    def hint(self) -> str:
        return {
            "user": "signing in...",
            "pass": "signing in...",
            "bbs": "opening the board...",
            "mud": "entering the realm...",
            "play": "your keyboard",
            "blocked": f"{self.username} already logged in — close that window",
        }.get(self.phase, "connected")

    def takeover(self) -> None:
        if self.phase not in ("user", "pass"):
            self.phase = "play"

    def _pause(self, seconds: float) -> None:
        self._until = time.monotonic() + seconds

    def tick(self, text: str, pacer: KeyPacer) -> None:
        low = text.lower()
        if "already logged in" in low or "only 1 connection" in low:
            self.phase = "blocked"
            pacer.clear()
            return
        if pacer.pending() or time.monotonic() < self._until:
            return
        if self.phase == "play" or self.phase == "blocked":
            return
        if self.phase == "user" and "Username:" in text:
            pacer.push_text(self.username, wipe=False)
            self.phase = "pass"
            return
        if self.phase == "pass" and "Password:" in text:
            pacer.push_text(self.password, wipe=False)
            self.phase = "bbs"
            return
        if self.phase == "bbs" and "Make your selection" in text:
            pacer.push_text("M", wipe=False)
            self.phase = "mud" if self.play else "play"
            return
        if not self.play:
            return
        if self.phase == "mud" and ("[MAJORMUD]:" in text or "Enter the Realm" in text):
            pacer.push_text("E", wipe=False)
            self.phase = "play"
            self._pause(0.4)


def load_player(path: Path) -> dict[str, object]:
    data: dict[str, object] = {
        "username": "klymacks",
        "password": "klymacks1",
        "auto_login": True,
        "auto_play": True,
        "pvp": False,
    }
    if path.is_file():
        loaded = json.loads(path.read_text())
        if isinstance(loaded, dict):
            data.update(loaded)
    return data


def board_aka(player: dict[str, object]) -> str:
    """Every local login and given name — sysop must not lock out Matt."""
    parts = [
        str(player.get("username") or ""),
        str(player.get("given") or ""),
        str(player.get("character") or ""),
    ]
    for path in (ROOT / "config" / "player.json", ROOT / "config" / "sysop.json"):
        if not path.is_file():
            continue
        try:
            loaded = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(loaded, dict):
            for key in ("username", "given", "character"):
                parts.append(str(loaded.get(key) or ""))
    return " ".join(parts)


def paint_splash(screen: AnsiScreen, host: str, port: int) -> None:
    if port == 2324:
        sub = "          |         original game  --  Willow Road           |"
        flavor = "          |         no day clock.  no level cap.  Go on.     |"
    else:
        sub = "          |      demo clock board  --  local 1.11p on 2323    |"
        flavor = "          |            not the desktop game.  Go on.         |"
    lines = (
        "",
        "            .----------------------------------------------.",
        "           /                                                \\",
        "          |              F I N N ' S   R E A L M              |",
        "          |                                                  |",
        sub,
        "          |                                                  |",
        flavor,
        "           \\                                                /",
        "            '----------------------------------------------'",
        "",
        f"                      connecting  {host}:{port}",
        "",
        "                   click this window if it is not focused",
    )
    screen.feed(b"\x1b[2J\x1b[1;36m")
    for i, line in enumerate(lines):
        screen.feed(f"\x1b[{i + 5};1H".encode() + line.encode("ascii") + b"\x1b[K")
    screen.feed(b"\x1b[0m")


def status_line(screen: AnsiScreen, host: str) -> str:
    text = screen.text()
    if screen.looks_like_creation():
        return "character sheet"
    if "[HP=" in text or "hits:" in text.lower():
        return "in the realm"
    if "[MAJORMUD]" in text or "Enter the Realm" in text:
        return "MajorMUD menu  ·  press E"
    if "Make your selection" in text:
        return "board menu"
    if "Username:" in text or "Password:" in text:
        return "signing in"
    if is_loopback_host(host):
        return "Finn's Realm"
    return "blocked"


def form_frozen(screen: AnsiScreen, sheet_lock: bool = False) -> bool:
    """TRAIN STATS / creation, or F11 lock. Status peeks must not type here."""
    return bool(sheet_lock or screen.looks_like_creation())


def use_local_input(
    screen: AnsiScreen, state: WorldState, sheet_lock: bool = False
) -> bool:
    """Type on the > bar in the realm. Sheet / TRAIN STATS keeps FSD keys."""
    return state.in_realm and not form_frozen(screen, sheet_lock)


def realm_bar_text(typed: str) -> str:
    """Letters on the > bar. Never password-mask."""
    return typed[:76]


def handle_special_key(
    key: bytes,
    brain: Brain,
    pacer: KeyPacer,
    *,
    in_realm: bool,
    state: WorldState | None = None,
) -> str | None:
    """F1 panic, F2–F6 peek, F7 hunt, F8 ambush, F9 join, F10 hold, F11 train.

    Peek / hold never call takeover(). Hold only freezes the painted
    grid; hunt keeps ticking. F11 freezes health/exp/hunt/peek so the
    TRAIN STATS / creation form is not typed into. F8 walk→ambush paces
    `sn` (or `u` if a lop is in the pit) immediately — not on the next
    hunt tick.
    """
    if key == KEY_F1:
        if in_realm and state is not None:
            brain.panic(state, pacer.push_text)
        return "panic"
    if key == KEY_F7:
        brain.toggle_hunt()
        return "hunt"
    if key == KEY_F8:
        was_on = brain.stealth_label() == "ambush"
        brain.toggle_stealth()
        now_on = brain.stealth_label() == "ambush"
        if not was_on and now_on and in_realm and state is not None:
            for cmd in brain.on_ambush_on(state):
                pacer.push_text(cmd)
        return "ambush"
    if key == KEY_F9:
        brain.toggle_auto_join()
        return "join"
    if key == KEY_F10:
        return "hold"
    if key == KEY_F11:
        return "sheet"
    cmd = PEEK_COMMANDS.get(key)
    if cmd is None:
        return None
    if in_realm:
        pacer.push_text(cmd)
    return "peek"


def toggle_sheet(
    brain: Brain,
    state: WorldState,
    *,
    locked: bool,
    on_form: bool,
) -> tuple[str, str | None]:
    """F11. Returns (lock|walk|unlock, mud_line_or_none). No takeover."""
    if locked or on_form:
        brain.cancel_train()
        return "unlock", None
    if not state.in_realm:
        return "lock", None
    _kind, mud = handle_client_line("train", brain, state)
    if mud:
        return "lock", mud
    return "walk", None


def write_hold_snapshot(screen: AnsiScreen, path: Path | None = None) -> Path | None:
    """Write the frozen 80×25 glyphs (CP437→UTF-8, same as display) for a grab."""
    dest = path or HOLD_SNAPSHOT
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(screen.text() + "\n", encoding="utf-8")
    except OSError:
        return None
    return dest


def copy_hold_clipboard(text: str) -> bool:
    """Put the held screen on the desktop clipboard (Ctrl+V)."""
    global _CLIP_ROOT
    try:
        if _CLIP_ROOT is None:
            root = tkinter.Tk()
            root.withdraw()
            _CLIP_ROOT = root
        _CLIP_ROOT.clipboard_clear()
        _CLIP_ROOT.clipboard_append(text)
        _CLIP_ROOT.update_idletasks()
        _CLIP_ROOT.update()
    except tkinter.TclError:
        return False
    return True


def pump_clipboard() -> None:
    """Serve X11 paste requests while F10 hold owns the clipboard."""
    if _CLIP_ROOT is None:
        return
    try:
        _CLIP_ROOT.update_idletasks()
        _CLIP_ROOT.update()
    except tkinter.TclError:
        return


def realm_fkey_tip(*, hunting: bool, ambush: str = "", join: str = "") -> str:
    """Current state / current action — not 'press to…'."""
    bits = [fkey_label(n) for n in range(1, 7)]
    bits.append(fkey_label(7, active=hunting))
    if ambush:
        bits.append(fkey_label(8, word=ambush))
    if join:
        bits.append(fkey_label(9, word=join))

    def pack(*, short_f3: bool, show_hold: bool) -> str:
        out = [fkey_label(3, short=short_f3) if i == 2 else bit for i, bit in enumerate(bits)]
        if show_hold:
            out.append(fkey_label(10))
        return " ".join(out)

    mid = ""
    for short_f3, show_hold in ((False, True), (True, True), (False, False), (True, False)):
        cand = pack(short_f3=short_f3, show_hold=show_hold)
        if len(cand) <= 80:
            mid = cand
            break
    if not mid:
        mid = pack(short_f3=True, show_hold=False)[:80]
    if hunting:
        extra = f"{mid}  letter takes over"
        return extra if len(extra) <= 80 else mid
    for prefix in ("> bar  Enter  ", "> bar  "):
        text = f"{prefix}{mid}"
        if len(text) <= 80:
            return text
    return mid[:80]


def maybe_auto_party(
    state: WorldState,
    brain: Brain,
    send,
    *,
    invited: bool,
    followed: bool,
    they_followed: bool = False,
    frozen: bool = False,
) -> None:
    """Join / backrank from an invite even when the hunter is stopped."""
    if frozen or not state.in_realm:
        return
    if they_followed:
        brain._sync_party(state)
    if invited:
        brain.on_invite(state, send)
    if followed:
        brain.on_follow(state, send)


def maybe_ask_exp(
    state: WorldState, send, *, pending: bool = False, frozen: bool = False
) -> bool:
    """Send `exp` once per gap, like health. `needs_exp` blocks a second send."""
    if frozen or pending or not state.in_realm or state.in_combat:
        return False
    if not state.needs_exp():
        return False
    state.exp_asked = True
    send("exp")
    return True


def handle_client_line(cmd: str, brain: Brain, state: WorldState) -> tuple[str, str | None]:
    """> bar client commands. Returns (kind, mud_line_or_none)."""
    raw = cmd.strip()
    low = raw.lower()
    if low == "hunt":
        brain.toggle_hunt()
        return "hunt", None
    if low == "stop":
        brain.takeover()
        return "stop", None
    if low in {"train", "go train"}:
        if state.at_trainer():
            brain.cancel_train()
            return "train", "train"
        brain.request_train()
        return "train", None
    if raw:
        brain.cancel_train()
        return "game", raw
    return "enter", ""


def character_label(player: dict[str, object]) -> str:
    """Window-title name: given, else username. Account klymacks stays lowercase."""
    given = str(player.get("given") or "").strip()
    username = str(player.get("username") or "").strip()
    who = given or username
    if who.lower() == "klymacks":
        return "klymacks"
    return who or "klymacks"


def window_title(player: dict[str, object]) -> str:
    return f"Finn's Realm — {character_label(player)}"


def osc_set_title(title: str) -> bytes:
    """OSC 0 icon+window title. Never emit an empty name."""
    text = (title or "").strip()
    if not text:
        return b""
    return f"\x1b]0;{text}\x07".encode()


# Bright red / yellow — VGA SGR the 80×25 HUD uses for hits. Footer bg is #0b0e0c.
HP_RED_SGR = "\x1b[1;31m"
HP_YELLOW_SGR = "\x1b[1;33m"
CHROME_BODY_SGR = "\x1b[1;37m"
HP_LOW_RATIO = 0.25
_SGR_RE = re.compile(r"\x1b\[[0-9;]*m")
_HP_SEGMENT_RE = re.compile(r"HP -?\d+(?:/\d+)?")
_TRAIN_SEGMENT_RE = re.compile(r"TRAIN \d+%")


def visible_len(text: str) -> int:
    return len(_SGR_RE.sub("", text))


def pad_visible(text: str, width: int) -> str:
    extra = width - visible_len(text)
    if extra <= 0:
        return text
    return text + (" " * extra)


def hp_chrome_sgr(state: WorldState) -> str:
    """Red if hp < 0; yellow if 0 ≤ hp and hp/max < 25%. Else chrome fg."""
    if state.hp is None:
        return ""
    if state.hp < 0:
        return HP_RED_SGR
    ratio = state.hp_ratio()
    if ratio is not None and ratio < HP_LOW_RATIO:
        return HP_YELLOW_SGR
    return ""


def color_footer_hp(plain: str, state: WorldState) -> str:
    """Color only the leading HP segment. MA and the rest stay chrome fg."""
    sgr = hp_chrome_sgr(state)
    if not sgr:
        return plain
    matched = _HP_SEGMENT_RE.match(plain)
    if not matched:
        return plain
    return f"{sgr}{matched.group(0)}{CHROME_BODY_SGR}{plain[matched.end():]}"


def color_footer_train(plain: str, state: WorldState) -> str:
    """Yellow TRAIN when there is enough exp to walk to the guild."""
    if not state.can_train():
        return plain
    matched = _TRAIN_SEGMENT_RE.search(plain)
    if not matched:
        return plain
    return (
        f"{plain[: matched.start()]}{HP_YELLOW_SGR}{matched.group(0)}"
        f"{CHROME_BODY_SGR}{plain[matched.end() :]}"
    )


def chrome(
    term_rows: int,
    screen: AnsiScreen,
    hint: str,
    host: str,
    state: WorldState,
    brain: Brain,
    typed: str = "",
    wm_title: str = "",
    held: bool = False,
    hold_copied: bool = False,
    sheet_lock: bool = False,
) -> bytes:
    prefix = osc_set_title(wm_title)
    if term_rows < ROWS + 3:
        return prefix
    rule = "─" * 80
    title = " FINN'S REALM"
    frozen = form_frozen(screen, sheet_lock)
    tag = fkey_label(10, held=held)
    if frozen:
        sheet_tag = fkey_label(11, held=True)
        tag = f"{sheet_tag}  {tag}" if held else sheet_tag
    elif state.can_train():
        ready = fkey_label(11)
        tag = f"{ready}  {tag}" if held else ready
    right = status_line(screen, host)
    right = f"{right}  {tag}" if right else tag
    head = f"{title}{right.rjust(80 - len(title))}"[:80]
    if state.in_realm and state.hp is not None:
        vitals = state.hp_label()
        progress = state.exp_label()
        if progress:
            vitals = f"{vitals}  {progress}" if vitals else progress
        room = (state.room or "the realm")[:22]
        ambush = brain.stealth_label()
        shown = brain.next_action
        if ambush and ambush not in shown:
            shown = f"{shown}  {ambush}"
        rest = f"  {room}  {brain.mode}  next: {shown}"
        budget = max(0, 80 - len(vitals))
        plain = (vitals + rest[:budget])[:80]
        body = pad_visible(color_footer_hp(plain, state), 80)
        body = color_footer_train(body, state)
    else:
        body = hint[:80]
    if screen.looks_like_creation():
        foot = ""
        for y in range(screen.rows - 1, 17, -1):
            line = screen.line(y).strip()
            if line and "────" not in line and "____" not in line:
                foot = line
                break
        tip = (foot or "Type on the form. F11 live after SAVE. Last name required.")[:80]
    elif frozen:
        tip = fkey_label(11, style="sheet_tip")
    elif held:
        tip = fkey_label(10, style="hold_tip", copied=hold_copied)
    elif brain.bail:
        tip = "friendly fire   logged off   a human has to be at the keys"
    elif state.in_realm:
        tip = realm_fkey_tip(
            hunting=brain.hunting(),
            ambush=brain.stealth_label(),
            join=brain.join_label(),
        )
    elif "[MAJORMUD]" in screen.text():
        tip = "E enter the realm   H help   X leave MajorMUD"
    else:
        tip = f"{fkey_label(1)} in the realm   Ctrl-C hangs up"
    out = bytearray(prefix)
    out += b"\x1b[0m"
    out += f"\x1b[26;1H\x1b[0;36m{rule}\x1b[0m".encode()
    out += f"\x1b[27;1H\x1b[1;36m{head:<80}\x1b[0m".encode()
    out += f"\x1b[28;1H\x1b[1;37m{pad_visible(body, 80)}\x1b[0m".encode()
    if use_local_input(screen, state, sheet_lock):
        shown = realm_bar_text(typed)
        cmd = f"> {shown}"
        out += f"\x1b[29;1H\x1b[1;32m{cmd:<80}\x1b[0m".encode()
        out += f"\x1b[30;1H\x1b[0;36m{tip:<80}\x1b[0m".encode()
        col = min(80, 3 + len(shown))
        out += f"\x1b[29;{col}H\x1b[?25h".encode()
        return bytes(out)
    out += f"\x1b[29;1H\x1b[0;36m{tip:<80}\x1b[0m".encode()
    if term_rows >= ROWS + CHROME:
        out += f"\x1b[30;1H\x1b[0;36m{rule}\x1b[0m".encode()
    out += f"\x1b[{screen.cy + 1};{screen.cx + 1}H\x1b[?25h".encode()
    return bytes(out)


def help_overlay() -> bytes:
    rows = (
        "letters     type on the > bar, always visible",
        "Enter       send the line (sheet: next field)",
        "Up Down     move fields (Tab is Down)",
        "Space       cycle hair, eyes, SAVE / EXIT",
        *(fkey_label(n, style="help") for n in range(1, 12)),
        "F2-F6       peek - hunter stays on",
        "hunt stop   same as F7, not sent to the game",
        "train       same as F11 — freezes status on the sheet",
        "Ctrl-C      hang up",
        "Names go on the bar under the form, then Enter",
        "At [HP=] type reroll to throw the character.",
    )
    inner = max(len(row) for row in rows)
    width = inner + 6
    title_pad = max(1, width - 9)
    box = [f"┌─ keys {'─' * title_pad}┐"]
    for row in rows:
        box.append(f"│  {row.ljust(inner)}  │")
    box.append(f"└{'─' * (width - 2)}┘")
    out = bytearray(b"\x1b[0;1;36m")
    top = 5
    left = 13
    for i, line in enumerate(box):
        out += f"\x1b[{top + i};{left}H{line}".encode()
    out += b"\x1b[0m"
    return bytes(out)


def _more_stdin(stdin: int, pending: bytearray, wait: float) -> None:
    if stdin < 0:
        return
    more, _, _ = select.select([stdin], [], [], wait)
    if more:
        pending.extend(os.read(stdin, 64))


def read_key(stdin: int, pending: bytearray) -> bytes | None:
    _more_stdin(stdin, pending, 0)
    if not pending:
        return None

    first = pending[0]
    if first == 0x8F:
        if len(pending) < 2:
            _more_stdin(stdin, pending, 0.04)
        if len(pending) < 2:
            return None
        code = pending[1]
        del pending[:2]
        return _SS3_FKEYS.get(code, b"")
    if first != 0x1B:
        return bytes([pending.pop(0)])

    if len(pending) == 1:
        _more_stdin(stdin, pending, 0.04)
        if len(pending) == 1:
            pending.pop(0)
            return b""

    if len(pending) >= 2 and pending[1] == ord("O"):
        if len(pending) < 3:
            _more_stdin(stdin, pending, 0.04)
        if len(pending) < 3:
            return None
        code = pending[2]
        del pending[:3]
        if code in (65, 66):
            return bytes((0x1B, ord("["), code))
        return _SS3_FKEYS.get(code, b"")

    if len(pending) >= 3 and pending[1] == ord("[") and pending[2] == ord("["):
        if len(pending) < 4:
            _more_stdin(stdin, pending, 0.04)
        if len(pending) < 4:
            return None
        code = pending[3]
        del pending[:4]
        return _LINUX_FKEYS.get(code, b"")

    if len(pending) >= 2 and pending[1] == ord("["):
        if len(pending) >= 3 and pending[2] == ord("O"):
            if len(pending) < 4:
                _more_stdin(stdin, pending, 0.04)
            if len(pending) < 4:
                return None
            code = pending[3]
            del pending[:4]
            return _SS3_FKEYS.get(code, b"")
        end = None
        for i in range(2, len(pending)):
            if 0x40 <= pending[i] <= 0x7E:
                end = i
                break
        if end is None:
            return None
        final = pending[end]
        seq = bytes(pending[: end + 1])
        del pending[: end + 1]
        mapped = _CSI_SS3.get(seq)
        if mapped:
            return mapped
        if seq.endswith(b"~") and seq.startswith(b"\x1b["):
            num = seq[2:-1].split(b";", 1)[0]
            if num.isdigit():
                fkey = _CSI_FKEYS.get(int(num))
                if fkey:
                    return fkey
        if len(seq) == 3 and final in (65, 66):
            return seq
        return b""

    pending.pop(0)
    return b""


def run(host: str, port: int, player: dict[str, object], auto: bool) -> int:
    wm_title = window_title(player)
    cols, rows = shutil.get_terminal_size(fallback=(80, 24))
    if cols < 80 or rows < 24:
        sys.stderr.write(
            f"This terminal is {cols}x{rows}. The character sheet needs 80x25.\n"
            f"Use the window from ./scripts/play-window.sh.\n\n"
        )
        sys.stderr.flush()

    screen = AnsiScreen()
    paint_splash(screen, host, port)
    pacer = KeyPacer()
    play = bool(player.get("auto_play", True)) and auto
    clear_lock()
    pilot = Autopilot(player, play) if auto else None
    transcript = Transcript()
    state = WorldState()
    brain = Brain(
        allowed=is_loopback_host(host),
        pvp=bool(player.get("pvp")),
        me=" ".join(
            str(player.get(key) or "")
            for key in ("username", "given", "character")
        ),
        alts=board_aka(player),
        party_leader=str(player.get("party_leader") or ""),
        rank=str(player.get("rank") or ""),
        klass=str(player.get("class") or ""),
        spell_list=player.get("spells"),
        ambush=str(player.get("ambush") or "stand"),
        stealth=str(player.get("stealth") or ""),
        atlas=Atlas(DEFAULT_PATH),
        auto_join=bool(player.get("auto_join", True)),
    )
    typed = ""
    logoff_at = 0.0
    stdin = sys.stdin.fileno()
    old = termios.tcgetattr(stdin)
    pending = bytearray()
    help_on = False
    hold_on = False
    hold_copied = False
    paint_hold_once = False
    sheet_lock = False
    sheet_prompt: int | None = None
    last_stamp: tuple[object, ...] = ()
    if auto:
        hint = "signing in..."
    else:
        hint = "Type your username."
    seen_rows: set[str] = set()

    def apply_payload(payload: bytes) -> None:
        streamed: set[str] = set()
        saw_invite = False
        saw_follow = False
        saw_they_follow = False

        def take(ev: dict[str, object]) -> None:
            nonlocal saw_invite, saw_follow, saw_they_follow
            streamed.add(str(ev["kind"]))
            state.apply(ev)
            if ev.get("kind") == "invited" and not ev.get("by_me"):
                saw_invite = True
            elif ev.get("kind") == "following":
                saw_follow = True
            elif ev.get("kind") == "followed":
                saw_they_follow = True

        for line in transcript.feed(payload):
            for ev in parse_events(line):
                take(ev)
        for ev in events_from_payload(payload):
            take(ev)
        blob = screen.text()
        for ev in harvest_screen(blob, seen_rows):
            if ev.get("kind") == "experience" and "experience" in streamed:
                continue
            take(ev)
        state.empty_if_look_missed(streamed, blob)
        if "prompt" not in streamed and "[HP=" in blob:
            idx = blob.rfind("[HP=")
            for ev in parse_events(blob[idx : idx + 40].split("\n", 1)[0]):
                if ev.get("kind") == "prompt":
                    take(ev)
        maybe_auto_party(
            state,
            brain,
            pacer.push_text,
            invited=saw_invite,
            followed=saw_follow,
            they_followed=saw_they_follow,
            frozen=form_frozen(screen, sheet_lock),
        )

    def freeze_sheet(*, from_train: bool = False) -> None:
        nonlocal sheet_lock, sheet_prompt
        sheet_lock = True
        if from_train and sheet_prompt is None:
            sheet_prompt = state.prompt_seq

    def thaw_sheet() -> None:
        nonlocal sheet_lock, sheet_prompt
        sheet_lock = False
        sheet_prompt = None

    def on_bar() -> bool:
        return use_local_input(screen, state, sheet_lock)

    def brain_send(text: str) -> None:
        if text.strip().lower() == "train":
            freeze_sheet(from_train=True)
        pacer.push_text(text)

    try:
        tty.setraw(stdin)
        sys.stdout.buffer.write(b"\x1b[?7l\x1b[8;30;80t\x1b[2J\x1b[H")
        sys.stdout.buffer.write(osc_set_title(wm_title))
        sys.stdout.buffer.write(screen.render())
        sys.stdout.buffer.flush()

        sock = socket.create_connection((host, port), timeout=8)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setblocking(False)
        telnet = Telnet(sock)
        try:
            while True:
                timeout = 0.03 if pacer.pending() else (
                    0.4 if brain.hunting() and not form_frozen(screen, sheet_lock) else None
                )
                if _CLIP_ROOT is not None and timeout is None:
                    timeout = 0.25
                readable, _, _ = select.select([sock, stdin], [], [], timeout)
                if sock in readable:
                    try:
                        chunk = sock.recv(4096)
                    except BlockingIOError:
                        chunk = b""
                    if not chunk:
                        why = "disconnected"
                        if pilot is not None and pilot.phase == "blocked":
                            why = pilot.hint()
                        sys.stdout.write(f"\r\n[{why}]\r\n")
                        sys.stdout.flush()
                        if not state.in_realm:
                            _hold_error()
                        return 0
                    payload = telnet.feed(chunk)
                    was_sheet = screen.looks_like_creation()
                    screen.feed(payload)
                    try:
                        apply_payload(payload)
                    except Exception:
                        tb = traceback.format_exc()
                        log = ROOT / "data" / "client-crash.log"
                        try:
                            log.parent.mkdir(parents=True, exist_ok=True)
                            log.write_text(tb, encoding="utf-8")
                        except OSError:
                            pass
                        hint = "parse error — see data/client-crash.log"
                    now_sheet = screen.looks_like_creation()
                    if now_sheet:
                        freeze_sheet()
                    elif was_sheet:
                        thaw_sheet()
                        screen.leave_form()
                    elif (
                        sheet_lock
                        and sheet_prompt is not None
                        and state.prompt_seq > sheet_prompt
                    ):
                        thaw_sheet()
                        screen.leave_form()
                    if pilot is not None:
                        pilot.tick(screen.text(), pacer)
                        hint = pilot.hint()

                if stdin in readable:
                    while True:
                        key = read_key(stdin, pending)
                        if key is None:
                            break
                        if key == b"":
                            continue
                        if key in (b"\x03", b"\x1d"):
                            return 0
                        if is_locked():
                            clear_lock()
                            hint = "your keyboard"
                        special = handle_special_key(
                            key,
                            brain,
                            pacer,
                            in_realm=on_bar(),
                            state=state,
                        )
                        if special in ("hunt", "panic", "ambush", "join"):
                            hint = f"{brain.mode}  ·  {brain.next_action}"
                            continue
                        if special == "peek":
                            continue
                        if special == "sheet":
                            action, mud = toggle_sheet(
                                brain,
                                state,
                                locked=sheet_lock,
                                on_form=screen.looks_like_creation(),
                            )
                            if action == "lock":
                                freeze_sheet(from_train=bool(mud))
                                if mud:
                                    pacer.push_text(mud)
                                hint = "sheet"
                            elif action == "walk":
                                if brain._with_leader(state):
                                    hint = "following — leader owns movement"
                                else:
                                    hint = f"{brain.mode}  ·  train"
                            else:
                                thaw_sheet()
                                hint = "your keyboard"
                            continue
                        if special == "hold":
                            hold_on = not hold_on
                            if hold_on:
                                write_hold_snapshot(screen)
                                hold_copied = copy_hold_clipboard(screen.text())
                                paint_hold_once = True
                            else:
                                hold_copied = False
                                last_stamp = ()
                            continue
                        if key == b"\x7f":
                            key = b"\x08"
                        if key == b"\t":
                            key = KEY_DN
                        if key in (b"\n", b"\r"):
                            key = b"\r"
                        in_play = pilot is None or pilot.phase == "play"
                        if in_play and brain.hunting() and on_bar():
                            brain.takeover()
                            pacer.clear()
                            hint = "your keyboard"
                        if in_play and on_bar():
                            if key == b"\r":
                                cmd = typed.strip()
                                typed = ""
                                kind, mud = handle_client_line(cmd, brain, state)
                                if kind in ("hunt", "stop"):
                                    hint = f"{brain.mode}  ·  {brain.next_action}"
                                    continue
                                if kind == "train":
                                    if mud:
                                        freeze_sheet(from_train=True)
                                        pacer.push_text(mud)
                                    elif brain._with_leader(state):
                                        hint = "following — leader owns movement"
                                    else:
                                        hint = f"{brain.mode}  ·  train"
                                    continue
                                if mud:
                                    pacer.push_text(mud)
                                else:
                                    pacer.push(b"\r")
                                continue
                            if key == b"\x08":
                                typed = typed[:-1]
                                continue
                            if len(key) == 1 and 32 <= key[0] < 127:
                                if len(typed) < 76:
                                    typed += chr(key[0])
                                continue
                            continue
                        pacer.push(key)

                if not on_bar():
                    typed = ""

                in_play = pilot is None or pilot.phase == "play"
                frozen = form_frozen(screen, sheet_lock)
                if in_play and not typed and not frozen:
                    brain.tick(state, brain_send, pacer.pending(), pacer.clear)
                    if (
                        not pacer.pending()
                        and not brain.bail
                        and maybe_ask_exp(
                            state, brain_send, pending=False, frozen=frozen
                        )
                    ):
                        pass
                    if brain.bail and not logoff_at:
                        hint = f"friendly fire — {brain.bail}"
                        pacer.clear()
                        pacer.push_text("quit")
                        logoff_at = time.monotonic() + 1.5
                    elif state.in_realm and not brain.bail:
                        hint = f"{brain.mode}  ·  {brain.next_action}"
                    if logoff_at and time.monotonic() >= logoff_at and not pacer.pending():
                        return 0

                now = time.monotonic()
                outgoing = pacer.take(now)
                if outgoing is not None:
                    telnet.send(outgoing)

                stamp = (
                    screen.generation,
                    brain.mode,
                    brain.next_action,
                    brain.stealth,
                    brain.auto_join,
                    state.hp,
                    state.exp,
                    state.exp_pct,
                    state.exp_stale,
                    state.room,
                    brain._want_train,
                    hint,
                    help_on,
                    hold_on,
                    hold_copied,
                    typed,
                    on_bar(),
                    sheet_lock,
                )
                # HOLD: live AnsiScreen still feeds; stdout stays put.
                # Hunt keeps ticking. Unhold paints latest.
                pump_clipboard()
                if hold_on and not paint_hold_once:
                    continue
                if paint_hold_once or stamp != last_stamp:
                    last_stamp = stamp
                    paint_hold_once = False
                    _, term_rows = shutil.get_terminal_size(fallback=(80, rows))
                    bar = chrome(
                        term_rows,
                        screen,
                        hint,
                        host,
                        state,
                        brain,
                        typed,
                        wm_title=wm_title,
                        held=hold_on,
                        hold_copied=hold_copied,
                        sheet_lock=sheet_lock,
                    )
                    frame = screen.render() + bar
                    if help_on:
                        frame += help_overlay()
                    sys.stdout.buffer.write(frame)
                    sys.stdout.buffer.flush()
        finally:
            sock.close()
    finally:
        termios.tcsetattr(stdin, termios.TCSADRAIN, old)
    return 0


def main() -> int:
    player = load_player(ROOT / "config" / "player.json")
    parser = argparse.ArgumentParser(
        description="Local telnet client for Finn's Realm (loopback only)"
    )
    parser.add_argument("host", nargs="?", default="127.0.0.1")
    parser.add_argument("port", nargs="?", type=int, default=2323)
    parser.add_argument("--user", default=str(player["username"]))
    parser.add_argument("--password", default=str(player["password"]))
    parser.add_argument("--sysop", action="store_true", help="log in as sysop / sysop")
    parser.add_argument("--no-auto", action="store_true", help="type everything yourself")
    args = parser.parse_args()
    if args.sysop:
        sysop_path = ROOT / "config" / "sysop.json"
        player = load_player(sysop_path)
        player["username"] = "sysop"
        player["password"] = "sysop"
    else:
        player["username"] = args.user
        player["password"] = args.password
    auto = bool(player.get("auto_login", True)) and not args.no_auto
    if not is_loopback_host(args.host):
        print(
            "This client only opens local telnet "
            "(127.0.0.1 / localhost / ::1). Not a public BBS.",
            file=sys.stderr,
        )
        return 2
    if not sys.stdin.isatty():
        print("Need a real terminal.", file=sys.stderr)
        return 1
    try:
        return run(args.host, args.port, player, auto)
    except ConnectionRefusedError:
        print(f"Nothing listening on {args.host}:{args.port}. Try ./scripts/start.sh", file=sys.stderr)
        _hold_error()
        return 1
    except KeyboardInterrupt:
        return 0
    except Exception:
        tb = traceback.format_exc()
        log = ROOT / "data" / "client-crash.log"
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(tb, encoding="utf-8")
        except OSError:
            pass
        sys.stderr.write(tb)
        sys.stderr.write("\nClient crashed. Enter to close.\n")
        sys.stderr.flush()
        _hold_error()
        return 1


def _hold_error() -> None:
    if not sys.stdin.isatty():
        return
    try:
        sys.stdin.read(1)
    except Exception:
        time.sleep(20)


if __name__ == "__main__":
    raise SystemExit(main())
