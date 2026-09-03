"""Live MajorMUD room graph. Seeded from Newhaven and Silvermere walks.

Persists under data/ (gitignored). Does not read WCCMMUD module files.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from .paths import in_newhaven, in_silvermere

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "data" / "realm-map.json"

CARDINALS = ("n", "s", "e", "w", "u", "d", "ne", "nw", "se", "sw")
SPECIALS = ("borrow skiff", "search down", "go manhole")
DIRS = CARDINALS + SPECIALS
REVERSE = {
    "n": "s",
    "s": "n",
    "e": "w",
    "w": "e",
    "u": "d",
    "d": "u",
    "ne": "sw",
    "nw": "se",
    "se": "nw",
    "sw": "ne",
    "borrow skiff": "borrow skiff",
    "go manhole": "u",
    "search down": "u",
}

# Mirrors client/paths.py: village entrance, shops, narrow path/road, arena.
NEWHAVEN = {
    "Newhaven, Village Entrance": {
        "n": "Newhaven, Weapon Shop",
        "s": "Newhaven, Armour Shop",
        "w": "Newhaven, Narrow Path",
        "se": "Newhaven, Forest Path",
    },
    "Newhaven, Weapon Shop": {"s": "Newhaven, Village Entrance"},
    "Newhaven, Nathaniel": {"s": "Newhaven, Village Entrance"},
    "Newhaven, Armour Shop": {"n": "Newhaven, Village Entrance"},
    "Newhaven, Betram": {"n": "Newhaven, Village Entrance"},
    "Newhaven, Narrow Path": {
        "n": "Newhaven, Spell Shop",
        "s": "Newhaven, General Store",
        "e": "Newhaven, Village Entrance",
        "w": "Newhaven, Narrow Road",
    },
    "Newhaven, Spell Shop": {"s": "Newhaven, Narrow Path"},
    "Newhaven, General Store": {"n": "Newhaven, Narrow Path"},
    "Newhaven, Narrow Road": {
        "n": "Newhaven, Guild",
        "e": "Newhaven, Narrow Path",
        "w": "Newhaven, Healer",
        "d": "Newhaven, Arena",
    },
    "Newhaven, Guild": {"s": "Newhaven, Narrow Road"},
    "Newhaven, Healer": {"e": "Newhaven, Narrow Road"},
    "Newhaven, Arena": {"u": "Newhaven, Narrow Road"},
    "Newhaven, Forest Path": {
        "nw": "Newhaven, Village Entrance",
        "s": "Newhaven, Docks",
    },
    "Newhaven, Docks": {
        "n": "Newhaven, Forest Path",
        "borrow skiff": "Pier",
    },
}

# Live Silvermere titles (no "Silvermere," prefix). Landmarks only — generic
# River Street tiles share a name, so streets walk by compass in paths.py.
SILVERMERE = {
    "Town Square": {
        "n": "Guild Street, Southern End",
        "go manhole": "Sewer Tunnel, Junction (below TS)",
    },
    "Guild Street, Southern End": {
        "s": "Town Square",
        "n": "Guild Street, Northern End",
    },
    "Guild Street, Northern End": {
        "s": "Guild Street, Southern End",
        "n": "Intersection of Guild St. & River St.",
    },
    "Intersection of Guild St. & River St.": {
        "s": "Guild Street, Northern End",
        "w": "Docks",
    },
    "Docks": {
        "e": "Intersection of Guild St. & River St.",
        "n": "Pier",
        "s": "Intersection of Guild St. & River St.",
        "search down": "Pier",
    },
    "Pier": {
        "s": "Docks",
        "borrow skiff": "Newhaven, Docks",
    },
    "Sewer Tunnel, Junction (below TS)": {"u": "Town Square"},
    "Fountain": {"go manhole": "Sewer Tunnel, Junction (below TS)"},
    "Temple Hall": {"s": "Temple Spell Store", "n": "Temple Healer", "e": "Temple Street"},
    "Temple Spell Store": {"n": "Temple Hall"},
    "Temple Healer": {"s": "Temple Hall"},
    "Temple Chapel": {"e": "Temple Hall"},
    "Clerical Training Room": {"s": "Temple Hall"},
    "Priestly Training Room": {"n": "Temple Hall"},
    "Temple Street": {"e": "Town Square", "w": "Temple Hall"},
    "Helfgrim's Blades": {"e": "Guild Street, Southern End"},
    "Skali's Fine Armour, Front Room": {"s": "Town Square"},
    "Sentara's Clothing, Front Room": {"s": "Town Square", "w": "Town Square"},
    "General Store": {"n": "Town Square"},
    "Magic Shoppe": {"n": "Intersection of Guild St. & River St."},
    "Paladin Training Room": {},
    "Ninja Training Room": {},
    "Arena Entrance": {"s": "Town Square"},
}

_NEWHAVEN_HOME = (
    "arena",
    "narrow road",
    "village entrance",
    "healer",
    "newhaven",
)
_SILVERMERE_HOME = (
    "sewer",
    "town square",
)
_HOME_HINTS = _SILVERMERE_HOME + _NEWHAVEN_HOME


def room_key(title: str) -> str:
    """Dedup Newhaven, Arena / Newhaven Arena."""
    cleaned = title.lower().replace(",", " ")
    return " ".join(cleaned.split())


def reverse_dir(step: str) -> str:
    return REVERSE.get(step.strip().lower(), "")


def _mappable(title: str) -> bool:
    raw = title.strip()
    if not raw or len(raw) > 80:
        return False
    if raw.endswith("St."):
        words = raw.split()
        return 2 <= len(words) <= 10
    if raw.endswith(("!", ":", "]", ".")):
        return False
    if raw[0].islower() or raw[0].isdigit():
        return False
    if raw.startswith(("You ", "A ", "The ", "An ", "[")):
        # "The Town Square" is a real room; combat lines end with ! already.
        if raw.startswith("The ") and not raw.endswith("!"):
            words = raw.split()
            return 2 <= len(words) <= 6
        return False
    return True


@dataclass
class Hint:
    action: str = ""
    step: str = ""
    route: list[str] = field(default_factory=list)
    chrome: str = ""


class Atlas:
    def __init__(self, path: Path | str | None = None) -> None:
        self.store = Path(path) if path else None
        self.rooms: dict[str, dict[str, object]] = {}
        self.edges: dict[tuple[str, str], str] = {}
        self._seed_graph(NEWHAVEN)
        self._seed_graph(SILVERMERE)
        if self.store:
            self.load()

    def room_count(self) -> int:
        return len(self.rooms)

    def known(self, title: str) -> bool:
        key = room_key(title)
        return bool(key) and key in self.rooms

    def _seed_graph(self, graph: dict[str, dict[str, str]]) -> None:
        for title, exits in graph.items():
            key = room_key(title)
            node = self.rooms.get(key)
            if node is None:
                self.rooms[key] = {"title": title, "exits": sorted(exits)}
            else:
                old = list(node.get("exits") or [])
                node["exits"] = sorted(set(old) | set(exits))
            for step, dest in exits.items():
                self.edges[(key, step)] = room_key(dest)

    def _seed_newhaven(self) -> None:
        self._seed_graph(NEWHAVEN)

    def observe(
        self,
        title: str,
        exits: list[str] | None,
        via: str = "",
        prev: str = "",
    ) -> str:
        """Record a room and the edge that reached it. Returns the room key."""
        raw = (title or "").strip()
        if raw and not _mappable(raw):
            raw = ""
        key = room_key(raw) if raw else ""
        step = via.strip().lower()
        if step not in DIRS:
            step = ""
        prev_key = room_key(prev) if prev and _mappable(prev) else ""
        if not key and prev_key and step:
            key = f"?{prev_key}:{step}"
            raw = raw or key
        if not key:
            return ""
        seen = [d for d in (exits or []) if d in CARDINALS]
        node = self.rooms.get(key)
        if node is None:
            self.rooms[key] = {"title": raw, "exits": seen}
        else:
            if raw and not str(node.get("title") or "").startswith("?"):
                node["title"] = raw
            old = [d for d in node.get("exits") or [] if d in DIRS]
            node["exits"] = sorted(set(old) | set(seen))
        if prev_key and step and prev_key != key:
            self.edges[(prev_key, step)] = key
            back = REVERSE.get(step, "")
            if back in CARDINALS and (key, back) not in self.edges:
                self.edges[(key, back)] = prev_key
            if prev_key in self.rooms:
                old = [d for d in self.rooms[prev_key].get("exits") or [] if d in DIRS]
                if step not in old:
                    self.rooms[prev_key]["exits"] = sorted(set(old) | {step})
        self.save()
        return key

    def path(self, src: str, dest: str) -> list[str]:
        start = room_key(src)
        goal = room_key(dest)
        if not start or start not in self.rooms:
            return []
        if start == goal:
            return []
        return self._bfs(start, {goal})

    def way_home(self, title: str, exits: list[str] | None = None) -> list[str]:
        """Shortest known walk toward the local farm, then the town hub."""
        start = room_key(title)
        if not start or start not in self.rooms:
            return []
        allowed = {d for d in (exits or []) if d in DIRS} if exits else None
        if in_newhaven(title):
            hints = _NEWHAVEN_HOME
        elif in_silvermere(title):
            hints = _SILVERMERE_HOME
        else:
            hints = _NEWHAVEN_HOME + _SILVERMERE_HOME
        for hint in hints:
            goals = {key for key in self.rooms if hint in key}
            goals.discard(start)
            if not goals:
                continue
            route = self._bfs(start, goals, allowed)
            if route:
                return route
        return []

    def suggest(
        self,
        title: str,
        exits: list[str] | None,
        last_step: str = "",
        scanned: bool = True,
    ) -> Hint:
        """What to do when lost. Caller skips this while following."""
        count = self.room_count()
        if not scanned:
            return Hint(action="look", chrome=f"map: {count} rooms")
        route = self.way_home(title, exits)
        if route:
            return Hint(
                action="path",
                step=route[0],
                route=route,
                chrome=f"path: {','.join(route)}",
            )
        if self.known(title):
            return Hint()
        back = reverse_dir(last_step)
        for guess in (back, "u"):
            if not guess:
                continue
            if exits and guess not in exits:
                continue
            return Hint(
                action="guess",
                step=guess,
                chrome=f"map: {count} rooms",
            )
        return Hint(action="look", chrome=f"map: {count} rooms")

    def _bfs(
        self,
        start: str,
        goals: set[str],
        allowed: set[str] | None = None,
    ) -> list[str]:
        if start in goals:
            return []
        seen = {start}
        q: deque[tuple[str, list[str]]] = deque([(start, [])])
        while q:
            here, route = q.popleft()
            for step in DIRS:
                dest = self.edges.get((here, step))
                if not dest or dest in seen:
                    continue
                if (
                    here == start
                    and allowed is not None
                    and step not in allowed
                    and step not in SPECIALS
                ):
                    continue
                nxt = [*route, step]
                if dest in goals:
                    return nxt
                seen.add(dest)
                q.append((dest, nxt))
        return []

    def load(self) -> None:
        if not self.store or not self.store.is_file():
            return
        try:
            data = json.loads(self.store.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        rooms = data.get("rooms") or {}
        if isinstance(rooms, dict):
            for key, node in rooms.items():
                if not isinstance(key, str) or not isinstance(node, dict):
                    continue
                title = str(node.get("title") or key)
                exits = [d for d in node.get("exits") or [] if d in DIRS]
                self.rooms[room_key(key) if " " in key or key[:1] != "?" else key] = {
                    "title": title,
                    "exits": exits,
                }
        for edge in data.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            src = room_key(str(edge.get("from") or ""))
            dest = room_key(str(edge.get("to") or ""))
            step = str(edge.get("dir") or "").lower()
            if src and dest and step in DIRS:
                self.edges[(src, step)] = dest

    def save(self) -> None:
        if not self.store:
            return
        payload = {
            "rooms": {
                key: {
                    "title": node.get("title") or key,
                    "exits": list(node.get("exits") or []),
                }
                for key, node in sorted(self.rooms.items())
            },
            "edges": [
                {"from": src, "dir": step, "to": dest}
                for (src, step), dest in sorted(self.edges.items())
            ],
        }
        try:
            self.store.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.store.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            tmp.replace(self.store)
        except OSError:
            return
