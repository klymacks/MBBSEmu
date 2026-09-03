"""Leftover lock file from older clients. New windows clear it and never write it."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCKOUT = ROOT / "config" / "pvp_lockout"


def is_locked() -> bool:
    return LOCKOUT.is_file()


def set_lock(reason: str) -> None:
    LOCKOUT.write_text(reason.strip() + "\n", encoding="utf-8")


def clear_lock() -> None:
    if LOCKOUT.is_file():
        LOCKOUT.unlink()


def lock_reason() -> str:
    if not LOCKOUT.is_file():
        return ""
    return LOCKOUT.read_text(encoding="utf-8").strip()
