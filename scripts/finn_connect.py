#!/usr/bin/env python3
"""Finn's Realm raw-mode client.

Auto-logs in as sysop, enters MajorMUD, then hands you the keyboard.
Ctrl-] quits.
"""
from __future__ import annotations

import argparse
import re
import select
import socket
import sys
import termios
import time
import tty

HOST, PORT = "127.0.0.1", 2323
IAC, DO, DONT, WILL, WONT, SB, SE = 255, 253, 254, 251, 252, 250, 240
ANSI_RE = re.compile(rb"\x1b\[[0-9;?]*[A-Za-z]")


def filt(data: bytes, sock: socket.socket, pending: bytearray) -> bytes:
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
            opt = buf[i + 2]
            reply = WONT if c in (DO, DONT) else DONT
            try:
                sock.sendall(bytes([IAC, reply, opt]))
            except OSError:
                pass
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
        if c == IAC:
            out.append(IAC)
            i += 2
            continue
        i += 2
    del pending[:i]
    return bytes(out)


def visible(data: bytes) -> str:
    return ANSI_RE.sub(b"", data).decode("latin1", "replace").lower()


def wait_for(
    sock: socket.socket,
    pending: bytearray,
    needles: list[str],
    timeout: float,
) -> str:
    hay = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        remain = max(0.05, deadline - time.time())
        ready, _, _ = select.select([sock], [], [], min(0.3, remain))
        if sock not in ready:
            continue
        try:
            data = sock.recv(4096)
        except (BlockingIOError, TimeoutError):
            continue
        if not data:
            break
        out = filt(data, sock, pending)
        sys.stdout.buffer.write(out)
        sys.stdout.buffer.flush()
        hay += visible(out)
        if any(n in hay for n in needles):
            return hay
    return hay


def send_line(sock: socket.socket, text: str) -> None:
    sock.sendall(text.encode("ascii") + b"\r")


def auto_login(sock: socket.socket, pending: bytearray, user: str, password: str) -> None:
    """BBS login → MajorMUD → Enter the Realm, then optional first-time creation."""
    sock.setblocking(False)
    wait_for(sock, pending, ["username:"], 8)
    send_line(sock, user)
    hay = wait_for(sock, pending, ["password:", "already logged"], 8)
    if "already logged" in hay:
        return
    send_line(sock, password)
    hay = wait_for(sock, pending, ["make your selection", "already logged"], 10)
    if "already logged" in hay:
        return
    send_line(sock, "M")
    wait_for(sock, pending, ["[majormud]", "enter the realm", "make your selection"], 10)
    send_line(sock, "E")
    hay = wait_for(
        sock,
        pending,
        ["choose a race", "race:", "which character", "enter your name", "[hp=", "the realm"],
        6,
    )
    if "choose a race" in hay or "race:" in hay:
        send_line(sock, "1")
        wait_for(sock, pending, ["class", "choose a class"], 8)
        send_line(sock, "1")
        wait_for(sock, pending, ["lawful", "alignment"], 8)
        send_line(sock, "Y")
        wait_for(sock, pending, ["save your character", "exit", "character"], 6)


def interactive(sock: socket.socket, pending: bytearray) -> None:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        sock.setblocking(False)
        while True:
            ready, _, _ = select.select([sock, sys.stdin], [], [])
            if sock in ready:
                try:
                    data = sock.recv(4096)
                except BlockingIOError:
                    continue
                if not data:
                    break
                sys.stdout.buffer.write(filt(data, sock, pending))
                sys.stdout.buffer.flush()
            if sys.stdin in ready:
                ch = sys.stdin.buffer.read1(1)
                if not ch or ch == b"\x1d":
                    break
                sock.sendall(ch)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main() -> int:
    parser = argparse.ArgumentParser(description="Connect to Finn's Realm")
    parser.add_argument("--sysop", action="store_true", help="auto-login as sysop (default)")
    parser.add_argument("--user", default="sysop", help="BBS account (default: sysop)")
    parser.add_argument("--password", default="sysop", help="BBS password")
    parser.add_argument("--no-login", action="store_true", help="skip auto-login")
    args = parser.parse_args()
    user = "sysop" if args.sysop else args.user
    password = args.password if not args.sysop else "sysop"

    try:
        sock = socket.create_connection((HOST, PORT), timeout=8)
    except OSError as exc:
        print(f"Can't reach the board on {HOST}:{PORT}: {exc}")
        input("Enter to close")
        return 1
    sock.settimeout(None)
    pending = bytearray()
    try:
        if not args.no_login:
            auto_login(sock, pending, user, password)
        interactive(sock, pending)
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
