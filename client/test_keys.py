from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

from client.brain import Brain
from client.parse import parse_line
from client.state import WorldState

_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("bbs_client", _ROOT / "scripts" / "bbs_client.py")
assert _SPEC and _SPEC.loader
_CLIENT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CLIENT)


def _read(seq: bytes) -> bytes | None:
    pending = bytearray(seq)
    key = _CLIENT.read_key(-1, pending)
    assert not pending, seq
    return key


def test_f2_sequences() -> None:
    for seq in (b"\x1bOQ", b"\x1b[12~", b"\x1b[OQ", b"\x1b[[B", b"\x8fQ", b"\x1b[12;2~"):
        pending = bytearray(seq)
        key = _CLIENT.read_key(-1, pending)
        assert key == _CLIENT.KEY_F2, seq
        assert not pending


def test_f1_sequences() -> None:
    for seq in (b"\x1bOP", b"\x1b[11~", b"\x1b[[A", b"\x8fP"):
        pending = bytearray(seq)
        key = _CLIENT.read_key(-1, pending)
        assert key == _CLIENT.KEY_F1, seq


def test_f3_to_f8_sequences() -> None:
    cases = (
        (b"\x1bOR", _CLIENT.KEY_F3),
        (b"\x1b[13~", _CLIENT.KEY_F3),
        (b"\x1b[OR", _CLIENT.KEY_F3),
        (b"\x1b[[C", _CLIENT.KEY_F3),
        (b"\x8fR", _CLIENT.KEY_F3),
        (b"\x1b[13;2~", _CLIENT.KEY_F3),
        (b"\x1bOS", _CLIENT.KEY_F4),
        (b"\x1b[14~", _CLIENT.KEY_F4),
        (b"\x1b[[D", _CLIENT.KEY_F4),
        (b"\x8fS", _CLIENT.KEY_F4),
        (b"\x1b[15~", _CLIENT.KEY_F5),
        (b"\x1b[[E", _CLIENT.KEY_F5),
        (b"\x8fT", _CLIENT.KEY_F5),
        (b"\x1b[17~", _CLIENT.KEY_F6),
        (b"\x1b[17;2~", _CLIENT.KEY_F6),
        (b"\x8fU", _CLIENT.KEY_F6),
        (b"\x1b[18~", _CLIENT.KEY_F7),
        (b"\x8fV", _CLIENT.KEY_F7),
        (b"\x1b[19~", _CLIENT.KEY_F8),
        (b"\x1b[19;2~", _CLIENT.KEY_F8),
        (b"\x1bOW", _CLIENT.KEY_F8),
        (b"\x8fW", _CLIENT.KEY_F8),
        (b"\x1b[20~", _CLIENT.KEY_F9),
        (b"\x1b[20;2~", _CLIENT.KEY_F9),
        (b"\x1bOX", _CLIENT.KEY_F9),
        (b"\x8fX", _CLIENT.KEY_F9),
        (b"\x1b[21~", _CLIENT.KEY_F10),
        (b"\x1b[21;2~", _CLIENT.KEY_F10),
        (b"\x1bOY", _CLIENT.KEY_F10),
        (b"\x8fY", _CLIENT.KEY_F10),
        (b"\x1b[23~", _CLIENT.KEY_F11),
        (b"\x1b[23;2~", _CLIENT.KEY_F11),
    )
    for seq, want in cases:
        assert _read(seq) == want, seq


def test_esc_o_waits() -> None:
    pending = bytearray(b"\x1bO")
    assert _CLIENT.read_key(-1, pending) is None
    assert pending == bytearray(b"\x1bO")
    pending.extend(b"Q")
    assert _CLIENT.read_key(-1, pending) == _CLIENT.KEY_F2


def test_peek_commands() -> None:
    assert _CLIENT.PEEK_COMMANDS[_CLIENT.KEY_F2] == "look"
    assert _CLIENT.PEEK_COMMANDS[_CLIENT.KEY_F3] == "health"
    assert _CLIENT.PEEK_COMMANDS[_CLIENT.KEY_F4] == "inventory"
    assert _CLIENT.PEEK_COMMANDS[_CLIENT.KEY_F5] == "exp"
    assert _CLIENT.PEEK_COMMANDS[_CLIENT.KEY_F6] == "who"
    assert _CLIENT.KEY_F7 not in _CLIENT.PEEK_COMMANDS
    assert _CLIENT.KEY_F8 not in _CLIENT.PEEK_COMMANDS
    assert _CLIENT.KEY_F9 not in _CLIENT.PEEK_COMMANDS
    assert _CLIENT.KEY_F10 not in _CLIENT.PEEK_COMMANDS
    assert _CLIENT.KEY_F11 not in _CLIENT.PEEK_COMMANDS
    assert _CLIENT.KEY_F1 not in _CLIENT.PEEK_COMMANDS


def _special(
    key: bytes,
    *,
    in_realm: bool,
    hunting: bool = True,
    brain: Brain | None = None,
    state: WorldState | None = None,
):
    brain = brain or Brain(allowed=True)
    if hunting:
        brain.mode = "hunt"
        brain.next_action = "lop"
    pacer = _CLIENT.KeyPacer()
    world = state if state is not None else WorldState()
    kind = _CLIENT.handle_special_key(
        key, brain, pacer, in_realm=in_realm, state=world
    )
    return kind, brain, pacer, world


def _drain(pacer: _CLIENT.KeyPacer) -> list[bytes]:
    out: list[bytes] = []
    now = 1.0
    while True:
        line = pacer.take(now)
        if line is None:
            break
        out.append(line)
        now += 1.0
    return out


def _next_cmd(pacer: _CLIENT.KeyPacer, now: float = 1.0) -> bytes | None:
    """Skip prompt-wipe packets; return the next CR-terminated line."""
    t = now
    while True:
        item = pacer.take(t)
        t += 1.0
        if item is None:
            return None
        if item.endswith(b"\r"):
            return item


def _cmds(pacer: _CLIENT.KeyPacer) -> list[bytes]:
    return [ln for ln in _drain(pacer) if ln.endswith(b"\r")]


def _arena(*, following: str = "") -> WorldState:
    state = WorldState()
    state.in_realm = True
    state.hp = 20
    state.max_hp = 28
    state.max_hp_known = True
    state.room = "Newhaven, Arena"
    state.exits = ["u"]
    state.scanned = True
    state.in_combat = True
    state.following = following
    return state


def test_peek_does_not_stop_hunter() -> None:
    kind, brain, pacer, _ = _special(_CLIENT.KEY_F2, in_realm=True)
    assert kind == "peek"
    assert brain.mode == "hunt"
    assert brain.next_action == "lop"
    assert pacer.pending()
    line = _next_cmd(pacer)
    assert line is not None
    assert line.endswith(b"look\r")


def test_peek_all_keys_queue() -> None:
    for key, cmd in _CLIENT.PEEK_COMMANDS.items():
        kind, brain, pacer, _ = _special(key, in_realm=True)
        assert kind == "peek"
        assert brain.mode == "hunt"
        line = _next_cmd(pacer)
        assert line is not None
        assert line.endswith(f"{cmd}\r".encode("ascii"))


def test_peek_skipped_outside_realm() -> None:
    kind, brain, pacer, _ = _special(_CLIENT.KEY_F3, in_realm=False)
    assert kind == "peek"
    assert brain.mode == "hunt"
    assert not pacer.pending()


def test_peek_queues_behind_pending() -> None:
    kind, brain, pacer = _special(_CLIENT.KEY_F2, in_realm=True)[:3]
    assert kind == "peek"
    pacer_first = _CLIENT.KeyPacer()
    pacer_first.push_text("attack rat")
    again = _CLIENT.handle_special_key(
        _CLIENT.KEY_F5, brain, pacer_first, in_realm=True, state=WorldState()
    )
    assert again == "peek"
    assert brain.mode == "hunt"
    first = _next_cmd(pacer_first, 1.0)
    second = _next_cmd(pacer_first, 3.0)
    assert first is not None and first.endswith(b"k rat\r")
    assert second is not None and second.endswith(b"exp\r")


def test_realm_line_shortens_attack() -> None:
    """`k` is kill. `a carrion beast` is speech; `at acid slime` becomes spoken `a id slime`."""
    assert _CLIENT.realm_line("attack acid slime") == "k acid slime"
    assert _CLIENT.realm_line("attack") == "k"
    assert _CLIENT.realm_line("look") == "look"
    assert _CLIENT.realm_line("bs giant rat") == "bs giant rat"
    pacer = _CLIENT.KeyPacer()
    pacer.push_text("attack acid slime")
    assert _next_cmd(pacer, 1.0) == b"k acid slime\r"
    pacer.push_text("M", wipe=False)
    assert pacer.take(3.0) == b"M\r"


def test_f7_toggles_hunt() -> None:
    kind, brain, pacer, _ = _special(_CLIENT.KEY_F7, in_realm=True, hunting=False)
    assert kind == "hunt"
    assert brain.mode in ("gear", "hunt")
    assert not pacer.pending()


def test_f2_is_look_not_hunt() -> None:
    kind, brain, pacer, _ = _special(_CLIENT.KEY_F2, in_realm=True, hunting=False)
    assert kind == "peek"
    assert brain.mode == "manual"
    assert _next_cmd(pacer).endswith(b"look\r")


def test_f1_panic_party_break_only() -> None:
    brain = Brain(allowed=True, me="klymacks", party_leader="Matt")
    brain.mode = "hunt"
    brain.gear_done = True
    brain._followed = True
    brain._attacking = "filthbug"
    brain._last_cast = "heal:minor healing"
    brain._cast_at = 99.0
    state = _arena(following="Matt")
    kind, brain, pacer, state = _special(
        _CLIENT.KEY_F1, in_realm=True, brain=brain, state=state
    )
    assert kind == "panic"
    assert brain.mode == "hunt"
    assert brain._attacking == ""
    assert brain._last_cast == ""
    assert brain._cast_at == 0.0
    assert not state.in_combat
    lines = _cmds(pacer)
    assert [ln.endswith(b"break\r") for ln in lines] == [True]
    blob = b" ".join(lines)
    assert b"\r u\r" not in blob and not any(ln.endswith(b"u\r") for ln in lines)
    assert b"follow" not in blob


def test_f1_panic_leader_with_followers_stays() -> None:
    brain = Brain(allowed=True, me="Matt", party_leader="Matt", klass="paladin")
    brain.mode = "hunt"
    brain.gear_done = True
    brain._in_camp = True
    brain._attacking = "acid slime"
    state = _arena()
    state.followers = ["klymacks"]
    kind, brain, pacer, _ = _special(
        _CLIENT.KEY_F1, in_realm=True, brain=brain, state=state
    )
    assert kind == "panic"
    assert brain.mode == "hunt"
    lines = _cmds(pacer)
    assert len(lines) == 1 and lines[0].endswith(b"break\r")


def test_f1_panic_solo_pit_break_then_u() -> None:
    brain = Brain(allowed=True)
    brain.mode = "hunt"
    brain.gear_done = True
    brain._in_camp = True
    brain._attacking = "filthbug"
    state = _arena()
    kind, brain, pacer, state = _special(
        _CLIENT.KEY_F1, in_realm=True, brain=brain, state=state
    )
    assert kind == "panic"
    assert brain.mode == "hunt"
    assert not state.in_combat
    lines = _cmds(pacer)
    assert len(lines) == 2
    assert lines[0].endswith(b"break\r")
    assert lines[1].endswith(b"u\r")


def test_f1_panic_does_not_takeover_or_reaggro() -> None:
    brain = Brain(allowed=True)
    brain.mode = "hunt"
    brain.gear_done = True
    brain._in_camp = True
    brain._attacking = "filthbug"
    brain._asked_health = True
    state = _arena()
    state.hp = 28
    state.max_hp = 28
    state.mobs = ["filthbug"]
    state.prompt_seq = 10
    kind, brain, pacer, state = _special(
        _CLIENT.KEY_F1, in_realm=True, brain=brain, state=state
    )
    assert kind == "panic"
    assert brain.mode == "hunt"
    _drain(pacer)
    state.prompt_seq += 1
    sent: list[str] = []
    brain.tick(state, sent.append, pending=False)
    assert brain.mode == "hunt"
    assert not any(item.startswith("attack") or item.startswith("bs ") for item in sent)


def test_f1_leader_hurt_does_not_pit_flee() -> None:
    brain = Brain(allowed=True, me="Matt", party_leader="Matt", klass="paladin")
    brain.mode = "hunt"
    brain.gear_done = True
    brain._in_camp = True
    brain._asked_health = True
    state = _arena()
    state.followers = ["klymacks"]
    state.hp = 10
    state.mobs = []
    state.in_combat = False
    state.prompt_seq = 20
    pacer = _CLIENT.KeyPacer()
    _CLIENT.handle_special_key(
        _CLIENT.KEY_F1, brain, pacer, in_realm=True, state=state
    )
    _drain(pacer)
    state.prompt_seq += 1
    sent: list[str] = []
    brain.tick(state, sent.append, pending=False)
    assert "u" not in sent
    assert "follow off" not in sent


def test_f1_panic_matt_mortal_rescues() -> None:
    brain = Brain(
        allowed=True, me="klymacks", party_leader="Matt", klass="ninja"
    )
    brain.mode = "hunt"
    brain.gear_done = True
    brain._followed = True
    brain._ranked = True
    brain._in_camp = True
    state = _arena(following="Matt")
    state.apply({"kind": "mortal", "name": "Matt"})
    kind, brain, pacer, state = _special(
        _CLIENT.KEY_F1, in_realm=True, brain=brain, state=state
    )
    assert kind == "panic"
    assert brain.mode == "hunt"
    assert brain._rescue == "out"
    assert brain._panic_until == 0.0
    lines = _cmds(pacer)
    assert lines and lines[0].endswith(b"break\r")
    assert not any(ln.endswith(b"u\r") for ln in lines)
    state.in_combat = False
    state.prompt_seq += 1
    sent: list[str] = []
    brain.tick(state, sent.append, pending=False)
    assert sent[-1] == "leave"
    assert "u" not in sent


def test_f1_party_tick_does_not_flee() -> None:
    brain = Brain(
        allowed=True, me="klymacks", party_leader="Matt", klass="ninja"
    )
    brain.mode = "hunt"
    brain.gear_done = True
    brain._followed = True
    brain._ranked = True
    brain._in_camp = True
    brain._asked_health = True
    state = _arena(following="Matt")
    state.hp = 10
    state.mobs = ["filthbug"]
    state.prompt_seq = 20
    _CLIENT.handle_special_key(
        _CLIENT.KEY_F1, brain, _CLIENT.KeyPacer(), in_realm=True, state=state
    )
    state.prompt_seq += 1
    sent: list[str] = []
    brain.tick(state, sent.append, pending=False)
    assert "u" not in sent
    assert "follow off" not in sent
    assert brain.mode == "hunt"


def test_f1_skipped_outside_realm() -> None:
    kind, brain, pacer, _ = _special(_CLIENT.KEY_F1, in_realm=False)
    assert kind == "panic"
    assert brain.mode == "hunt"
    assert not pacer.pending()


def _road(*, resting: bool = False) -> WorldState:
    state = WorldState()
    state.in_realm = True
    state.hp = 28
    state.max_hp = 28
    state.max_hp_known = True
    state.room = "Newhaven, Narrow Road"
    state.exits = ["n", "e", "w", "d"]
    state.scanned = True
    state.resting = resting
    return state


def _pit_slime() -> WorldState:
    state = WorldState()
    state.in_realm = True
    state.hp = 28
    state.max_hp = 28
    state.max_hp_known = True
    state.room = "Newhaven, Arena"
    state.exits = ["u"]
    state.scanned = True
    state.mobs = ["acid slime"]
    return state


def test_f8_toggles_ninja_stealth() -> None:
    brain = Brain(allowed=True, klass="ninja", stealth="always")
    kind, brain, pacer, _ = _special(
        _CLIENT.KEY_F8, in_realm=True, hunting=True, brain=brain
    )
    assert kind == "ambush"
    assert brain.stealth == "walk"
    assert brain.stealth_label() == "walk"
    assert brain.next_action == "ambush walk"
    assert brain.mode == "hunt"
    assert not pacer.pending()
    again, brain, _, _ = _special(
        _CLIENT.KEY_F8, in_realm=True, hunting=True, brain=brain
    )
    assert again == "ambush"
    assert brain.stealth == "always"
    assert brain.stealth_label() == "ambush"
    assert brain.next_action == "ambush always"


def test_f8_walk_to_ambush_sns_on_empty_road() -> None:
    brain = Brain(allowed=True, klass="ninja", stealth="walk", me="klymacks")
    kind, brain, pacer, _ = _special(
        _CLIENT.KEY_F8,
        in_realm=True,
        hunting=True,
        brain=brain,
        state=_road(),
    )
    assert kind == "ambush"
    assert brain.stealth == "always"
    assert brain.stealth_label() == "ambush"
    assert brain.mode == "hunt"
    lines = _drain(pacer)
    assert any(ln.endswith(b"sn\r") for ln in lines)
    assert not any(ln.endswith(b"u\r") for ln in lines)
    assert brain._sneak_wait
    assert brain.next_action == "sn"


def test_f8_walk_to_ambush_pit_slime_goes_up() -> None:
    brain = Brain(allowed=True, klass="ninja", stealth="walk", me="klymacks")
    brain._in_camp = True
    kind, brain, pacer, _ = _special(
        _CLIENT.KEY_F8,
        in_realm=True,
        hunting=True,
        brain=brain,
        state=_pit_slime(),
    )
    assert kind == "ambush"
    assert brain.stealth == "always"
    assert brain.mode == "hunt"
    lines = _drain(pacer)
    assert any(ln.endswith(b"u\r") for ln in lines)
    assert not any(ln.endswith(b"sn\r") for ln in lines)
    assert not brain._sneak_wait


def test_f8_ambush_to_walk_no_sn() -> None:
    brain = Brain(allowed=True, klass="ninja", stealth="always", me="klymacks")
    kind, brain, pacer, _ = _special(
        _CLIENT.KEY_F8,
        in_realm=True,
        hunting=True,
        brain=brain,
        state=_road(),
    )
    assert kind == "ambush"
    assert brain.stealth == "walk"
    assert brain.stealth_label() == "walk"
    assert brain.mode == "hunt"
    assert not pacer.pending()
    assert not brain._sneak_wait
    assert not any(ln.endswith(b"sn\r") for ln in _drain(pacer))


def test_f8_walk_to_ambush_manual_sns() -> None:
    brain = Brain(allowed=True, klass="ninja", stealth="walk", me="klymacks")
    kind, brain, pacer, _ = _special(
        _CLIENT.KEY_F8,
        in_realm=True,
        hunting=False,
        brain=brain,
        state=_road(),
    )
    assert kind == "ambush"
    assert brain.mode == "manual"
    lines = _drain(pacer)
    assert any(ln.endswith(b"sn\r") for ln in lines)
    assert brain._sneak_wait


def test_f8_walk_to_ambush_sitting_breaks_then_sn() -> None:
    brain = Brain(allowed=True, klass="ninja", stealth="walk", me="klymacks")
    brain._sitting = True
    kind, brain, pacer, _ = _special(
        _CLIENT.KEY_F8,
        in_realm=True,
        hunting=True,
        brain=brain,
        state=_road(resting=True),
    )
    assert kind == "ambush"
    assert brain.mode == "hunt"
    lines = _cmds(pacer)
    assert len(lines) == 2
    assert lines[0].endswith(b"break\r")
    assert lines[1].endswith(b"sn\r")
    assert brain._sneak_wait


def test_f9_toggles_auto_join() -> None:
    brain = Brain(allowed=True, me="klymacks", party_leader="Matt")
    brain.mode = "hunt"
    brain.next_action = "lop"
    kind, brain, pacer, _ = _special(
        _CLIENT.KEY_F9, in_realm=True, hunting=True, brain=brain
    )
    assert kind == "join"
    assert brain.auto_join is False
    assert brain.join_label() == "join off"
    assert brain.mode == "hunt"
    assert not pacer.pending()
    again, brain, _, _ = _special(
        _CLIENT.KEY_F9, in_realm=True, hunting=True, brain=brain
    )
    assert again == "join"
    assert brain.auto_join is True
    assert brain.join_label() == "join"
    assert brain.mode == "hunt"


def test_maybe_auto_party_manual_join() -> None:
    brain = Brain(
        allowed=True, me="klymacks", party_leader="Matt", rank="back"
    )
    brain.mode = "manual"
    state = WorldState()
    state.in_realm = True
    state.apply({"kind": "invited", "name": "Matt"})
    sent: list[str] = []
    _CLIENT.maybe_auto_party(
        state, brain, sent.append, invited=True, followed=False
    )
    assert sent == ["join Matt"]
    state.apply({"kind": "following", "name": "Matt"})
    _CLIENT.maybe_auto_party(
        state, brain, sent.append, invited=False, followed=True
    )
    assert sent == ["join Matt", "backrank"]
    assert brain.mode == "hunt"


def test_maybe_auto_party_join_off_no_hunt() -> None:
    brain = Brain(
        allowed=True, me="klymacks", party_leader="Matt", rank="back"
    )
    brain.mode = "manual"
    brain.auto_join = False
    state = WorldState()
    state.in_realm = True
    state.apply({"kind": "following", "name": "Matt"})
    sent: list[str] = []
    _CLIENT.maybe_auto_party(
        state, brain, sent.append, invited=False, followed=True
    )
    assert sent == ["backrank"]
    assert brain.mode == "manual"


def test_maybe_auto_party_no_join_without_invite() -> None:
    brain = Brain(
        allowed=True, me="klymacks", party_leader="Matt", rank="back"
    )
    brain.mode = "manual"
    assert brain.auto_join
    state = WorldState()
    state.in_realm = True
    state.mobs = ["Matt"]
    sent: list[str] = []
    _CLIENT.maybe_auto_party(
        state, brain, sent.append, invited=False, followed=False
    )
    assert sent == []
    state.apply({"kind": "sneak_try"})
    _CLIENT.maybe_auto_party(
        state, brain, sent.append, invited=False, followed=False
    )
    assert sent == []


def test_f10_is_hold_does_not_takeover() -> None:
    kind, brain, pacer, _ = _special(
        _CLIENT.KEY_F10, in_realm=True, hunting=True
    )
    assert kind == "hold"
    assert brain.mode == "hunt"
    assert brain.next_action == "lop"
    assert not pacer.pending()
    again, brain, pacer, _ = _special(
        _CLIENT.KEY_F10, in_realm=True, hunting=True, brain=brain
    )
    assert again == "hold"
    assert brain.mode == "hunt"
    assert brain.next_action == "lop"
    assert not pacer.pending()


def test_f10_hold_outside_realm() -> None:
    kind, brain, pacer, _ = _special(_CLIENT.KEY_F10, in_realm=False)
    assert kind == "hold"
    assert brain.mode == "hunt"
    assert not pacer.pending()


def test_f11_is_sheet_does_not_takeover() -> None:
    kind, brain, pacer, _ = _special(
        _CLIENT.KEY_F11, in_realm=True, hunting=True
    )
    assert kind == "sheet"
    assert brain.mode == "hunt"
    assert not pacer.pending()


def test_toggle_sheet_sends_train_at_guild() -> None:
    state = WorldState()
    state.in_realm = True
    state.room = "Newhaven, Guild"
    brain = Brain(allowed=True, klass="ninja")
    brain.mode = "hunt"
    action, mud = _CLIENT.toggle_sheet(
        brain, state, locked=False, on_form=False
    )
    assert action == "lock"
    assert mud == "train"
    assert not brain._want_train


def test_toggle_sheet_walks_when_not_at_guild() -> None:
    state = WorldState()
    state.in_realm = True
    state.room = "Newhaven, Narrow Road"
    brain = Brain(allowed=True, klass="ninja")
    action, mud = _CLIENT.toggle_sheet(
        brain, state, locked=False, on_form=False
    )
    assert action == "walk"
    assert mud is None
    assert brain._want_train


def test_toggle_sheet_unlocks_and_cancels_walk() -> None:
    state = WorldState()
    state.in_realm = True
    state.room = "Newhaven, Narrow Road"
    brain = Brain(allowed=True, klass="ninja")
    brain.request_train()
    action, mud = _CLIENT.toggle_sheet(
        brain, state, locked=True, on_form=False
    )
    assert action == "unlock"
    assert mud is None
    assert not brain._want_train
    action, mud = _CLIENT.toggle_sheet(
        brain, state, locked=False, on_form=True
    )
    assert action == "unlock"


def test_sheet_lock_keeps_fsd_keys_with_leftover_hp() -> None:
    """Leftover [HP=] hides the form title. F11 lock still owns the keys."""
    screen = _CLIENT.AnsiScreen()
    screen.feed(b"\x1b[1;1HTRAIN STATS\r\nGiven Name\r\n")
    screen.feed(b"\x1b[25;1H[HP=28]: ")
    state = WorldState()
    state.in_realm = True
    state.hp = 28
    assert not screen.looks_like_creation()
    assert _CLIENT.use_local_input(screen, state)
    assert not _CLIENT.use_local_input(screen, state, sheet_lock=True)
    assert _CLIENT.form_frozen(screen, True)
    asked: list[str] = []
    assert not _CLIENT.maybe_ask_exp(state, asked.append, frozen=True)
    assert asked == []
    sent: list[str] = []
    _CLIENT.maybe_auto_party(
        state,
        Brain(allowed=True),
        sent.append,
        invited=True,
        followed=False,
        frozen=True,
    )
    assert sent == []


def test_hold_snapshot_writes_utf8_grid() -> None:
    screen = _CLIENT.AnsiScreen()
    screen.feed("Hello".encode("ascii") + bytes((0xC4,)))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "screen-hold.txt"
        wrote = _CLIENT.write_hold_snapshot(screen, path)
        assert wrote == path
        text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) == 25
    assert lines[0].startswith("Hello─")
    assert all(len(row) == 80 for row in lines)


def test_f8_paladin_noop() -> None:
    brain = Brain(allowed=True, klass="paladin", stealth="always")
    kind, brain, pacer, _ = _special(
        _CLIENT.KEY_F8, in_realm=True, hunting=True, brain=brain
    )
    assert kind == "ambush"
    assert brain.stealth == "always"
    assert brain.stealth_label() == ""
    assert brain.next_action == "ambush off"
    assert not pacer.pending()


def test_letter_is_not_special() -> None:
    kind, brain, pacer, _ = _special(b"x", in_realm=True)
    assert kind is None
    assert brain.mode == "hunt"
    assert not pacer.pending()


def test_help_overlay_lists_keys() -> None:
    raw = _CLIENT.help_overlay().decode("utf-8", "replace")
    assert "F1          panic" in raw
    assert "F2          look" in raw
    assert "F3          health" in raw
    assert "F4          inv" in raw
    assert "F5          exp" in raw
    assert "F6          who" in raw
    assert "F7          hunt / hunt off" in raw
    assert "F8          ambush / walk (ninja)" in raw
    assert "F9          join / join off" in raw
    assert "F10         hold / live" in raw
    assert "F11         train / live" in raw
    for n in range(1, 12):
        assert _CLIENT.fkey_label(n, style="help") in raw
    assert "peek - hunter stays on" in raw
    assert "same as F11" in raw
    assert "start / stop" not in raw
    assert "press to" not in raw.lower()
    drawn = []
    for part in raw.split("\x1b["):
        if "H" not in part:
            continue
        body = part.split("H", 1)[1]
        if body:
            drawn.append(body)
    assert drawn
    assert len({len(row) for row in drawn}) == 1, drawn


def test_fkey_table_feeds_tip_and_hold() -> None:
    on8 = _CLIENT.FKEYS[8]["on"]
    on9 = _CLIENT.FKEYS[9]["on"]
    hunt = _CLIENT.realm_fkey_tip(hunting=True, ambush=on8, join=on9)
    idle = _CLIENT.realm_fkey_tip(
        hunting=False, ambush=_CLIENT.FKEYS[8]["off"], join=_CLIENT.FKEYS[9]["off"]
    )
    assert _CLIENT.fkey_label(1) in hunt
    assert _CLIENT.fkey_label(7, active=True) in hunt
    assert _CLIENT.fkey_label(7, active=False) in idle
    assert _CLIENT.fkey_label(10) in hunt
    assert _CLIENT.fkey_label(10, held=True) == _CLIENT.FKEYS[10]["held"]
    live = _CLIENT.fkey_label(10, style="hold_tip", copied=False)
    copied = _CLIENT.fkey_label(10, style="hold_tip", copied=True)
    assert _CLIENT.FKEYS[10]["held"] in live
    assert _CLIENT.fkey_label(10, active=False) in live
    assert "Ctrl+V" in copied


def test_window_title_is_distinct() -> None:
    kly = _CLIENT.window_title({"given": "Klymacks", "username": "klymacks"})
    matt = _CLIENT.window_title({"given": "Matt", "username": "sysop"})
    empty_given = _CLIENT.window_title({"given": "", "username": "klymacks"})
    assert kly == "Finn's Realm — klymacks"
    assert matt == "Finn's Realm — Matt"
    assert empty_given == "Finn's Realm — klymacks"
    assert "Klymacks" not in kly
    osc = _CLIENT.osc_set_title(matt)
    assert osc.startswith(b"\x1b]0;")
    assert osc.endswith(b"\x07")
    assert b"Matt" in osc
    assert _CLIENT.osc_set_title("") == b""
    assert _CLIENT.osc_set_title("   ") == b""


def test_chrome_lists_new_map() -> None:
    screen = _CLIENT.AnsiScreen()
    state = WorldState()
    state.in_realm = True
    state.hp = 20
    state.max_hp = 20
    brain = Brain(allowed=True, klass="ninja", stealth="always")
    brain.mode = "hunt"
    bar = _CLIENT.chrome(30, screen, "x", "127.0.0.1", state, brain)
    text = bar.decode("utf-8", "replace")
    assert "F1 panic" in text
    assert "F2 look" in text
    assert "F3 hp" in text or "F3 health" in text
    assert "F4 inv" in text
    assert "F5 exp" in text
    assert "F6 who" in text
    assert "F7 hunt" in text
    assert "F7 hunt off" not in text
    assert "F8 ambush" in text
    assert "F9 join" in text
    assert "F10 hold" in text
    assert "F7/stop" not in text
    assert "HOLD" not in _plain_bar(bar)
    assert "next:" in text and "ambush" in text
    assert "F2 hunt" not in text
    brain.mode = "manual"
    brain.stealth = "walk"
    brain.auto_join = False
    bar = _CLIENT.chrome(30, screen, "x", "127.0.0.1", state, brain)
    text = bar.decode("utf-8", "replace")
    assert "F7 hunt off" in text
    assert "F8 walk" in text
    assert "F9 join off" in text
    assert "F10 hold" in text
    assert "F1 panic" in text
    held_bar = _CLIENT.chrome(30, screen, "x", "127.0.0.1", state, brain, held=True)
    held_text = held_bar.decode("utf-8", "replace")
    assert "HOLD" in _plain_bar(held_bar)
    assert "F10 live" in held_text
    assert "F10 resume" not in held_text
    assert "data/screen-hold.txt" in held_text
    copied_bar = _CLIENT.chrome(
        30, screen, "x", "127.0.0.1", state, brain, held=True, hold_copied=True
    )
    copied_text = copied_bar.decode("utf-8", "replace")
    assert "Ctrl+V" in copied_text
    assert "copied" in copied_text


def test_copy_hold_clipboard_returns_bool() -> None:
    ok = _CLIENT.copy_hold_clipboard("finn hold")
    assert ok in {True, False}


def test_autopilot_stops_when_already_logged_in() -> None:
    pacer = _CLIENT.KeyPacer()
    pacer.push_text("sysop")
    pilot = _CLIENT.Autopilot({"username": "sysop", "password": "sysop"}, play=True)
    pilot.phase = "pass"
    text = "sysop is already logged in -- only 1 connection allowed per user.\nUsername: "
    pilot.tick(text, pacer)
    assert pilot.phase == "blocked"
    assert not pacer.pending()
    assert "already logged in" in pilot.hint()


def test_chrome_tips_fit() -> None:
    hunt = _CLIENT.realm_fkey_tip(hunting=True, ambush="ambush", join="join")
    idle = _CLIENT.realm_fkey_tip(hunting=False, ambush="walk", join="join")
    paladin = _CLIENT.realm_fkey_tip(hunting=True, ambush="", join="join")
    idle_off = _CLIENT.realm_fkey_tip(
        hunting=False, ambush="walk", join="join off"
    )
    hunt_off = _CLIENT.realm_fkey_tip(
        hunting=True, ambush="ambush", join="join off"
    )
    assert len(hunt) <= 80, hunt
    assert len(idle) <= 80, idle
    assert len(paladin) <= 80, paladin
    assert len(idle_off) <= 80, idle_off
    assert len(hunt_off) <= 80, hunt_off
    assert "F7 hunt" in hunt
    assert "F7 hunt off" not in hunt
    assert "F9 join" in hunt
    assert "F7 hunt off" in idle
    assert "F9 join off" in idle_off
    assert "F7 hunt off" in idle_off
    assert "F7 hunt" in paladin
    assert "F7 hunt off" not in paladin


def _plain_bar(bar: bytes) -> str:
    return _CLIENT._SGR_RE.sub("", bar.decode("utf-8", "replace"))


def _chrome_for(state: WorldState, klass: str = "ninja") -> bytes:
    screen = _CLIENT.AnsiScreen()
    brain = Brain(allowed=True, klass=klass, stealth="always")
    brain.mode = "hunt"
    return _CLIENT.chrome(30, screen, "x", "127.0.0.1", state, brain)


def test_chrome_hp_tone() -> None:
    ok = WorldState()
    ok.in_realm = True
    ok.hp = 20
    ok.max_hp = 20
    ok.max_hp_known = True
    bar = _chrome_for(ok)
    text = bar.decode("utf-8", "replace")
    assert "HP 20/20" in _plain_bar(bar)
    assert _CLIENT.HP_RED_SGR not in text
    assert _CLIENT.HP_YELLOW_SGR not in text
    assert _CLIENT.hp_chrome_sgr(ok) == ""

    edge = WorldState()
    edge.in_realm = True
    edge.hp = 7
    edge.max_hp = 28
    edge.max_hp_known = True
    assert edge.hp_ratio() == 0.25
    assert _CLIENT.hp_chrome_sgr(edge) == ""

    low = WorldState()
    low.in_realm = True
    low.hp = 6
    low.max_hp = 28
    low.max_hp_known = True
    low.ma = 3
    low.max_ma = 8
    assert low.hp_ratio() is not None and low.hp_ratio() < 0.25
    assert _CLIENT.hp_chrome_sgr(low) == _CLIENT.HP_YELLOW_SGR
    yellow = _chrome_for(low).decode("utf-8", "replace")
    assert f"{_CLIENT.HP_YELLOW_SGR}HP 6/28{_CLIENT.CHROME_BODY_SGR}" in yellow
    assert "MA 3/8" in yellow
    assert f"{_CLIENT.HP_YELLOW_SGR}HP 6/28  MA" not in yellow
    body = _CLIENT.color_footer_hp(low.hp_label() + "  room", low)
    assert _CLIENT.visible_len(_CLIENT.pad_visible(body, 80)) == 80

    dead = WorldState()
    dead.in_realm = True
    dead.hp = -95
    dead.max_hp = 28
    dead.max_hp_known = True
    dead.ma = 8
    dead.max_ma = 8
    assert dead.hp_label() == "HP -95/28  MA 8/8"
    assert _CLIENT.hp_chrome_sgr(dead) == _CLIENT.HP_RED_SGR
    red = _chrome_for(dead).decode("utf-8", "replace")
    assert f"{_CLIENT.HP_RED_SGR}HP -95/28{_CLIENT.CHROME_BODY_SGR}" in red
    assert "MA 8/8" in red
    assert f"{_CLIENT.HP_RED_SGR}HP -95/28  MA" not in red
    assert "HP -95/28" in _CLIENT._SGR_RE.sub("", red)
    padded = _CLIENT.pad_visible(_CLIENT.color_footer_hp(dead.hp_label(), dead), 80)
    assert _CLIENT.visible_len(padded) == 80
    assert len(padded) > 80

    zero = WorldState()
    zero.hp = 0
    zero.max_hp = 28
    zero.max_hp_known = True
    assert _CLIENT.hp_chrome_sgr(zero) == _CLIENT.HP_YELLOW_SGR


def test_handle_client_line_train() -> None:
    state = WorldState()
    state.in_realm = True
    state.room = "Newhaven, Narrow Road"
    brain = Brain(allowed=True, klass="ninja")
    kind, mud = _CLIENT.handle_client_line("train", brain, state)
    assert kind == "train" and mud is None
    assert brain._want_train
    kind, mud = _CLIENT.handle_client_line("look", brain, state)
    assert kind == "game" and mud == "look"
    assert not brain._want_train
    brain.request_train()
    state.room = "Newhaven, Guild"
    kind, mud = _CLIENT.handle_client_line("train", brain, state)
    assert kind == "train" and mud == "train"
    assert not brain._want_train
    kind, mud = _CLIENT.handle_client_line("go train", brain, state)
    assert kind == "train" and mud == "train"


def test_maybe_ask_exp_once() -> None:
    state = WorldState()
    state.in_realm = True
    state.hp = 28
    sent: list[str] = []
    assert _CLIENT.maybe_ask_exp(state, sent.append)
    assert sent == ["exp"]
    assert state.exp_asked
    assert not _CLIENT.maybe_ask_exp(state, sent.append)
    assert sent == ["exp"]
    state.apply(
        {
            "kind": "level",
            "level": 1,
            "exp": 762,
            "needed": 1538,
            "next": 2300,
            "pct": 33,
        }
    )
    assert not state.needs_exp()
    state.apply({"kind": "experience", "amount": 40})
    state.apply({"kind": "killed", "name": "rat"})
    assert not state.needs_exp()
    sent.clear()
    assert not _CLIENT.maybe_ask_exp(state, sent.append)
    assert sent == []
    state.apply({"kind": "killed", "name": "rat"})
    assert not state.needs_exp()
    assert not _CLIENT.maybe_ask_exp(state, sent.append)
    assert sent == []
    state.in_combat = True
    state.exp_asked = False
    assert not _CLIENT.maybe_ask_exp(state, sent.append)


def test_hunt_ticks_do_not_resend_exp() -> None:
    """After a full Exp: line, hunt ticks and kills do not send `exp`."""
    state = WorldState()
    state.in_realm = True
    state.hp = 38
    state.max_hp = 38
    state.max_hp_known = True
    state.room = "Newhaven, Arena"
    state.scanned = True
    state.apply(
        parse_line("Exp: 4610 Level: 3 Exp needed for next level: 3823 (8433) [54%]")
    )
    assert state.has_exp_reading()
    assert not state.needs_exp()
    brain = Brain(allowed=True, me="klymacks", klass="ninja")
    brain.gear_done = True
    brain.mode = "hunt"
    brain._in_camp = True
    brain._asked_health = True
    sent: list[str] = []
    for _ in range(4):
        brain.tick(state, sent.append, pending=False)
        assert not _CLIENT.maybe_ask_exp(state, sent.append)
        state.prompt_seq += 1
    assert "exp" not in sent
    state.apply({"kind": "killed", "name": "giant rat"})
    assert not state.needs_exp()
    brain.tick(state, sent.append, pending=False)
    assert not _CLIENT.maybe_ask_exp(state, sent.append)
    assert "exp" not in sent
    assert not _CLIENT.maybe_ask_exp(state, sent.append)


def test_chrome_shows_exp_and_train() -> None:
    state = WorldState()
    state.in_realm = True
    state.hp = 28
    state.max_hp = 28
    state.max_hp_known = True
    state.apply(
        {
            "kind": "level",
            "level": 1,
            "exp": 762,
            "needed": 1538,
            "next": 2300,
            "pct": 33,
        }
    )
    text = _plain_bar(_chrome_for(state))
    assert "HP 28/28" in text
    assert "EXP 762/2300 33%" in text
    assert text.count("EXP ") == 1
    assert text.index("HP 28/28") < text.index("EXP 762/2300 33%")
    assert "TRAIN" not in text
    state.apply(
        {
            "kind": "level",
            "level": 1,
            "exp": 2300,
            "needed": 0,
            "next": 2300,
            "pct": 100,
        }
    )
    bar = _chrome_for(state)
    text = _plain_bar(bar)
    assert "TRAIN 100%" in text
    raw = bar.decode("utf-8", "replace")
    assert _CLIENT.HP_YELLOW_SGR in raw
    assert "F11 train" in text
    locked = _plain_bar(
        _CLIENT.chrome(
            30,
            _CLIENT.AnsiScreen(),
            "x",
            "127.0.0.1",
            state,
            Brain(allowed=True, klass="ninja"),
            sheet_lock=True,
        )
    )
    assert "SHEET" in locked
    assert "F11 live" in locked
    assert "no health/exp/hunt" in locked


def test_chrome_shows_hp_and_ma_over_max() -> None:
    state = WorldState()
    state.in_realm = True
    state.hp = 24
    state.max_hp = 28
    state.max_hp_known = True
    state.ma = 3
    state.max_ma = 8
    state.room = "Newhaven, Narrow Road"
    brain = Brain(allowed=True, klass="paladin")
    brain.mode = "hunt"
    brain.next_action = "fighting acid slime  ambush always"
    bar = _CLIENT.chrome(30, _CLIENT.AnsiScreen(), "x", "127.0.0.1", state, brain)
    text = _plain_bar(bar)
    assert "HP 24/28" in text
    assert "MA 3/8" in text
    state.apply(
        {
            "kind": "level",
            "level": 1,
            "exp": 762,
            "needed": 1538,
            "next": 2300,
            "pct": 33,
        }
    )
    crowded = _plain_bar(
        _CLIENT.chrome(30, _CLIENT.AnsiScreen(), "x", "127.0.0.1", state, brain)
    )
    assert crowded.index("HP 24/28") < crowded.index("EXP 762/2300 33%")
    assert crowded.count("EXP ") == 1


def test_realm_prompt_drops_sheet_mask() -> None:
    """Leftover TRAIN STATS / creation text must not star-mask the > bar."""
    screen = _CLIENT.AnsiScreen()
    screen.feed(b"\x1b[2J\x1b[1;1H")
    screen.feed(b"M A J O R  M U D Character Creation\r\n")
    screen.feed(b"Given Name   klymacks\r\n")
    screen.feed(b"Point Cost Chart\r\n")
    state = WorldState()
    state.in_realm = True
    state.hp = 28
    state.max_hp = 28
    state.max_hp_known = True
    assert screen.looks_like_creation()
    assert not _CLIENT.use_local_input(screen, state)
    assert _CLIENT.status_line(screen, "127.0.0.1") == "character sheet"

    screen.fg, screen.bold, screen.rev = 1, True, True
    # Form leftovers stay; realm prompt overlays — same as a live EXIT.
    screen.feed(b"\x1b[24;1H[HP=28]: ")
    blob = screen.text()
    assert "Character Creation" in blob
    assert "Given Name" in blob
    assert "[HP=" in blob
    assert not screen.looks_like_creation()
    assert _CLIENT.use_local_input(screen, state)
    screen.leave_form()
    assert (screen.fg, screen.bg, screen.bold, screen.rev) == (7, 0, False, False)
    assert _CLIENT.status_line(screen, "127.0.0.1") == "in the realm"

    brain = Brain(allowed=True, klass="ninja")
    bar = _CLIENT.chrome(30, screen, "", "127.0.0.1", state, brain, typed="north")
    plain = _plain_bar(bar)
    assert "> north" in plain
    assert "*****" not in plain
    assert _CLIENT.realm_bar_text("north") == "north"

    train = _CLIENT.AnsiScreen()
    train.feed(b"\x1b[1;1HTRAIN STATS\r\nGiven Name\r\n")
    assert train.looks_like_creation()
    assert not _CLIENT.use_local_input(train, state)
    train.feed(b"\x1b[25;1H[HP=28]: ")
    assert not train.looks_like_creation()
    assert _CLIENT.use_local_input(train, state)


if __name__ == "__main__":
    test_f2_sequences()
    test_f1_sequences()
    test_f3_to_f8_sequences()
    test_esc_o_waits()
    test_peek_commands()
    test_peek_does_not_stop_hunter()
    test_peek_all_keys_queue()
    test_peek_skipped_outside_realm()
    test_peek_queues_behind_pending()
    test_realm_line_shortens_attack()
    test_f7_toggles_hunt()
    test_f2_is_look_not_hunt()
    test_f1_panic_party_break_only()
    test_f1_panic_leader_with_followers_stays()
    test_f1_panic_solo_pit_break_then_u()
    test_f1_panic_does_not_takeover_or_reaggro()
    test_f1_leader_hurt_does_not_pit_flee()
    test_f1_panic_matt_mortal_rescues()
    test_f1_party_tick_does_not_flee()
    test_f1_skipped_outside_realm()
    test_f8_toggles_ninja_stealth()
    test_f8_walk_to_ambush_sns_on_empty_road()
    test_f8_walk_to_ambush_pit_slime_goes_up()
    test_f8_ambush_to_walk_no_sn()
    test_f8_walk_to_ambush_manual_sns()
    test_f8_walk_to_ambush_sitting_breaks_then_sn()
    test_f9_toggles_auto_join()
    test_maybe_auto_party_manual_join()
    test_maybe_auto_party_join_off_no_hunt()
    test_maybe_auto_party_no_join_without_invite()
    test_f10_is_hold_does_not_takeover()
    test_f10_hold_outside_realm()
    test_f11_is_sheet_does_not_takeover()
    test_toggle_sheet_sends_train_at_guild()
    test_toggle_sheet_walks_when_not_at_guild()
    test_toggle_sheet_unlocks_and_cancels_walk()
    test_sheet_lock_keeps_fsd_keys_with_leftover_hp()
    test_hold_snapshot_writes_utf8_grid()
    test_copy_hold_clipboard_returns_bool()
    test_f8_paladin_noop()
    test_letter_is_not_special()
    test_help_overlay_lists_keys()
    test_fkey_table_feeds_tip_and_hold()
    test_window_title_is_distinct()
    test_chrome_lists_new_map()
    test_autopilot_stops_when_already_logged_in()
    test_chrome_tips_fit()
    test_chrome_hp_tone()
    test_handle_client_line_train()
    test_maybe_ask_exp_once()
    test_hunt_ticks_do_not_resend_exp()
    test_chrome_shows_exp_and_train()
    test_chrome_shows_hp_and_ma_over_max()
    test_realm_prompt_drops_sheet_mask()
    print("ok")
