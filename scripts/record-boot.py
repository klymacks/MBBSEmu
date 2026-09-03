#!/usr/bin/env python3
"""Read the latest MBBSEmu boot from data/mbbsemu.log and record it.

  python3 scripts/record-boot.py
  python3 scripts/record-boot.py /path/to/repo

Writes data/last-boot.json and appends data/boot-history.jsonl.
Prints one line: users / DEMO / recovery.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if len(sys.argv) > 1:
    ROOT = Path(sys.argv[1]).resolve()

DATA = ROOT / "data"
LOG = DATA / "mbbsemu.log"
LAST = DATA / "last-boot.json"
HISTORY = DATA / "boot-history.jsonl"

USERS_RE = re.compile(r"MajorMUD - (\d+) users")
DEMO_RE = re.compile(r"DEMO MODE ACTIVATED")
RECOVERY_RE = re.compile(r"Recovery Mode")


def latest_chunk(text: str) -> str:
    idx = text.rfind("Loading WCCMMUD")
    return text[idx:] if idx >= 0 else text[-8000:]


def parse(text: str) -> dict[str, object]:
    chunk = latest_chunk(text)
    users_match = USERS_RE.search(chunk)
    users = int(users_match.group(1)) if users_match else None
    demo = bool(DEMO_RE.search(chunk))
    recovery = bool(RECOVERY_RE.search(chunk))
    seats_ok = users is not None and users > 0
    return {
        "at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "users": users,
        "demo": demo,
        "recovery": recovery,
        "seats_ok": seats_ok,
    }


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    if not LOG.is_file():
        print("no mbbsemu.log yet")
        return 1
    raw = LOG.read_bytes().decode("utf-8", errors="replace")
    record = parse(raw)
    LAST.write_text(json.dumps(record, indent=2) + "\n")
    with HISTORY.open("a") as fh:
        fh.write(json.dumps(record) + "\n")
    users = record["users"]
    demo = "DEMO" if record["demo"] else "licensed"
    recov = " recovery" if record["recovery"] else ""
    print(f"boot: {users} users  {demo}{recov}")
    return 0 if record["seats_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
