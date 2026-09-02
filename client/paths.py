"""NewHaven and Silvermere rooms recorded from 1.11p + MegaMMUD stock paths.

Village Entrance: south armour (Betram), north weapons, west to the path,
southeast to the forest path and the Newhaven docks (`borrow skiff`).
Narrow Path: south general store, north spell shop, west to the road.
Narrow Road: down into the arena (filthbugs), north guild, west healer.

Silvermere hub is Town Square. `go manhole` drops into the sewers (the next
exp loop). Docks / Pier: `borrow skiff` (or `search down` then north) back to
Newhaven. Shops: Helfgrim, Skali, Sentara, Giovanni, Temple Spell Store.

MegaMMUD v2.1 Stock .mp files use the same graph. Do not import Paramud rooms.
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
    "giovanni",
    "helfgrim",
    "skali",
    "sentara",
    "aiken",
    "boatman",
    "priest",
    "bishop",
    "jael",
    "thuluk",
    "colin",
    "meia",
    "godfrey",
    "lionheart",
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
    return (
        "weapon" in low
        or "nathaniel" in low
        or "helfgrim" in low
        or "blades" in low
        or "sword shop" in low
    )


def is_armour_shop(room: str) -> bool:
    low = room.lower()
    return (
        "armour" in low
        or "armor" in low
        or "betram" in low
        or "bertram" in low
        or "skali" in low
        or "sentara" in low
        or "leather" in low
    )


def is_general_store(room: str) -> bool:
    low = room.lower()
    return "general store" in low or "giovanni" in low


def is_spell_shop(room: str) -> bool:
    """Newhaven Spell Shop / Dathalar, or Silvermere Temple / Magic Shoppe."""
    low = room.lower()
    return (
        "spell shop" in low
        or "spell store" in low
        or "dathalar" in low
        or "magic shoppe" in low
    )


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
    "giovanni",
    "blades",
    "leather",
)

ARENA_WORDS = ("arena", "pit", "dungeon", "sewer", "slum")
SPECIAL_STEPS = frozenset({"borrow skiff", "search down", "go manhole"})
FARM_DROPS = frozenset({"d", "go manhole"})
_SILVERMERE_HINTS = (
    "town square",
    "guild street",
    "river street",
    "sovereign",
    "silver street",
    "brass street",
    "oak street",
    "crown street",
    "estwall",
    "town gates",
    "helfgrim",
    "skali",
    "sentara",
    "magic shoppe",
    "temple hall",
    "temple spell",
    "temple healer",
    "temple entrance",
    "temple chapel",
    "temple street",
    "clerical training",
    "priestly training",
    "priest's quarters",
    "marble passage",
    "halls of the dead",
    "adventurer's guild",
    "paladin training",
    "ninja training",
    "arena entrance",
    "arena practice",
    "arena stands",
    "sewer",
    "fountain",
    "boathouse",
    "homely hearth",
    "bank of godfrey",
    "wailing",
    "wharf",
    "intersection of",
    "park street",
    "park plaza",
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
# or `a` → `ttack`). `bs` / `at` are the same class on a ninja swing.
_SWING_LEFTOVER = frozenset({"attack", "ttack", "tack", "bs", "at", "att", "bash", "aa"})
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
    if low in {"docks", "pier", "park"}:
        return True
    if in_temple(low) or "temple street" in low:
        return True
    return any(hint in low for hint in _SILVERMERE_HINTS)


def in_temple(room: str) -> bool:
    """Inside the Silvermere temple building — not Temple Street outside."""
    low = room.lower()
    if "temple street" in low:
        return False
    return any(
        hint in low
        for hint in (
            "temple hall",
            "temple spell",
            "temple healer",
            "temple chapel",
            "temple entrance",
            "clerical training",
            "priestly training",
            "priest's quarters",
            "marble passage",
            "halls of the dead",
        )
    )


def at_farm(room: str) -> bool:
    """Newhaven pit or Silvermere sewers — not the temple catacombs."""
    low = room.lower()
    if "sewer" in low or "slum" in low:
        return True
    if "newhaven" in low and "arena" in low:
        return True
    return False


def is_dangerous(room: str) -> bool:
    """A hunt camp. Silvermere arena stands are streets, not the farm."""
    low = room.lower()
    if at_farm(low):
        return True
    if any(word in low for word in ("entrance", "stands", "concession", "practice")):
        return False
    return "arena" in low or "pit" in low


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


def leave_spell_shop(room: str, exits: list[str] | None = None) -> str | None:
    """Newhaven spell shop exits south; Temple Spell Store exits north."""
    low = room.lower()
    prefer = ("n", "e") if "temple" in low else ("s", "n", "e", "w")
    for step in prefer:
        got = _open_step(step, exits)
        if got:
            return got
    return None


def _first_open(prefer: tuple[str, ...], exits: list[str] | None) -> str | None:
    for step in prefer:
        got = _open_step(step, exits)
        if got:
            return got
    return None


def step_out_temple(room: str, exits: list[str] | None = None) -> str | None:
    """East is the street. West is chapel. Down from the healer is catacombs."""
    low = room.lower()
    if "spell" in low:
        return _open_step("n", exits)
    if "healer" in low:
        return _open_step("s", exits)
    if "clerical" in low:
        return _open_step("s", exits)
    if "priestly" in low:
        return _open_step("n", exits)
    if "priest's" in low:
        return _first_open(("e", "n", "s"), exits)
    if "chapel" in low:
        return _first_open(("e", "n"), exits)
    if any(word in low for word in ("marble", "halls of the dead", "dungeon")):
        return _first_open(("u", "e", "n", "s"), exits)
    # Several rooms share the title Temple Hall. East is always toward the door.
    return _first_open(("e", "n", "s", "u"), exits)


def step_toward_square(room: str, exits: list[str] | None = None) -> str | None:
    """One step toward Silvermere Town Square."""
    low = room.lower()
    step: str | None
    if "town square" in low:
        step = None
    elif "sewer" in low:
        step = "u"
    elif "guild street, southern" in low:
        step = "s"
    elif "guild street, northern" in low:
        step = "s"
    elif "guild street" in low:
        step = "s"
    elif "intersection of guild" in low:
        step = "s"
    elif "river street" in low:
        step = "e"
    elif low == "docks" or "wharf" in low:
        step = "s"
    elif low == "pier":
        step = "s"
    elif "boathouse" in low:
        step = "w"
    elif "town gates" in low or "silver street" in low or "estwall" in low:
        step = "w"
    elif "sovereign" in low:
        step = "n"
    elif "temple street" in low:
        step = "e"
    elif in_temple(low):
        return step_out_temple(room, exits)
    elif "helfgrim" in low:
        step = "e"
    elif "skali" in low or "sentara" in low:
        step = "s"
    elif is_general_store(low):
        step = "n"
    elif "magic shoppe" in low:
        step = "n"
    elif "adventurer's guild" in low:
        step = "w"
    elif "arena" in low:
        step = "s"
    elif "brass street" in low:
        step = "s"
    elif "oak street" in low or "crown street" in low:
        step = "w"
    elif "fountain" in low:
        step = "n"
    else:
        step = None
    return _open_step(step, exits)


def step_toward_sewers(room: str, exits: list[str] | None = None) -> str | None:
    """Town Square `go manhole`, or walk toward the square first."""
    low = room.lower()
    if "sewer" in low:
        return None
    if "town square" in low or low == "fountain":
        return _open_step("go manhole", exits)
    return step_toward_square(room, exits)


def step_toward_newhaven(room: str, exits: list[str] | None = None) -> str | None:
    """Skiff back to newbie land: west to docks, north onto the pier, borrow skiff."""
    low = room.lower()
    step: str | None
    if in_newhaven(low):
        if "docks" in low:
            step = "n"
        elif "forest path" in low:
            step = "nw"
        elif "village entrance" in low:
            step = None
        else:
            return step_toward_arena(room, exits)
    elif low == "pier":
        step = "borrow skiff"
    elif low == "docks" or "wharf" in low:
        step = "n"
    elif "boathouse" in low:
        step = "w"
    elif "river street" in low or "intersection of guild" in low:
        step = "w"
    elif "guild street, northern" in low:
        step = "n"
    elif "guild street" in low or "town square" in low:
        step = "n"
    elif "sewer" in low:
        step = "u"
    else:
        hub = step_toward_square(room, exits)
        return hub
    return _open_step(step, exits)


def step_toward_store(room: str, exits: list[str] | None = None) -> str | None:
    """Narrow Road east to the path, south into the general store."""
    low = room.lower()
    if in_silvermere(room) and not in_newhaven(room):
        if is_general_store(low):
            return None
        if "town square" in low:
            return _open_step("e", exits)
        return step_toward_square(room, exits)
    step: str | None
    if "general" in low:
        step = None
    elif any(word in low for word in ARENA_WORDS):
        step = "u"
    elif "healer" in low:
        step = "e"
    elif "guild" in low:
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


def step_toward_spell_shop(
    room: str,
    exits: list[str] | None = None,
    via: str = "",
    prev: str = "",
) -> str | None:
    """Newhaven Spell Shop, or Silvermere Temple Spell Store west of the square.

    Temple Hall is two rooms with the same name. `s` is the shop only just after
    walking in from Temple Street. Any other Temple Hall: `e` toward the door.
    """
    low = room.lower()
    if is_spell_shop(low):
        return None
    if "temple street" in low:
        return _open_step("w", exits)
    if "town square" in low:
        return _open_step("w", exits)
    if in_temple(room):
        if "healer" in low:
            return _open_step("s", exits)
        if "temple hall" in low or "temple entrance" in low:
            from_street = "temple street" in prev.lower() and via.strip().lower() == "w"
            if from_street:
                return _open_step("s", exits)
            return step_out_temple(room, exits)
        return step_out_temple(room, exits)
    if in_silvermere(room):
        return step_toward_square(room, exits)
    step: str | None
    if any(word in low for word in ARENA_WORDS):
        step = "u"
    elif "healer" in low:
        step = "e"
    elif "guild" in low:
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
    """Newhaven guild hall or a class training room — not Guild Street."""
    low = room.lower()
    if "street" in low:
        return False
    if "training room" in low or "universal trainer" in low:
        return True
    return "newhaven" in low and "guild" in low


def step_toward_guild(room: str, exits: list[str] | None = None) -> str | None:
    """Newhaven guild north of Narrow Road, or Silvermere class training rooms."""
    low = room.lower()
    if is_trainer(low):
        return None
    if in_silvermere(room):
        if "adventurer's guild, foyer" in low:
            return _open_step("e", exits)
        if "adventurer's guild, main" in low:
            return _open_step("s", exits)
        if "town square" in low:
            return _open_step("n", exits)
        if "guild street, southern" in low:
            return _open_step("n", exits)
        return step_toward_square(room, exits)
    step: str | None
    if any(word in low for word in ARENA_WORDS):
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


def step_toward_arena(room: str, exits: list[str] | None = None) -> str | None:
    """Newhaven pit (`d`) or Silvermere sewers (`go manhole`)."""
    low = room.lower()
    if at_farm(low):
        return None
    if in_silvermere(room):
        return step_toward_sewers(room, exits)
    step: str | None
    if any(word in low for word in ARENA_WORDS):
        step = None
    elif "healer" in low:
        step = "e"
    elif "guild" in low:
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
    elif "narrow path" in low:
        step = "w"
    elif "narrow road" in low:
        step = "d"
    else:
        step = None
    return _open_step(step, exits)


def _open_step(step: str | None, exits: list[str] | None) -> str | None:
    if not step:
        return None
    low = step.strip().lower()
    if is_special_step(low):
        return low
    if exits and low not in exits:
        return None
    return low
