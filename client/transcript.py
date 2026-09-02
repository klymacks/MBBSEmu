"""Line buffer of telnet payload with CSI stripped."""

from __future__ import annotations

from .parse import flushable, hold_inventory, strip_csi, unglue


class Transcript:
    def __init__(self) -> None:
        self._hold = ""
        self._inv_hold: list[str] = []
        self.lines: list[str] = []

    def feed(self, data: bytes) -> list[str]:
        if not data:
            return []
        text = self._hold + unglue(strip_csi(data))
        parts = text.split("\n")
        self._hold = parts[-1]
        fresh = [_apply_bs(p.rstrip()) for p in parts[:-1] if p.strip()]
        hold = self._hold.strip()
        if flushable(hold):
            fresh.append(_apply_bs(hold))
            self._hold = ""
        emit, self._inv_hold = hold_inventory(self._inv_hold, fresh)
        self.lines.extend(emit)
        return emit


def _apply_bs(text: str) -> str:
    out: list[str] = []
    for ch in text:
        if ch == "\b":
            if out:
                out.pop()
        else:
            out.append(ch)
    return "".join(out)
