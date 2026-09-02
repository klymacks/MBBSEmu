from __future__ import annotations

import tempfile
from pathlib import Path

from .realm_map import Atlas, NEWHAVEN, SILVERMERE, room_key


def test_seed_has_newhaven() -> None:
    atlas = Atlas()
    assert atlas.known("Newhaven, Arena")
    assert atlas.known("Newhaven Arena")
    assert atlas.known("Newhaven, Village Entrance")
    assert atlas.room_count() >= len(NEWHAVEN)
    assert atlas.path("Newhaven, Village Entrance", "Newhaven, Arena") == [
        "w",
        "w",
        "d",
    ]
    assert atlas.path("Newhaven, Arena", "Newhaven, Guild") == ["u", "n"]
    assert atlas.path("Newhaven, Narrow Road", "Newhaven, Guild") == ["n"]
    assert atlas.path("Newhaven, Village Entrance", "Newhaven, Docks") == ["se", "s"]
    assert atlas.path("Pier", "Newhaven, Docks") == ["borrow skiff"]
    assert atlas.way_home("Town Square") == ["go manhole"]
    assert atlas.way_home("Newhaven, Village Entrance") == ["w", "w", "d"]
    assert atlas.known("Town Square")
    assert atlas.room_count() >= len(NEWHAVEN) + len(SILVERMERE)


def test_record_edge_bfs() -> None:
    atlas = Atlas()
    atlas.observe("Room A", ["d"])
    atlas.observe("Newhaven, Arena", ["u"], via="d", prev="Room A")
    assert atlas.path("Room A", "Newhaven, Arena") == ["d"]
    assert atlas.way_home("Room A") == ["d"]


def test_unknown_room_no_crash() -> None:
    atlas = Atlas()
    assert atlas.path("???", "Newhaven, Arena") == []
    assert atlas.way_home("") == []
    assert atlas.way_home("no such hall") == []
    key = atlas.observe("", ["n"], via="s", prev="Somewhere Dark")
    assert key.startswith("?")
    hint = atlas.suggest("Mystery Cave", ["n", "s"], last_step="n", scanned=True)
    assert hint.action in {"guess", "look"}
    assert hint.step in {"", "s", "u"}


def test_suggest_look_when_unscanned() -> None:
    atlas = Atlas()
    hint = atlas.suggest("Room A", ["d"], scanned=False)
    assert hint.action == "look"
    assert hint.chrome.startswith("map:")


def test_suggest_path_chrome() -> None:
    atlas = Atlas()
    atlas.observe("Room A", ["d"])
    atlas.observe("Newhaven, Arena", ["u"], via="d", prev="Room A")
    hint = atlas.suggest("Room A", ["d"], scanned=True)
    assert hint.action == "path"
    assert hint.route == ["d"]
    assert hint.chrome == "path: d"


def test_normalize_title() -> None:
    assert room_key("Newhaven, Arena") == room_key("Newhaven Arena")
    assert room_key("  Newhaven,  Arena ") == "newhaven arena"


def test_persist_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "realm-map.json"
        atlas = Atlas(path)
        atlas.observe("Room A", ["d"])
        atlas.observe("Newhaven, Arena", ["u"], via="d", prev="Room A")
        again = Atlas(path)
        assert again.path("Room A", "Newhaven, Arena") == ["d"]


if __name__ == "__main__":
    test_seed_has_newhaven()
    test_record_edge_bfs()
    test_unknown_room_no_crash()
    test_suggest_look_when_unscanned()
    test_suggest_path_chrome()
    test_normalize_title()
    test_persist_roundtrip()
    print("ok")
