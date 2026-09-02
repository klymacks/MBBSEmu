#!/usr/bin/env python3
"""TDF splash previews E–AF. Preview only — does not touch the live client."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import COLS, HERE, ROWS, Grid, render_cp437, render_utf8

TDF_DIR = HERE / "tdf"
CHARLIST = (
    "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
)
MAGIC = b"\x13TheDraw FONTS file"

# letter, file stem, tdf, window title (look, not font filename)
SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("E", "E-ice-script-font", "bladex.tdf", "ice blades"),
    ("F", "F-thick-ice", "icex.tdf", "thick ice"),
    ("G", "G-drip-script", "font37.tdf", "drip script"),
    ("H", "H-vintage-chrome", "vintage.tdf", "vintage chrome"),
    ("I", "I-thin-outline", "outlinex.tdf", "thin outline"),
    ("J", "J-compact-ice", "icezonex.tdf", "compact ice"),
    ("K", "K-cyan-shards", "acheronx.tdf", "cyan shards"),
    ("L", "L-layered", "voices.tdf", "layered"),
    ("M", "M-broken-razors", "razor2.tdf", "broken razors"),
    ("N", "N-beast-script", "beast.tdf", "beast script"),
    ("O", "O-soft-chrome", "bansheex.tdf", "soft chrome"),
    ("P", "P-wild-fade", "wildchld.tdf", "wild fade"),
    ("Q", "Q-tile-chrome", "super.tdf", "tile chrome"),
    ("R", "R-crystal-fade", "crystalx.tdf", "crystal fade"),
    ("S", "S-small-tag", "juicex.tdf", "small tag"),
    ("T", "T-acrylic", "acrylicx.tdf", "acrylic"),
    ("U", "U-alchemy", "alchemyx.tdf", "alchemy"),
    ("V", "V-arcane-outline", "arcane.tdf", "arcane outline"),
)

# Closest remaining shard/taper fonts + Infinity ice field (wash + sparkles).
INFINITY_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("W", "W-shard-script", "font30.tdf", "shard script"),
    ("X", "X-jagged-overlap", "union2.tdf", "jagged overlap"),
    ("Y", "Y-weave-shards", "twoyears.tdf", "weave shards"),
    ("Z", "Z-ravaged-ice", "ravaged.tdf", "ravaged ice"),
    ("AA", "AA-ice-tapers", "font23.tdf", "ice tapers"),
    ("AB", "AB-round-ice", "font59x.tdf", "round ice"),
    ("AC", "AC-heaven-ice", "sheavenx.tdf", "heaven ice"),
    ("AD", "AD-iridium", "iridium.tdf", "iridium chrome"),
    ("AE", "AE-ice-rounds", "font38.tdf", "ice rounds"),
    ("AF", "AF-3d-ice", "asylumx.tdf", "3d ice"),
)


class Glyph:
    __slots__ = ("width", "height", "cells")

    def __init__(self, width: int, height: int, cells: list[tuple[str, int]]) -> None:
        self.width = width
        self.height = height
        self.cells = cells


class ColorFont:
    def __init__(self, name: str, spacing: int, glyphs: dict[str, Glyph]) -> None:
        self.name = name
        self.spacing = spacing
        self.glyphs = glyphs

    def lookup(self, ch: str) -> Glyph | None:
        return self.glyphs.get(ch)


def load_color_tdf(path: Path) -> ColorFont:
    data = path.read_bytes()
    if data[:19] != MAGIC:
        raise ValueError(f"not a TheDraw font: {path}")
    namelen = data[24]
    name = data[25 : 25 + namelen].decode("latin1", "replace").rstrip("\x00")
    fonttype = data[41]
    spacing = data[42]
    if fonttype != 2:
        raise ValueError(f"{path} is type {fonttype}, need color (2)")
    offsets = struct.unpack_from("<94H", data, 45)
    payload = data[233:]
    glyphs: dict[str, Glyph] = {}
    for i, ch in enumerate(CHARLIST):
        off = offsets[i]
        if off == 0xFFFF or off >= len(payload):
            continue
        glyphs[ch] = _read_glyph(payload, off)
    return ColorFont(name, spacing, glyphs)


def _read_glyph(payload: bytes, off: int) -> Glyph:
    width = payload[off]
    height = payload[off + 1]
    p = off + 2
    grid = [(" ", 0)] * (width * height)
    row = 0
    col = 0
    while p < len(payload) and payload[p] != 0:
        ch = payload[p]
        p += 1
        if ch == 0x0D:
            row += 1
            col = 0
            if row >= height:
                break
            continue
        if p >= len(payload):
            break
        color = payload[p]
        p += 1
        if ch < 0x20:
            ch = 0x20
        if 0 <= row < height and 0 <= col < width:
            grid[row * width + col] = (bytes([ch]).decode("cp437"), color)
        col += 1
    return Glyph(width, height, grid)


# TheDraw/CGA nibble order is not ANSI: BLK BLU GRN CYN RED MAG BRN GRY.
_TD_TO_ANSI = (0, 4, 2, 6, 1, 5, 3, 7)


def pack_color(color: int) -> tuple[int, int, bool]:
    fg16 = color & 0x0F
    bg = (color >> 4) & 0x07
    return (_TD_TO_ANSI[fg16 & 7], _TD_TO_ANSI[bg], fg16 >= 8)


def word_size(font: ColorFont, word: str, spacing: int) -> tuple[int, int]:
    present = [g for g in (font.lookup(ch) for ch in word) if g is not None]
    if not present:
        return 0, 0
    width = sum(g.width for g in present) + spacing * max(0, len(present) - 1)
    height = max(g.height for g in present)
    return width, height


def fit_spacing(font: ColorFont, words: tuple[str, ...]) -> int:
    for spacing in (font.spacing, 1, 0, -1, -2):
        if all(word_size(font, word, spacing)[0] <= COLS for word in words):
            return spacing
    return -2


def blit_tdf(
    g: Grid,
    y0: int,
    x0: int,
    font: ColorFont,
    word: str,
    spacing: int,
) -> None:
    x = x0
    for ch in word:
        gl = font.lookup(ch)
        if gl is None:
            continue
        for row in range(gl.height):
            for col in range(gl.width):
                mark, color = gl.cells[row * gl.width + col]
                if mark == " " and (color & 0x0F) == 0:
                    continue
                fg, bg, bold = pack_color(color)
                g.put(y0 + row, x + col, mark, fg, bg, bold, overlay=True)
        x += gl.width + spacing


def _layout(font: ColorFont) -> tuple[str, str, int, int, int, int, int, int, int]:
    finn = "FINN'S" if font.lookup("'") else "FINNS"
    realm = "REALM"
    spacing = fit_spacing(font, (finn, realm))
    fw, fh = word_size(font, finn, spacing)
    rw, rh = word_size(font, realm, spacing)
    y1 = 1 if fh + rh <= 20 else 0
    y2 = y1 + fh
    if y2 + rh > 22:
        y2 = max(0, 22 - rh)
    return finn, realm, spacing, fw, fh, rw, rh, y1, y2


def ice_wash(g: Grid, y: int, x: int, w: int, h: int) -> None:
    """Dark blue under-splash, Infinity-style. Drawn first so letters sit on top."""
    x0 = max(0, x - 2)
    x1 = min(COLS, x + w + 2)
    y0 = min(22, max(0, y + max(2, h // 3)))
    y1 = min(22, y + h + 2)
    mid = (x0 + x1) // 2
    for yy in range(y0, y1 + 1):
        t = (yy - y0) / max(1, y1 - y0)
        inset = int((x1 - x0) * t * 0.18)
        left, right = x0 + inset, x1 - inset
        for xx in range(left, right):
            edge = min(xx - left, right - 1 - xx)
            if g.buf[yy][xx].ch not in {" ", "░", "▒", "·"}:
                continue
            dist = abs(xx - mid) / max(1, (right - left) / 2)
            if t < 0.35 and edge > 3:
                ch, fg, bold = "▓", 4, True
            elif t < 0.65 or edge > 2:
                ch, fg, bold = "▒", 4, False
            else:
                ch, fg, bold = "░", 4, False
            if dist > 0.85:
                ch, bold = "░", False
            g.put(yy, xx, ch, fg, 0, bold, overlay=False)


def ice_sparkles(g: Grid) -> None:
    marks = (
        (0, 14, "·", 6, True),
        (0, 38, "▀", 6, True),
        (0, 62, "·", 6, True),
        (1, 8, "▄", 6, True),
        (2, 72, "·", 6, True),
        (10, 6, "·", 6, True),
        (11, 74, "▀", 6, True),
        (18, 70, "·", 6, True),
    )
    for y, x, ch, fg, bold in marks:
        if g.buf[y][x].ch == " ":
            g.put(y, x, ch, fg, 0, bold, overlay=False)


def paint_tdf(g: Grid, font: ColorFont) -> None:
    finn, realm, spacing, fw, fh, rw, rh, y1, y2 = _layout(font)
    blit_tdf(g, y1, max(0, (COLS - fw) // 2), font, finn, spacing)
    blit_tdf(g, y2, max(0, (COLS - rw) // 2), font, realm, spacing)
    g.center(23, "f i n n ' s     r e a l m", 6, bold=True)
    g.puts(24, 2, "klymacks", 7, bold=False)


def paint_infinity(g: Grid, font: ColorFont) -> None:
    finn, realm, spacing, fw, fh, rw, rh, y1, y2 = _layout(font)
    x1 = max(0, (COLS - fw) // 2)
    x2 = max(0, (COLS - rw) // 2)
    ice_wash(g, y1, x1, fw, fh)
    ice_wash(g, y2, x2, rw, rh)
    blit_tdf(g, y1, x1, font, finn, spacing)
    blit_tdf(g, y2, x2, font, realm, spacing)
    ice_sparkles(g)
    g.center(23, "f i n n ' s     r e a l m", 6, bold=True)
    g.puts(24, 2, "klymacks", 7, bold=False)


def write_stem(stem: str, g: Grid) -> None:
    (HERE / f"{stem}.utf8.ans").write_bytes(render_utf8(g))
    (HERE / f"{stem}.ans").write_bytes(render_cp437(g))
    (HERE / f"{stem}.txt").write_text(g.text() + "\n", encoding="utf-8")


def _emit(letter: str, stem: str, tdf_name: str, look: str, painter) -> None:
    font = load_color_tdf(TDF_DIR / tdf_name)
    g = Grid()
    painter(g, font)
    write_stem(stem, g)
    finn, _realm, spacing, fw, fh, rw, rh, _y1, _y2 = _layout(font)
    print(f"{letter} {look:16} {stem}  {fw}x{fh}+{rw}x{rh} sp={spacing}")


def main() -> None:
    for letter, stem, tdf_name, look in SPECS:
        _emit(letter, stem, tdf_name, look, paint_tdf)
    for letter, stem, tdf_name, look in INFINITY_SPECS:
        _emit(letter, stem, tdf_name, look, paint_infinity)


if __name__ == "__main__":
    main()
