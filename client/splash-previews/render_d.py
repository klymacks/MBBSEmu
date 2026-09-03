#!/usr/bin/env python3
"""Option D: ice-script Finn's Realm. Preview only — does not touch the live client."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import HERE, Grid, render_cp437, render_utf8

# Ice-script ink. W/w chrome, blue wash, cyan sparkle. Not TheDraw blocks.
CHROME = {
    "W": ("█", 7, True),
    "w": ("█", 7, False),
    "B": ("▓", 7, False),
    "C": ("▒", 7, False),
    "D": ("░", 7, False),
    "P": ("▀", 7, True),
    "E": ("▄", 7, True),
    "p": ("▀", 7, False),
    "e": ("▄", 7, False),
    "/": ("▌", 7, True),
    "\\": ("▐", 7, True),
}
WASH = {
    "U": ("█", 4, True),
    "u": ("█", 4, False),
    "V": ("▓", 4, False),
    "v": ("▒", 4, False),
    "n": ("░", 4, False),
    "E": ("▄", 4, True),
    "e": ("▄", 4, False),
    "P": ("▀", 4, True),
    "p": ("▀", 4, False),
}
SPARK = {
    "*": ("·", 6, True),
    "+": ("▀", 6, True),
    "x": ("▄", 6, True),
    "o": ("█", 6, True),
}
GOLD = {
    "Z": ("▀", 3, True),
    "z": ("·", 3, True),
}


def stamp(g: Grid, y: int, x: int, lines: tuple[str, ...], table: dict[str, tuple[str, int, bool]]) -> None:
    for dy, line in enumerate(lines):
        for dx, ch in enumerate(line):
            if ch in table:
                glyph, fg, bold = table[ch]
                g.put(y + dy, x + dx, glyph, fg, 0, bold)


def paint_d_ice_script(g: Grid) -> None:
    # Dark blue ice-wash under both words — infinity-style under-splash.
    wash = (
        "      nvvVVvvn              nvvn         nvVVVvn                            ",
        "    nvVVVVVVVVvn         nvVVVVVvn     vVVVVVVVVvn                          ",
        "   vVVVuuuuuVVVVVn   nvvVVVuuuVVVVVvvvVVVuuuuVVVVVn                         ",
        "  nVVVvn   nVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVvn  nVVn                         ",
        "   nn        nVVVVVVVVVVVVVVVVVVVVVVVVvn       nv                           ",
        "               nvVVVVVVVVVVVVVVVvn      n                                   ",
        "                 nn  nvVVVn   nn          n                                 ",
    )
    stamp(g, 8, 3, wash, WASH)
    for x, h in ((18, 3), (41, 4), (62, 2)):
        for i in range(h):
            ch = "u" if i == 0 else ("V" if i < h - 1 else "n")
            stamp(g, 14 + i, x, (ch,), WASH)

    # FINN'S — pointed overlapping shards.
    f = (
        "      EWWWWWP",
        "    EWWWWBB  ",
        "   WWWC    + ",
        "   WW        ",
        "   WW EWWWP  ",
        "   WWB  D    ",
        "   WW        ",
        "   WC        ",
        "   P         ",
    )
    i_let = (
        " EWP ",
        " WWWB",
        "  WW ",
        "  WW ",
        "  WW ",
        "  WW ",
        " EWW ",
        " D D ",
        "     ",
    )
    n = (
        "WW    EWP",
        "WWB   WW ",
        "WW W W WW",
        "WW  W  WW",
        "WW W W WW",
        "WWW   WW ",
        "WW    WW ",
        "e      e ",
        "         ",
    )
    apos = (
        "WP",
        "C ",
        "  ",
    )
    s = (
        "  EWWWWP",
        " WWC    ",
        "  WWBD  ",
        "    CWW ",
        "      WW",
        " EWWWWP ",
        " D      ",
        "        ",
        "        ",
    )
    stamp(g, 1, 4, f, CHROME)
    stamp(g, 1, 16, i_let, CHROME)
    stamp(g, 1, 21, n, CHROME)
    stamp(g, 1, 30, n, CHROME)
    stamp(g, 1, 41, apos, CHROME)
    stamp(g, 1, 44, s, CHROME)

    # REALM — same script, lower, in the wash, slight right kick.
    r = (
        " EWWWWP ",
        "WW   WWB",
        "WW  WW  ",
        "WWWWBD  ",
        "WW WWB  ",
        "WW  WWW ",
        "WW   WWB",
        "e     P ",
    )
    e = (
        " EWWWWWP",
        " WW     ",
        " WWWWB  ",
        " WW     ",
        " WWWWWWP",
        " e      ",
        "        ",
        "        ",
    )
    a = (
        "   WW   ",
        "  WWWW  ",
        " WW  WW ",
        "WWWWWWWW",
        "WW    WW",
        "WW    WW",
        "e      e",
        "        ",
    )
    ell = (
        "WW      ",
        "WW      ",
        "WW      ",
        "WW      ",
        "WW      ",
        "WWWWWWP ",
        "e       ",
        "        ",
    )
    m = (
        "WW    WW",
        "WWW  WWW",
        "WW WW WW",
        "WW  W  WW",
        "WW     WW",
        "WW     WW",
        "e       e",
        "         ",
    )
    stamp(g, 11, 8, r, CHROME)
    stamp(g, 11, 17, e, CHROME)
    stamp(g, 11, 27, a, CHROME)
    stamp(g, 11, 37, ell, CHROME)
    stamp(g, 11, 46, m, CHROME)
    stamp(g, 12, 56, ("Z",), GOLD)

    sparkles = (
        (0, 12, "+"),
        (0, 26, "*"),
        (0, 48, "o"),
        (1, 19, "*"),
        (2, 40, "+"),
        (10, 10, "x"),
        (10, 52, "*"),
        (11, 32, "+"),
        (18, 64, "*"),
    )
    for y, x, ch in sparkles:
        stamp(g, y, x, (ch,), SPARK)

    g.center(21, "f i n n ' s     r e a l m", 6, bold=True)
    g.puts(23, 2, "klymacks", 7, bold=False)
    g.puts(23, 68, "ice script", 4, bold=False)


def main() -> None:
    g = Grid()
    paint_d_ice_script(g)
    stem = "D-ice-script"
    (HERE / f"{stem}.utf8.ans").write_bytes(render_utf8(g))
    (HERE / f"{stem}.ans").write_bytes(render_cp437(g))
    (HERE / f"{stem}.txt").write_text(g.text() + "\n", encoding="utf-8")
    print(g.text())
    print(f"wrote {stem}  ({g.text().count('█')} blocks)")


if __name__ == "__main__":
    main()
