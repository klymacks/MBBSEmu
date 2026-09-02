#!/usr/bin/env python3
"""Standalone Finn's Realm ANSI splash previews. Does not touch the live client."""

from __future__ import annotations

from pathlib import Path

COLS, ROWS = 80, 25
HERE = Path(__file__).resolve().parent

# TheDraw-style 5-row stems. No slant, no drips.
FONT: dict[str, tuple[str, ...]] = {
    "F": (
        "███████",
        "██     ",
        "█████  ",
        "██     ",
        "██     ",
    ),
    "I": (
        "█████",
        " ███ ",
        " ███ ",
        " ███ ",
        "█████",
    ),
    "N": (
        "██    ██",
        "███   ██",
        "██ ██ ██",
        "██   ███",
        "██    ██",
    ),
    "'": (
        "██",
        "▀ ",
        "  ",
        "  ",
        "  ",
    ),
    "S": (
        " █████",
        "██    ",
        " ████ ",
        "    ██",
        "█████ ",
    ),
    "R": (
        "██████ ",
        "██   ██",
        "██████ ",
        "██  ██ ",
        "██   ██",
    ),
    "E": (
        "██████",
        "██    ",
        "█████ ",
        "██    ",
        "██████",
    ),
    "A": (
        " ████ ",
        "██  ██",
        "██████",
        "██  ██",
        "██  ██",
    ),
    "L": (
        "██    ",
        "██    ",
        "██    ",
        "██    ",
        "██████",
    ),
    "M": (
        "██    ██",
        "███  ███",
        "██ ██ ██",
        "██    ██",
        "██    ██",
    ),
    " ": (
        "  ",
        "  ",
        "  ",
        "  ",
        "  ",
    ),
}

GAP = 1
DEPTH = 2


class Cell:
    __slots__ = ("ch", "fg", "bg", "bold")

    def __init__(self, ch: str = " ", fg: int = 7, bg: int = 0, bold: bool = False) -> None:
        self.ch = ch
        self.fg = fg
        self.bg = bg
        self.bold = bold


class Grid:
    def __init__(self) -> None:
        self.buf = [[Cell() for _ in range(COLS)] for _ in range(ROWS)]

    def put(
        self,
        y: int,
        x: int,
        ch: str,
        fg: int = 7,
        bg: int = 0,
        bold: bool = False,
        *,
        overlay: bool = True,
    ) -> None:
        if y < 0 or y >= ROWS or x < 0 or x >= COLS or ch == "":
            return
        if not overlay and self.buf[y][x].ch not in {" ", "░", "▒", "·"}:
            return
        self.buf[y][x] = Cell(ch, fg, bg, bold)

    def puts(self, y: int, x: int, text: str, fg: int, bg: int = 0, bold: bool = False) -> None:
        for i, ch in enumerate(text):
            self.put(y, x + i, ch, fg, bg, bold)

    def center(self, y: int, text: str, fg: int, bg: int = 0, bold: bool = False) -> None:
        self.puts(y, max(0, (COLS - len(text)) // 2), text, fg, bg, bold)

    def line(self, y: int) -> str:
        return "".join(c.ch for c in self.buf[y])

    def text(self) -> str:
        return "\n".join(self.line(y) for y in range(ROWS))


def word_width(word: str) -> int:
    return sum(len(FONT[ch][0]) for ch in word) + GAP * max(0, len(word) - 1)


def blit_word(
    g: Grid,
    y: int,
    x: int,
    word: str,
    palette: tuple[tuple[int, bool], ...],
    shadow: tuple[int, bool],
    fill: str = "█",
) -> None:
    glyphs: list[list[tuple[int, int, str, int]]] = []
    cursor = x
    for glyph in word:
        rows = FONT[glyph]
        width = len(rows[0])
        marks: list[tuple[int, int, str, int]] = []
        for row, line in enumerate(rows):
            for col, ch in enumerate(line):
                if ch == " ":
                    continue
                marks.append((cursor + col, y + row, ch, row))
        glyphs.append(marks)
        cursor += width + GAP
    all_ink = {(px, py) for marks in glyphs for px, py, _ch, _row in marks}
    for marks in glyphs:
        if not marks:
            continue
        right = max(px for px, _py, _ch, _row in marks)
        floor = max(py for _px, py, _ch, _row in marks)
        for px, py, _ch, _row in marks:
            if px >= right:
                for d in range(1, DEPTH + 1):
                    if (px + d, py) not in all_ink:
                        g.put(py, px + d, "▓", shadow[0], 0, shadow[1], overlay=False)
            if py == floor:
                for d in range(1, DEPTH + 1):
                    if (px, py + d) not in all_ink:
                        g.put(py + d, px, "▓", shadow[0], 0, shadow[1], overlay=False)
            if px >= right and py == floor:
                for d in range(1, DEPTH + 1):
                    if (px + d, py + d) not in all_ink:
                        g.put(py + d, px + d, "▓", shadow[0], 0, shadow[1], overlay=False)
    for marks in glyphs:
        for px, py, ch, row in marks:
            fg, bold = palette[min(row, len(palette) - 1)]
            mark = ch if ch in "▄▀" else fill
            g.put(py, px, mark, fg, 0, bold, overlay=True)
            if row == 0 and ch == "█":
                g.put(py - 1, px, "▀", palette[0][0], 0, True, overlay=False)


def fade_bar(g: Grid, y: int, hues: tuple[tuple[int, bool], ...], cut: str = "") -> None:
    for x in range(COLS):
        edge = min(x, COLS - 1 - x)
        if edge < 5:
            ch = "░"
        elif edge < 10:
            ch = "▒"
        elif edge < 16:
            ch = "▓"
        else:
            ch = "█"
        fg, bold = hues[(x * len(hues)) // COLS]
        g.put(y, x, ch, fg, 0, bold)
    if cut:
        label = f" {cut} "
        x0 = (COLS - len(label)) // 2
        for i, ch in enumerate(label):
            g.put(y, x0 + i, ch, 0, hues[len(hues) // 2][0], True)


def metal_rule(g: Grid, y: int, fg: int, bold: bool = False) -> None:
    g.puts(y, 0, "─" * COLS, fg, 0, bold)


def paint_a_ice(g: Grid) -> None:
    """Classic iCE chrome: cyan / white / ice-blue metal."""
    ice = ((7, True), (6, True), (6, True), (6, False), (4, True))
    shadow = (4, False)
    fade_bar(g, 0, ((4, False), (6, False), (6, True), (7, True), (6, True), (4, True)))
    g.center(1, "·  FINN'S REALM  ·  local 1.11p  ·", 6, bold=True)
    finn, realm = "FINN'S", "REALM"
    blit_word(g, 3, (COLS - word_width(finn)) // 2, finn, ice, shadow)
    blit_word(g, 10, (COLS - word_width(realm)) // 2, realm, ice, shadow)
    fade_bar(g, 17, ((4, False), (6, False), (6, True), (7, True), (6, True), (4, True)))
    g.center(19, "MAJOR MUD  1.11p                    chrome / ice", 6)
    g.puts(23, 2, "klymacks", 6, bold=True)
    g.puts(23, 68, "80x25 ANS", 4)


def paint_b_acid(g: Grid) -> None:
    """ACiD fire / gold: yellow-red 3D on black."""
    fire = ((7, True), (3, True), (3, True), (1, True), (1, False))
    shadow = (1, False)
    fade_bar(g, 0, ((1, False), (1, True), (3, True), (7, True), (3, True), (1, True)))
    g.center(1, "·  FINN'S REALM  ·  the gold pack", 3, bold=True)
    finn, realm = "FINN'S", "REALM"
    blit_word(g, 3, (COLS - word_width(finn)) // 2, finn, fire, shadow)
    blit_word(g, 10, (COLS - word_width(realm)) // 2 + 2, realm, fire, shadow)
    fade_bar(g, 17, ((1, False), (1, True), (3, True), (7, True), (3, True), (1, True)))
    g.center(19, "1.11p LOCAL", 3, bold=True)
    g.puts(23, 2, "klymacks", 3, bold=True)
    g.puts(23, 66, "ACID / FIRE", 1, bold=True)


def paint_c_sauce(g: Grid) -> None:
    """Dark DOS / SAUCE pack header: grey metal, one amber accent."""
    steel = ((7, True), (7, True), (7, False), (7, False), (7, False))
    shadow = (7, False)
    g.puts(0, 0, "█" + "▀" * 78 + "█", 7, 0, True)
    g.put(1, 0, "█", 7, 0, True)
    g.put(1, 79, "█", 7, 0, True)
    g.puts(1, 2, "FINN'S REALM", 3, 0, True)
    g.puts(1, 16, "·", 7)
    g.puts(1, 18, "MajorMUD 1.11p local BBS", 7)
    g.puts(1, 58, "SAUCE / 80x25", 7, bold=True)
    g.puts(2, 0, "█" + "▄" * 78 + "█", 7, 0, True)
    metal_rule(g, 3, 3, True)
    finn, realm = "FINN'S", "REALM"
    blit_word(g, 5, (COLS - word_width(finn)) // 2, finn, steel, shadow, fill="█")
    blit_word(g, 12, (COLS - word_width(realm)) // 2, realm, steel, shadow, fill="█")
    metal_rule(g, 19, 3, True)
    g.center(21, "released for the board  ·  klymacks", 7)
    g.puts(23, 2, "klymacks", 3, bold=True)
    g.puts(23, 55, "DOS VGA  ·  file_id", 7)


def sgr(cell: Cell) -> bytes:
    parts = ["0"]
    if cell.bold:
        parts.append("1")
    parts.append(str(30 + cell.fg))
    parts.append(str(40 + cell.bg))
    return f"\x1b[{';'.join(parts)}m".encode()


def render_utf8(g: Grid) -> bytes:
    out = bytearray(b"\x1b[2J\x1b[H\x1b[?7l")
    prev: tuple[int, int, bool] | None = None
    for y in range(ROWS):
        out += f"\x1b[{y + 1};1H".encode()
        for cell in g.buf[y]:
            key = (cell.fg, cell.bg, cell.bold)
            if key != prev:
                out += sgr(cell)
                prev = key
            out += cell.ch.encode("utf-8", "replace")
        out += b"\x1b[K"
    out += b"\x1b[0m\x1b[25;1H"
    return bytes(out)


def render_cp437(g: Grid) -> bytes:
    out = bytearray()
    prev: tuple[int, int, bool] | None = None
    for y in range(ROWS):
        out += f"\x1b[{y + 1};1H".encode()
        for cell in g.buf[y]:
            key = (cell.fg, cell.bg, cell.bold)
            if key != prev:
                out += sgr(cell)
                prev = key
            out += cell.ch.encode("cp437", "replace")
        out += b"\x1b[K"
    out += b"\x1b[0m"
    return bytes(out)


SPECS = (
    ("A-ice-chrome", "A  iCE chrome", paint_a_ice),
    ("B-acid-fire", "B  ACiD fire", paint_b_acid),
    ("C-sauce-dos", "C  SAUCE / DOS", paint_c_sauce),
)


def main() -> None:
    HERE.mkdir(parents=True, exist_ok=True)
    for stem, _title, paint in SPECS:
        g = Grid()
        paint(g)
        (HERE / f"{stem}.utf8.ans").write_bytes(render_utf8(g))
        (HERE / f"{stem}.ans").write_bytes(render_cp437(g))
        (HERE / f"{stem}.txt").write_text(g.text() + "\n", encoding="utf-8")
        print(f"wrote {stem}  ({g.text().count('█')} blocks)")


if __name__ == "__main__":
    main()
