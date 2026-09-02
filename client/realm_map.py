"""Live MajorMUD room graph. Seeded from the NewHaven walk in paths.py.

Persists under data/ (gitignored). Does not read WCCMMUD module files.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "data" / "realm-map.json"

DIRS = ("n", "s", "e", "w", "u", "d")
REVERSE = {"n": "s", "s": "n", "e": "w", "w": "e", "u": "d", "d": "u"}

# Mirrors client/paths.py: village entrance, shops, narrow path/road, arena.
NEWHAVEN = {
    "Newhaven, Village Entrance": {
        "n": "Newhaven, Weapon Shop",
        "s": "Newhaven, Armour Shop",
        "w": "Newhaven, Narrow Path",
    },
    "Newhaven, Weapon Shop": {"s": "Newhaven, Village Entrance"},
    "Newhaven, Armour Shop": {"n": "Newhaven, Village Entrance"},
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
}

_HOME_HINTS = (
    "arena",
    "narrow road",
    "village entrance",
    "healer",
    "newhaven",
)


def room_key(title: str) -> str:
    """Dedup Newhaven, Arena / Newhaven Arena."""
    cleaned = title.lower().replace(",", " ")
    return " ".join(cleaned.split())


def reverse_dir(step: str) -> str:
    return REVERSE.get(step.strip().lower(), "")


def _mappable(title: str) -> bool:
    raw = title.strip()
    if not raw or len(raw) > 60:
        return False
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
        self._seed_newhaven()
        if self.store:
            self.load()

    def room_count(self) -> int:
        return len(self.rooms)

    def known(self, title: str) -> bool:
        key = room_key(title)
        return bool(key) and key in self.rooms

    def _seed_newhaven(self) -> None:
        for title, exits in NEWHAVEN.items():
            key = room_key(title)
            self.rooms[key] = {"title": title, "exits": sorted(exits)}
            for step, dest in exits.items():
                self.edges[(key, step)] = room_key(dest)

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
        seen = [d for d in (exits or []) if d in DIRS]
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
            back = REVERSE.get(step)
            if back and (key, back) not in self.edges:
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
        """Shortest known walk toward arena, then Newhaven."""
        start = room_key(title)
        if not start or start not in self.rooms:
            return []
        allowed = {d for d in (exits or []) if d in DIRS} if exits else None
        for hint in _HOME_HINTS:
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
                if here == start and allowed is not None and step not in allowed:
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
