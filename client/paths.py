"""NewHaven rooms recorded from a live walk on Finn's Realm (1.11p).

Village Entrance: south armour (Betram), north weapons, west to the path.
Narrow Path: south general store, north spell shop, west to the road.
Narrow Road: down into the arena (filthbugs), north guild, west healer.

MegaMMUD v2.1 Stock .mp files use the same graph (Newhaven Town = Narrow Road,
Temple Healer = healer, shops Betram / Nathaniel / Dathalar / Rayth). Arena
farm is u then d. Do not import Paramud rooms or the cave-bear / Silvermere
legs.
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
)

ARENA_WORDS = ("arena", "pit", "dungeon", "sewer", "slum")
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
_SWING_LEFTOVER = frozenset({"attack", "ttack", "tack", "bs", "at"})
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

    `a carrion beast` is speech. `attack` leaves `tack` on the line.
    `at acid slime` eats `at` into the name → spoken `a id slime`.
    `k` is kill — same swing, no collision with `acid`.
    """
    aim = attack_name(name) if name else ""
    if not aim:
        return "k"
    return f"k {aim}"


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
    elif "guild" in low:
        step = "s"
    elif "narrow road" in low:
        step = "e"
    elif "narrow path" in low:
        step = "s"
    elif "village entrance" in low:
        step = "w"
    elif "weapon" in low:
        step = "s"
    elif "armour" in low or "armor" in low:
        step = "n"
    elif "spell" in low:
        step = "s"
    else:
        step = None
    return _open_step(step, exits)


def is_trainer(room: str) -> bool:
    """Newhaven guild, north of Narrow Road."""
    return "guild" in room.lower()


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
    elif "armour" in low or "armor" in low:
        step = "n"
    elif "weapon" in low:
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
    """One step toward Narrow Road, then down into the arena."""
    low = room.lower()
    step: str | None
    if any(word in low for word in ARENA_WORDS):
        step = None
    elif "healer" in low:
        step = "e"
    elif "guild" in low:
        step = "s"
    elif "armour" in low or "armor" in low:
        step = "n"
    elif "weapon" in low:
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
    if exits and step not in exits:
        return None
    return step
