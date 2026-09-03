"""Newhaven and Silvermere rooms from Finn's Realm (1.11p).

Village Entrance: south armour (Betram), north weapons, west to the path,
southeast to the forest path and boatman. Narrow Path: south general store,
north spell shop, west to the road. Narrow Road: down into the arena, north
guild, west healer.

Silvermere is the next town — skiff only. Do not walk the Paramud / cave-bear
overland. Newhaven Docks `borrow skiff` lands on the Pier; the same command
returns. Town Square `go manhole` is the sewer farm.

MegaMMUD v2.1 stock uses the same Newhaven graph (Town = Narrow Road, shops
Betram / Nathaniel / Dathalar / Rayth).
"""

from __future__ import annotations

import re

STARTER_WEAPON = "club"
STARTER_LIGHT = "torch"
LOOT = ("copper", "silver", "gold", "platinum")

# Harm (and most priest damage) is living-only. Oozes and undead ignore it.
UNLIVING = (
    "slime",
    "ooze",
    "jelly",
    "pudding",
    "skeleton",
    "zombie",
    "ghoul",
    "ghost",
    "wight",
    "wraith",
    "spectre",
    "specter",
    "lich",
    "undead",
    "golem",
)

LOPS = (
    "kobold",
    "rat",
    "snake",
    "goblin",
    "bat",
    "spider",
    "wolf",
    "orc",
    "skeleton",
    "gnoll",
    "hobgoblin",
    "bandit",
    "thug",
    "orcish",
    "filthbug",
    "slime",
    "carrion",
    "worm",
    "lashworm",
)

FRIENDLY = (
    "healer",
    "betram",
    "bertram",
    "corwyn",
    "nathaniel",
    "dathalar",
    "shopkeeper",
    "guard",
    "boatman",
    "helfgrim",
    "skali",
    "sentara",
)
HOME_ACCOUNTS = ("klymacks", "sysop", "guest", "matt")
_BAD_MOB = (
    "lunge",
    "damage",
    "whap",
    "you say",
    "experience",
    "combat",
    "attack ",
)
# Also-here flavor only — never part of the swing. Keep species words
# (giant, acid, carrion) so `giant rat` / `acid slime` stay two-word names.
_SKIP_WORDS = {
    "a",
    "an",
    "the",
    "nasty",
    "small",
    "large",
    "huge",
    "tiny",
    "young",
    "old",
    "big",
    "little",
    "weak",
    "fierce",
    "angry",
    "mean",
    "fat",
    "thin",
    "lean",
    "scrawny",
    "stout",
    "hungry",
    "starving",
    "rabid",
    "wild",
    "sickly",
}

ARMOUR_ITEMS = (
    "padded vest",
    "padded helm",
    "padded pants",
    "padded boots",
    "padded gloves",
)
STARTER_GEAR = (*ARMOUR_ITEMS, STARTER_WEAPON, STARTER_LIGHT)
_INV_SLOT_RE = re.compile(r"\s*\(([^)]*)\)\s*$")
_INV_ARTICLE_RE = re.compile(r"^(?:a|an|the)\s+", re.IGNORECASE)
_INV_CARRY_RE = re.compile(r"^you are carrying:?\s*", re.IGNORECASE)
_INV_QTY_RE = re.compile(r"^(\d+)\s+")
# MajorMUD `i` wraps at 80 cols. Slots mark worn copies; bare names are extras.
_INV_SLOT_NAME_RE = re.compile(
    r"\((?:torso|head|legs|feet|hands|arms|neck|back|waist|wrist|finger|"
    r"ears?|face|eyes?|weapon hand|off-?hand|shield)\)",
    re.I,
)


def inventory_entries(raw: str) -> list[tuple[str, bool]]:
    """Split a carrying line into (name, worn). `(Torso)` / `(Head)` / etc = worn."""
    text = _INV_CARRY_RE.sub("", raw.strip())
    found: list[tuple[str, bool]] = []
    for part in text.split(","):
        slot = _INV_SLOT_RE.search(part)
        name = _INV_SLOT_RE.sub("", part).strip()
        name = _INV_ARTICLE_RE.sub("", name).strip().lower()
        qty = 1
        counted = _INV_QTY_RE.match(name)
        if counted:
            qty = max(1, int(counted.group(1)))
            name = name[counted.end() :].strip()
        if name and name not in {"you are carrying", "nothing"}:
            worn = bool(slot and (slot.group(1) or "").strip())
            copies = 1 if worn else qty
            found.extend((name, worn) for _ in range(copies))
    return found


def inventory_names(raw: str) -> list[str]:
    """Split a carrying line into item names (slots stripped)."""
    return [name for name, _worn in inventory_entries(raw)]


def inventory_extras(raw: str) -> list[str]:
    """Unequipped copies — bare names on the `i` line, no (Slot)."""
    return [name for name, worn in inventory_entries(raw) if not worn]


def inventory_worn(raw: str) -> list[str]:
    return [name for name, worn in inventory_entries(raw) if worn]


def has_inv_slot(raw: str) -> bool:
    """True when a carrying line names a worn slot like (Torso) or (Head)."""
    return bool(_INV_SLOT_NAME_RE.search(raw))


def _starter_match(low: str, name: str) -> bool:
    return low == name or low.endswith(name) or name in low.split(",")


def extra_starter(
    items: list[str],
    extras: list[str] | None = None,
    skip: set[str] | None = None,
    worn: list[str] | None = None,
) -> str | None:
    """One spare starter item to sell. Last `i` extras win; stacks stay sellable."""
    banned = {n.lower() for n in skip} if skip else set()
    worn_set = {n.strip().lower() for n in worn} if worn else set()
    counts: dict[str, int] = {}
    for raw in items:
        low = raw.strip().lower()
        for name in STARTER_GEAR:
            if name in banned:
                continue
            if _starter_match(low, name):
                counts[name] = counts.get(name, 0) + 1
                break
    if extras:
        for raw in extras:
            low = raw.strip().lower()
            for name in STARTER_GEAR:
                if name in banned:
                    continue
                if not _starter_match(low, name):
                    continue
                # Just-bought and not yet worn is not an extra to dump.
                if worn is None or name in worn_set or counts.get(name, 0) >= 2:
                    return name
    for name, n in counts.items():
        if n >= 2:
            return name
    return None


def is_weapon_shop(room: str) -> bool:
    low = room.lower()
    return "weapon" in low or "nathaniel" in low


def is_armour_shop(room: str) -> bool:
    low = room.lower()
    return "armour" in low or "armor" in low or "betram" in low or "bertram" in low


def is_general_store(room: str) -> bool:
    low = room.lower()
    return "general store" in low or "general" in low


def is_spell_shop(room: str) -> bool:
    """Newhaven Spell Shop / Dathalar, north of Narrow Path."""
    low = room.lower()
    return "spell" in low or "dathalar" in low


SHOP_WORDS = (
    "shop",
    "store",
    "armour",
    "armor",
    "weapon",
    "general",
    "betram",
    "bertram",
    "nathaniel",
    "dathalar",
    "helfgrim",
    "skali",
    "sentara",
)

ARENA_WORDS = ("arena", "pit", "dungeon", "sewer", "slum")
SPECIAL_STEPS = frozenset({"borrow skiff", "search down", "go manhole"})
FARM_DROPS = frozenset({"d", "go manhole"})
_SILVER_MARKS = (
    "town square",
    "guild street",
    "guild st.",
    "river st",
    "crown st",
    "westwall",
    "stone st",
    "temple",
    "pier",
    "sewer",
    "helfgrim",
    "skali",
    "sentara",
    "magic shoppe",
    "fountain",
    "mystic alley",
    "arena entrance",
)
_GIVEN_RE = re.compile(r"^[A-Z][a-z]{1,14}$")
_GLUE_GIVEN_RE = re.compile(r"^(.+?)([A-Z][a-z]{1,14})$")
_DIR_TOKENS = frozenset({"n", "s", "e", "w", "u", "d", "ne", "nw", "se", "sw"})
_DIR_LONG = frozenset(
    {
        "north",
        "south",
        "east",
        "west",
        "up",
        "down",
        "northeast",
        "northwest",
        "southeast",
        "southwest",
    }
)
_DIR_ALL = _DIR_TOKENS | _DIR_LONG
_DIR_PREFIXES = tuple(sorted(_DIR_ALL, key=len, reverse=True))
_LOOK_NOISE = frozenset({"also", "here", "obvious", "exits"})
# Leftover verb from `attack attack giant rat` (game eats `at` → `tack`,
# or `a` → `ttack`). `att` minus `a` is `tt` — that becomes spoken
# `att tt giant rat` if we swing it. `bs` / `at` are the same class.
_SWING_LEFTOVER = frozenset(
    {"attack", "ttack", "tack", "tt", "bs", "at", "att", "bash", "aa"}
)
_SWING_PREFIXES = tuple(sorted(_SWING_LEFTOVER, key=len, reverse=True))
_MOB_LEAD = frozenset({"giant", "acid"}) | _SKIP_WORDS | frozenset(LOPS)

# Kept for tests / docs. Brain walks by room name, not this list.
GEAR_COMMANDS = (
    "look",
    "e",
    "buy padded vest",
    "wear padded vest",
    "buy club",
    "wear club",
    "buy torch",
    "w",
    "d",
)


def is_home_account(name: str) -> bool:
    return name.strip().lower() in HOME_ACCOUNTS


def is_self(name: str, extra: set[str] | None = None) -> bool:
    tokens = [w.strip(".,!;:").lower() for w in name.split() if w.strip(".,!;:")]
    if not tokens:
        return False
    banned = set(HOME_ACCOUNTS)
    if extra:
        banned |= {x.lower() for x in extra}
    return any(token in banned for token in tokens)


def _bare_word(word: str) -> str:
    return word.lower().strip(".,!;:()[]")


def is_dir_token(word: str) -> bool:
    """n/s/e/w/u/d and long forms. Leftover exits, not part of a mob."""
    return _bare_word(word) in _DIR_ALL


def is_given_name(token: str, extra: set[str] | None = None) -> bool:
    """A PC given name: klymacks, Matt, Aelthas. Not The / giant / rat."""
    raw = token.strip(".,!;:")
    if not raw:
        return False
    low = raw.lower()
    if low in HOME_ACCOUNTS:
        return True
    if extra and low in {x.lower() for x in extra}:
        return True
    if is_dir_token(raw) or low in _LOOK_NOISE:
        return False
    if low in _SKIP_WORDS or low in FRIENDLY:
        return False
    if any(lop == low for lop in LOPS):
        return False
    return bool(_GIVEN_RE.match(raw))


def _name_needles(extra: set[str] | None = None) -> list[str]:
    names = list(HOME_ACCOUNTS)
    if extra:
        names.extend(extra)
    return sorted({n.lower() for n in names if len(n) >= 3}, key=len, reverse=True)


def _looks_like_mob_rest(rest: str) -> bool:
    low = rest.lower().lstrip("-/:;").strip(".,!;:")
    if not low:
        return False
    if low in _MOB_LEAD:
        return True
    return any(low.startswith(lop) for lop in LOPS)


def _split_dir_prefix(raw: str) -> list[str]:
    """drat / dgiant / downrat when CSI glued an exit onto the mob."""
    low = raw.lower()
    for pref in _DIR_PREFIXES:
        if len(raw) <= len(pref) or not low.startswith(pref):
            continue
        rest = raw[len(pref) :].lstrip("-/:;")
        if _looks_like_mob_rest(rest):
            return [raw[: len(pref)], rest]
    return [raw]


def _split_swing_prefix(raw: str) -> list[str]:
    """attackgiant / tackrat / attacktack when the verb mashed onto the mob.

    Never peel `at` off `acid` — that becomes `id slime`, and `a id slime` is speech.
    """
    low = raw.lower()
    if low == "acid" or low.startswith("acid"):
        return [raw]
    for pref in _SWING_PREFIXES:
        if len(raw) <= len(pref) or not low.startswith(pref):
            continue
        rest = raw[len(pref) :].lstrip("-/:;")
        if not rest:
            continue
        if _looks_like_mob_rest(rest) or is_swing_leftover(rest):
            return [raw[: len(pref)], rest]
        nested = _split_swing_prefix(rest)
        if len(nested) >= 2:
            return [raw[: len(pref)], *nested]
    return [raw]


def is_swing_leftover(word: str) -> bool:
    """`attack` / `tack` left on the aim — never part of a mob."""
    return _bare_word(word) in _SWING_LEFTOVER


def _is_noise_name(name: str) -> bool:
    tokens = [w for w in name.replace(":", " ").replace(".", " ").split() if w]
    if not tokens:
        return True
    return all(is_dir_token(w) or _bare_word(w) in _LOOK_NOISE for w in tokens)


def unglue_token(word: str, extra: set[str] | None = None) -> list[str]:
    """Split slimeKlymacks / ratmatt / drat when CSI ate a comma or exit."""
    raw = word.strip(".,!;:")
    if not raw:
        return []
    if is_dir_token(raw) or _bare_word(raw) in _LOOK_NOISE:
        return [raw]
    for sep in (".", ":"):
        if sep not in raw:
            continue
        bits = [b for b in raw.split(sep) if b]
        if len(bits) >= 2 and any(
            is_dir_token(b) or _bare_word(b) in _LOOK_NOISE for b in bits
        ):
            out: list[str] = []
            for bit in bits:
                out.extend(unglue_token(bit, extra))
            return out
    glued = _GLUE_GIVEN_RE.match(raw)
    if glued and is_given_name(glued.group(2), extra):
        left = glued.group(1)
        tail = [glued.group(2)]
        if left:
            return [*_unglue_left(left, extra), *tail]
        return tail
    return _unglue_left(raw, extra)


def _unglue_left(raw: str, extra: set[str] | None = None) -> list[str]:
    split = _split_dir_prefix(raw)
    if len(split) == 2:
        return [split[0], *unglue_token(split[1], extra)]
    split = _split_swing_prefix(raw)
    if len(split) == 2:
        return [split[0], *unglue_token(split[1], extra)]
    low = raw.lower()
    for needle in _name_needles(extra):
        if low.endswith(needle) and len(low) > len(needle):
            left = raw[: -len(needle)]
            if any(lop in left.lower() for lop in LOPS) or len(left) >= 3:
                return [left, raw[-len(needle) :]]
    return [raw]


def peel_presence(name: str, extra: set[str] | None = None) -> list[str]:
    """Split 'giant rat Klymacks' and 'slimeKlymacks' so we attack the rat."""
    words = name.split()
    if not words:
        return []
    chunks: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            cleaned = [
                w
                for w in buf
                if not is_dir_token(w)
                and _bare_word(w) not in _LOOK_NOISE
                and not is_swing_leftover(w)
            ]
            if cleaned:
                chunks.append(" ".join(cleaned))
            buf.clear()

    for word in words:
        for part in unglue_token(word, extra):
            if is_given_name(part, extra):
                flush()
                chunks.append(part)
            else:
                buf.append(part)
    flush()
    return chunks


def is_player(name: str) -> bool:
    """A PC: proper name, not a/an/the critter and not a known lop."""
    raw = name.strip()
    if not raw or len(raw) > 40:
        return False
    if is_dir_token(raw) or _is_noise_name(raw):
        return False
    low = raw.lower()
    if any(word in low for word in FRIENDLY):
        return False
    if any(word in low for word in _BAD_MOB):
        return False
    if any(lop in low for lop in LOPS):
        return False
    if low.startswith(("a ", "an ", "the ")):
        return False
    if any(word in _SKIP_WORDS - {"a", "an", "the"} for word in low.split()):
        return False
    return bool(raw)


def players_in(mobs: list[str], extra: set[str] | None = None) -> list[str]:
    found: list[str] = []
    for name in mobs:
        for piece in peel_presence(name, extra):
            if is_player(piece) or is_given_name(piece, extra) or is_home_account(piece):
                if piece not in found:
                    found.append(piece)
    return found


def _friendly_npc(piece: str) -> bool:
    """Corwyn, Betram, a town guard — named NPCs, not farm lops."""
    low = piece.lower().strip(".,!;:")
    if not low:
        return False
    if low in FRIENDLY:
        return True
    return any(word in FRIENDLY for word in low.split())


def occupants_in(mobs: list[str], extra: set[str] | None = None) -> list[str]:
    """PCs and named NPCs occupying the room. Sneak needs this empty."""
    found: list[str] = []
    for name in mobs:
        for piece in peel_presence(name, extra):
            if (
                is_given_name(piece, extra)
                or is_player(piece)
                or is_home_account(piece)
                or _friendly_npc(piece)
            ):
                if piece not in found:
                    found.append(piece)
    return found


def party_name(name: str, extra: set[str] | None = None) -> str:
    """Invite/join target: the toon, never a leftover exit or lop."""
    for piece in peel_presence(name, extra):
        if is_given_name(piece, extra) or is_player(piece) or is_home_account(piece):
            return piece
    raw = name.strip()
    if raw and (is_given_name(raw, extra) or is_player(raw) or is_home_account(raw)):
        return raw
    return ""


def is_living(name: str) -> bool:
    low = name.lower()
    return not any(word in low for word in UNLIVING)


def lop_in(mobs: list[str]) -> str | None:
    """Newest farm mob, as `attack_name` would swing it."""
    found = None
    for name in mobs:
        for piece in peel_presence(name):
            if is_given_name(piece) or is_player(piece):
                continue
            low = piece.lower()
            if any(word in low for word in FRIENDLY):
                continue
            if any(word in low for word in _BAD_MOB):
                continue
            if len(piece) > 40:
                continue
            if any(lop in low for lop in LOPS) or low.startswith(("a ", "an ", "the ")):
                found = attack_name(piece) or attack_name(name) or None
    return found


def living_lop(mobs: list[str]) -> str | None:
    """Newest farm mob that Harm can actually hit. Same name as `lop_in`."""
    found = None
    for name in mobs:
        live = lop_in([name])
        if live and is_living(live):
            found = live
    return found


def _repair_eaten_at(name: str) -> str:
    """`at acid` leftover is `id slime` — that is still the slime."""
    words = name.split()
    if len(words) >= 2 and words[0].lower() == "id":
        rest = " ".join(words[1:]).lower()
        if any(lop in rest for lop in LOPS):
            return "acid " + " ".join(words[1:])
    return name


def attack_name(name: str) -> str:
    """The swing name. Also-here, combat, leftover verb, adjective, exit, toon.

    One helper: `fat carrion beast` / `tack giant rat` / `nasty lashworm`
    become `carrion beast` / `giant rat` / `lashworm`. Everyone calls this.
    """
    pieces = peel_presence(name)
    creature = [p for p in pieces if not is_given_name(p) and not is_player(p)]
    blob = creature[0] if creature else name
    words = [
        w
        for w in blob.split()
        if _bare_word(w) not in _SKIP_WORDS
        and not is_dir_token(w)
        and _bare_word(w) not in _LOOK_NOISE
        and not is_swing_leftover(w)
        and not is_given_name(w)
    ]
    while words and is_swing_leftover(words[0]):
        words.pop(0)
    cleaned = " ".join(words).strip()
    if cleaned:
        return _repair_eaten_at(cleaned)
    if _is_noise_name(blob) or is_dir_token(blob):
        return ""
    if is_given_name(blob) or is_player(blob):
        return blob.strip()
    return ""


def attack_line(name: str = "") -> str:
    """Wire form for a visible swing.

    1.11p live: `att filthbug` engages. `k kobold thief` is spoken.
    `a carrion beast` is speech. `at acid slime` can become spoken `a id slime`.
    Paladin bash is `aa {aim}`, not this.
    """
    aim = attack_name(name) if name else ""
    if not aim:
        return "att"
    return f"att {aim}"


def has_toon(name: str, extra: set[str] | None = None) -> bool:
    low = name.lower()
    return any(needle in low for needle in _name_needles(extra))


def same_mob(a: str, b: str) -> bool:
    na, nb = attack_name(a).lower(), attack_name(b).lower()
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def without_dead(mobs: list[str], dead: str) -> list[str]:
    kept: list[str] = []
    removed = False
    for name in mobs:
        if not removed and same_mob(name, dead):
            removed = True
            continue
        kept.append(name)
    return kept


def coins_in(things: list[str]) -> list[str]:
    found: list[str] = []
    for item in things:
        low = item.lower()
        for coin in LOOT:
            if coin in low and coin not in found:
                found.append(coin)
    return found


def is_shop(room: str, mobs: list[str], flagged: bool) -> bool:
    if flagged:
        return True
    blob = " ".join([room, *mobs]).lower()
    return any(word in blob for word in SHOP_WORDS)


def is_special_step(step: str) -> bool:
    return step.strip().lower() in SPECIAL_STEPS


def is_farm_drop(step: str | None) -> bool:
    return bool(step) and step.strip().lower() in FARM_DROPS


def in_newhaven(room: str) -> bool:
    return "newhaven" in room.lower()


def in_silvermere(room: str) -> bool:
    low = room.lower()
    if in_newhaven(low):
        return False
    if "silvermere" in low:
        return True
    if low in {"docks", "general store"}:
        return True
    return any(mark in low for mark in _SILVER_MARKS)


def at_farm(room: str) -> bool:
    """Newhaven pit or Silvermere sewers — not the practice dummy."""
    low = room.lower()
    if "sewer" in low or "slum" in low:
        return True
    if "arena" in low and "entrance" not in low:
        return True
    return False


def at_quest_stop(room: str) -> bool:
    """Class-weapon walk ends at the graveyard, or Town Square if unmapped."""
    low = room.lower()
    return "graveyard" in low or "town square" in low


def is_dangerous(room: str) -> bool:
    low = room.lower()
    return any(word in low for word in ARENA_WORDS)


def gear_index_for_room(room: str) -> int:
    low = room.lower()
    if "arena" in low:
        return len(GEAR_COMMANDS)
    if "weapon shop" in low:
        return GEAR_COMMANDS.index("buy club")
    if "general store" in low:
        return GEAR_COMMANDS.index("buy torch")
    if "armour shop" in low or "armor shop" in low:
        return GEAR_COMMANDS.index("buy padded vest")
    return 0


def leave_dead_end(room: str, exits: list[str]) -> str | None:
    return step_toward_arena(room, exits)


def step_toward_store(room: str, exits: list[str] | None = None) -> str | None:
    """Narrow Road east to the path, south into the general store."""
    low = room.lower()
    step: str | None
    if "general" in low:
        step = None
    elif any(word in low for word in ARENA_WORDS):
        step = "u"
    elif "healer" in low:
        step = "e"
    elif is_trainer(low):
        step = "s"
    elif "narrow road" in low:
        step = "e"
    elif "narrow path" in low:
        step = "s"
    elif "village entrance" in low:
        step = "w"
    elif "weapon" in low or "nathaniel" in low:
        step = "s"
    elif "armour" in low or "armor" in low or "betram" in low or "bertram" in low:
        step = "n"
    elif "spell" in low:
        step = "s"
    else:
        step = None
    return _open_step(step, exits)


SPELL_SHOP_ROOMS = ("Newhaven, Spell Shop", "Dathalar")


def step_toward_spell_shop(room: str, exits: list[str] | None = None) -> str | None:
    """One step toward Newhaven Spell Shop (north of Narrow Path)."""
    low = room.lower()
    step: str | None
    if is_spell_shop(low):
        step = None
    elif any(word in low for word in ARENA_WORDS):
        step = "u"
    elif "healer" in low:
        step = "e"
    elif is_trainer(low):
        step = "s"
    elif "armour" in low or "armor" in low or "betram" in low or "bertram" in low:
        step = "n"
    elif "weapon" in low or "nathaniel" in low:
        step = "s"
    elif "general" in low:
        step = "n"
    elif "village entrance" in low:
        step = "w"
    elif "narrow path" in low:
        step = "n"
    elif "narrow road" in low:
        step = "e"
    else:
        step = None
    return _open_step(step, exits)


def is_trainer(room: str) -> bool:
    """Newhaven guild or a class training hall. Not Guild Street."""
    low = room.lower()
    if "training" in low:
        return True
    if "guild st" in low or "guild street" in low:
        return False
    return "guild" in low


def step_toward_guild(room: str, exits: list[str] | None = None) -> str | None:
    """One step toward the Newhaven guild (trainer), north of Narrow Road."""
    low = room.lower()
    step: str | None
    if is_trainer(low):
        step = None
    elif any(word in low for word in ARENA_WORDS):
        step = "u"
    elif "healer" in low:
        step = "e"
    elif "armour" in low or "armor" in low or "betram" in low or "bertram" in low:
        step = "n"
    elif "weapon" in low or "nathaniel" in low:
        step = "s"
    elif "general" in low:
        step = "n"
    elif "spell" in low:
        step = "s"
    elif "village entrance" in low:
        step = "w"
    elif "narrow path" in low:
        step = "w"
    elif "narrow road" in low:
        step = "n"
    else:
        step = None
    return _open_step(step, exits)


def step_toward_arena(room: str, exits: list[str]) -> str | None:
    """One step toward the local farm: Newhaven pit or Silvermere sewers."""
    if in_silvermere(room):
        return _step_toward_sewers(room, exits)
    low = room.lower()
    step: str | None
    if any(word in low for word in ARENA_WORDS):
        step = None
    elif "healer" in low:
        step = "e"
    elif is_trainer(low):
        step = "s"
    elif "armour" in low or "armor" in low or "betram" in low or "bertram" in low:
        step = "n"
    elif "weapon" in low or "nathaniel" in low:
        step = "s"
    elif "general" in low:
        step = "n"
    elif "spell" in low:
        step = "s"
    elif "village entrance" in low:
        step = "w"
    elif "forest path" in low:
        step = "nw"
    elif "docks" in low:
        step = "n"
    elif "narrow path" in low:
        step = "w"
    elif "narrow road" in low:
        step = "d"
    else:
        step = None
    return _open_step(step, exits)


def _step_toward_sewers(room: str, exits: list[str] | None) -> str | None:
    low = room.lower()
    if at_farm(low):
        return None
    if "town square" in low or "fountain" in low:
        return "go manhole"
    if "pier" in low:
        return _open_step("s", exits)
    if low == "docks" or (low.endswith("docks") and "newhaven" not in low):
        return _open_step("e", exits)
    if "guild st" in low and "river" in low:
        return _open_step("s", exits)
    if "northern end" in low:
        return _open_step("s", exits)
    if "southern end" in low:
        return _open_step("s", exits)
    if "temple hall" in low:
        return _open_step("e", exits)
    if "temple street" in low:
        return _open_step("e", exits)
    if "temple spell" in low:
        return _open_step("n", exits)
    if "temple healer" in low:
        return _open_step("s", exits)
    if "temple chapel" in low:
        return _open_step("e", exits)
    if "clerical" in low:
        return _open_step("s", exits)
    if "priestly" in low:
        return _open_step("n", exits)
    if "helfgrim" in low:
        return _open_step("e", exits)
    if "skali" in low:
        return _open_step("s", exits)
    if "sentara" in low:
        return _open_step("s", exits)
    if low == "general store":
        return _open_step("n", exits)
    if "magic shoppe" in low:
        return _open_step("n", exits)
    if "arena entrance" in low:
        return _open_step("s", exits)
    return None


def step_toward_silvermere(room: str, exits: list[str] | None = None) -> str | None:
    """Skiff to Silvermere. Never the cave-bear road."""
    if in_silvermere(room):
        return None
    low = room.lower()
    if "docks" in low:
        return "borrow skiff"
    if "forest path" in low:
        return _open_step("s", exits)
    if "village entrance" in low:
        return _open_step("se", exits)
    if any(word in low for word in ARENA_WORDS):
        return _open_step("u", exits)
    if "healer" in low:
        return _open_step("e", exits)
    if is_trainer(low):
        return _open_step("s", exits)
    if "armour" in low or "armor" in low or "betram" in low or "bertram" in low:
        return _open_step("n", exits)
    if "weapon" in low or "nathaniel" in low:
        return _open_step("s", exits)
    if "general" in low:
        return _open_step("n", exits)
    if "spell" in low:
        return _open_step("s", exits)
    if "narrow road" in low:
        return _open_step("e", exits)
    if "narrow path" in low:
        return _open_step("e", exits)
    return None


def _open_step(step: str | None, exits: list[str] | None) -> str | None:
    if not step:
        return None
    if is_special_step(step):
        return step
    if exits and step not in exits:
        return None
    return step
