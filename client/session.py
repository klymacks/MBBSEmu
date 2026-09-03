"""Headless telnet session for recording and verifying the hunter."""

from __future__ import annotations

import sys
import socket
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_SCRIPTS = str(ROOT / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import bbs_client
from client.localnet import require_loopback_host
from client.parse import events_from_payload, harvest_screen, parse_events
from client.state import WorldState
from client.transcript import Transcript


class Session:
    def __init__(self, host: str = "127.0.0.1", port: int = 2323) -> None:
        self.host = require_loopback_host(host)
        self.port = port
        self.sock = socket.create_connection((self.host, port), timeout=8)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.setblocking(False)
        self.telnet = bbs_client.Telnet(self.sock)
        self.screen = bbs_client.AnsiScreen()
        self.pacer = bbs_client.KeyPacer()
        self.transcript = Transcript()
        self.state = WorldState()
        self.seen_rows: set[str] = set()
        self.closed = False

    def close(self) -> None:
        if not self.closed:
            self.sock.close()
            self.closed = True

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def pump(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            now = time.monotonic()
            out = self.pacer.take(now)
            if out:
                self.telnet.send(out)
            try:
                chunk = self.sock.recv(4096)
            except BlockingIOError:
                time.sleep(0.03)
                continue
            if not chunk:
                return
            payload = self.telnet.feed(chunk)
            self.screen.feed(payload)
            streamed: set[str] = set()
            for line in self.transcript.feed(payload):
                for ev in parse_events(line):
                    streamed.add(str(ev["kind"]))
                    self.state.apply(ev)
            for ev in events_from_payload(payload):
                streamed.add(str(ev["kind"]))
                self.state.apply(ev)
            blob = self.screen.text()
            for ev in harvest_screen(blob, self.seen_rows):
                if ev.get("kind") == "experience" and "experience" in streamed:
                    continue
                self.state.apply(ev)
            self.state.empty_if_look_missed(streamed, blob)

    def text(self) -> str:
        return self.screen.text()

    def login(self, player: dict[str, object], play: bool = True) -> bool:
        pilot = bbs_client.Autopilot(player, play)
        for _ in range(900):
            self.pump(0.15)
            if "already logged in" in self.text().lower():
                return False
            pilot.tick(self.text(), self.pacer)
            if (
                pilot.phase == "play"
                and (self.state.in_realm or "[HP=" in self.text())
            ):
                self.pump(0.8)
                return True
        return self.state.in_realm or "[HP=" in self.text()

    def cmd(self, text: str, wait: float = 2.5) -> None:
        before = self.state.prompt_seq
        self.pacer.push_text(text)
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            self.pump(0.08)
            if self.state.prompt_seq > before and not self.pacer.pending():
                self.pump(0.2)
                return
        self.pump(0.2)


def load_player() -> dict[str, object]:
    return bbs_client.load_player(ROOT / "config" / "player.json")
