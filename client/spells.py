"""MajorMUD spells. Paladin starts with a couple; the shop sells more."""

from __future__ import annotations

# One cast per combat round. 1.11p is about eight seconds; spam just fizzles.
ROUND = 8.0

# kind: heal = self/friend, harm = combat target, buff = self (luck). mana is the 1.11p cost.
SPELLBOOK = {
    "minor healing": {"kind": "heal", "mana": 2, "short": "mihe"},
    "major healing": {"kind": "heal", "mana": 6, "short": "mahe"},
    "harm": {"kind": "harm", "mana": 1, "short": "harm"},
    "bless": {"kind": "buff", "mana": 2, "short": "bles"},
}

# Priest-1 at creation. Other classes learn more; buy those at the spell shop.
CLASS_SPELLS = {
    "paladin": ("minor healing", "harm", "bless"),
    "cleric": ("minor healing", "harm"),
    "priest": ("minor healing", "harm"),
    "warrior": (),
    "witchunter": (),
    "ninja": (),
}


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
