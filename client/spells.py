"""MajorMUD spells. Paladin starts with a couple; the shop sells more."""

from __future__ import annotations

# One cast per combat round. 1.11p is about eight seconds; spam just fizzles.
ROUND = 8.0

# kind: heal = self/friend, harm = combat target, buff = self (luck). mana is the 1.11p cost.
# level is the 1.11p character level to cast (spells.jsonl). Scrolls can be bought earlier.
SPELLBOOK = {
    "minor healing": {"kind": "heal", "mana": 2, "short": "mihe", "level": 1},
    "major healing": {"kind": "heal", "mana": 6, "short": "mahe", "level": 8},
    "harm": {"kind": "harm", "mana": 1, "short": "harm", "level": 1},
    "bless": {"kind": "buff", "mana": 2, "short": "bles", "level": 2},
}

# Priest-1 at creation. Other classes buy a scroll at the Newhaven spell shop
# (Dathalar, north of Narrow Path) and `read` it to memorize.
CLASS_SPELLS = {
    "paladin": ("minor healing", "harm", "bless"),
    "cleric": ("minor healing", "harm"),
    "priest": ("minor healing", "harm"),
    "warrior": (),
    "witchunter": (),
    "ninja": (),
}

# Shop item names. Harm's scroll is "cause harm", not "harm".
SCROLLS = {
    "minor healing": "scroll of minor healing",
    "harm": "scroll of cause harm",
    "bless": "scroll of bless",
    "major healing": "scroll of major healing",
}

_SHOP_FIRST = ("minor healing", "harm", "bless")


def normalize_spell_list(raw: object) -> list[str]:
    if isinstance(raw, (list, tuple)):
        return [str(item).strip().lower() for item in raw if str(item).strip()]
    return [part.strip().lower() for part in str(raw or "").split(",") if part.strip()]


def known_spells(klass: str, listed: object = None) -> list[str]:
    if listed is None:
        return list(CLASS_SPELLS.get(klass.strip().lower(), ()))
    return normalize_spell_list(listed)


def info(name: str) -> dict[str, object] | None:
    return SPELLBOOK.get(name.strip().lower())


def of_kind(names: list[str], kind: str) -> str:
    for name in names:
        spell = info(name)
        if spell and spell["kind"] == kind:
            return name
    return ""


def shop_spells(klass: str, listed: object = None) -> list[str]:
    """Spells this class can buy. Minor healing first, then harm, bless."""
    names = [name for name in known_spells(klass, listed) if name in SCROLLS]
    rank = {name: i for i, name in enumerate(_SHOP_FIRST)}
    names.sort(key=lambda name: (rank.get(name, len(_SHOP_FIRST)), name))
    return names


def scroll_name(spell: str) -> str:
    low = spell.strip().lower()
    return SCROLLS.get(low, f"scroll of {low}")


def buy_name(spell: str, alt: bool = False) -> str:
    low = spell.strip().lower()
    if alt:
        return low
    return scroll_name(low)


def read_command(spell: str) -> str:
    return f"read {scroll_name(spell)}"


def min_level(name: str) -> int:
    """Character level needed to `cast`. Scrolls can be bought and read sooner."""
    spell = info(name)
    if not spell:
        return 1
    raw = spell.get("level")
    if raw is None:
        return 1
    return int(raw)


def can_cast(name: str, level: int | None) -> bool:
    if level is None:
        return False
    return int(level) >= min_level(name)


def have_scroll(items: list[str], spell: str) -> bool:
    """True if `i` extras/inventory already has this spell's scroll."""
    want = scroll_name(spell)
    short = spell.strip().lower()
    for raw in items:
        low = raw.strip().lower()
        if not low:
            continue
        if want in low:
            return True
        if "scroll" in low and short in low:
            return True
    return False


def have_known(items: list[str], spell: str) -> bool:
    """True if `i` / known-spell text already lists this memorized spell."""
    short = spell.strip().lower()
    if not short:
        return False
    for raw in items:
        low = raw.strip().lower()
        if not low or "scroll" in low:
            continue
        if low == short or low.startswith(f"{short},") or low.startswith(f"{short} "):
            return True
        parts = [part.strip() for part in low.replace(";", ",").split(",")]
        if short in parts:
            return True
    return False


def command(name: str, target: str = "") -> str:
    line = f"cast {name.strip().lower()}"
    who = target.strip()
    if who:
        line = f"{line} {who}"
    return line


def cost(name: str) -> int:
    spell = info(name)
    if not spell:
        return 1
    return int(spell["mana"])
