"""Play MajorMUD: gear up, hunt lops, rest. Localhost only."""

from __future__ import annotations

import time

from . import paths, realm_map, spells
from .state import WorldState

REST_RATIO = 0.60
# klymacks ninja party (following Matt): sit-down rest under 75%.
PARTY_REST_RATIO = 0.75
REST_ABS = 12
# Self-heal and party `heal me` (spoken — not the `health` command) at this
# ratio or below. Sit-down rest stays on REST_RATIO (or PARTY_REST_RATIO
# while a ninja is following).
HEAL_RATIO = 0.80
HEAL_ASK = "heal me"
# Last-ditch harm on a living target already in the fight. Trash is never a boss.
HARM_DESPERATE = 0.30
_ARENA_TRASH = paths.LOPS + ("bug",)
ALLY_HP_ASSUME = 28
LOOK_GAP = 12.0
PANIC_HOLD = 2.5
# `Attempting to sneak...` is not ready. `d` on that prompt breaks sneak.
# A couple of seconds is enough — not a full combat round.
SNEAK_SETTLE = 2.0


def _trusted_live(state: WorldState) -> str | None:
    """Listed lops are live. A look in flight must not hide them."""
    return paths.lop_in(state.mobs)


def _is_trash(name: str) -> bool:
    """Newhaven / arena fodder: rats, bugs, worms, slimes, kobolds, …"""
    low = name.lower()
    return any(word in low for word in _ARENA_TRASH)


def _still_here(state: WorldState, name: str) -> str | None:
    """Return the swing name if that farm mob is still listed here."""
    if not name:
        return None
    for mob in state.mobs:
        if paths.same_mob(mob, name) and paths.lop_in([mob]):
            return paths.attack_name(mob) or None
    return None


class Brain:
    def __init__(
        self,
        allowed: bool,
        rest_ratio: float = REST_RATIO,
        pvp: bool = False,
        me: str = "",
        alts: str = "",
        party_leader: str = "",
        rank: str = "",
        klass: str = "",
        spell_list: object = None,
        ambush: str = "stand",
        stealth: str = "",
        atlas: realm_map.Atlas | None = None,
        auto_join: bool = True,
        aa: bool | None = None,
    ) -> None:
        self.allowed = allowed
        self.rest_ratio = rest_ratio
        self.pvp = pvp
        self.me = me.strip().lower()
        self._aka = {
            part
            for part in f"{me} {alts}".replace(",", " ").split()
            if part
        }
        self.leader = party_leader.strip()
        self.rank = rank.strip().lower()
        self.auto_join = bool(auto_join)
        self._joined = False
        self._followed = False
        self._ranked = False
        self._invited = False
        self._got_invite = False
        self._party_at = 0.0
        self.bail = ""
        self.mode = "manual"
        self.next_action = "manual"
        self.gear_done = False
        self._skip_sell: set[str] = set()
        self._await_inv = False
        self._pry_sent = False
        self._inv_seen = 0
        self._inv_after = 0
        self._i_prompt = 0
        self._selling = ""
        self._looked = False
        self._armour_i = 0
        self._wearing = False
        self._weapon_bought = False
        self._weapon_worn = False
        self._torch_bought = False
        self._tried_torch = False
        self._wait_prompt = 0
        self._sent_at = 0.0
        self._attacking = ""
        self._last_verb = ""
        self._last_aim = ""
        self._in_camp = False
        self._sitting = False
        self._want_look = False
        self._asked_health = True
        self._realm_maxes = False
        self._last_step = ""
        self._step_room = ""
        self.klass = klass.strip().lower()
        # Open the next lop unless this is a ninja (hunt still swings / backstabs).
        self.aa = (self.klass != "ninja") if aa is None else bool(aa)
        self._spells = spells.known_spells(self.klass, spell_list)
        self._learn = spells.shop_spells(self.klass, spell_list)
        self._spells_shopped = not bool(self._learn)
        self._spell_i = 0
        self._spell_buying = False
        self._spell_reading = False
        self._spell_alt = False
        self._last_cast = ""
        self._cast_at = 0.0
        # Bless is owned at buy; do not recast until level changes after a refuse.
        self._bless_hold: int | None = None
        self._sneaking = False
        self._sneak_wait = False
        self._sneak_armed = False
        self._sneak_flop = False
        self._sneak_block = False
        self._sneak_ready_at = 0.0
        self._ambush_boot = False
        self._boot_looked = False
        self._boot_asked = False
        self._boot_plan: list[str] = []
        self._ambush_out = False
        self._pit_fight = False
        self._drop_scan = False
        self._evaded = False
        self._need_break = False
        self._need_swing = False
        mode = ambush.strip().lower()
        self.ambush = "inout" if mode == "inout" else "stand"
        want = (stealth or "").strip().lower()
        if not want:
            if mode in {"always", "sneak", "on", "stand", "inout"}:
                want = "always"
            elif mode in {"walk", "regular", "off"}:
                want = "walk"
            else:
                want = "auto"
        if want in {"always", "sneak", "on"}:
            self.stealth = "always"
        elif want in {"walk", "regular", "off"}:
            self.stealth = "walk"
        else:
            self.stealth = "auto"
        self._atlas = atlas if atlas is not None else realm_map.Atlas()
        self._hidden = False
        self._pending_step = ""
        self._panic_until = 0.0
        self._rescue = ""
        self._rescue_who = ""
        self._drag_on = False
        self._recovering = False
        self._want_train = False
        self._train_hold = False
        self._asked_heal = False
        self._asked_heal_hp: int | None = None

    def _clear_rescue(self) -> None:
        self._rescue = ""
        self._rescue_who = ""
        self._drag_on = False
        self._recovering = False

    def toggle_hunt(self) -> None:
        if not self.allowed:
            self.next_action = "hunter stays on localhost"
            return
        if self.mode in ("hunt", "gear", "rest"):
            self.mode = "manual"
            self.next_action = "manual"
            self._attacking = ""
            self._last_verb = ""
            self._last_aim = ""
            self._sitting = False
            self._want_look = False
            self._sneaking = False
            self._sneak_wait = False
            self._sneak_armed = False
            self._sneak_flop = False
            self._sneak_block = False
            self._sneak_ready_at = 0.0
            self._clear_ambush_boot()
            self._ambush_out = False
            self._pit_fight = False
            self._drop_scan = False
            self._evaded = False
            self._need_break = False
            self._need_swing = False
            self._hidden = False
            self._pending_step = ""
            self._panic_until = 0.0
            self._clear_rescue()
            return
        self._start_hunt()
        # Keep follow/rank — F7 while following should swing, not re-party.

    def _start_hunt(self) -> None:
        """Turn hunt on. Never toggles off — join/backrank must not go manual."""
        if not self.allowed:
            self.next_action = "hunter stays on localhost"
            return
        if self.mode in ("hunt", "gear", "rest"):
            return
        # Already following: combat loop, not the shop. F7 on a fresh
        # toon still starts gear.
        self.mode = "gear" if not self.gear_done and not self._followed else "hunt"
        self.next_action = self.mode
        self._asked_health = False
        self._panic_until = 0.0
        self._want_train = False
        self._train_hold = False
        if self.mode == "gear":
            self._await_inv = True
            self._pry_sent = False
            self._wait_prompt = 0
            self._last_step = ""
            self._looked = True
            self.next_action = "i"
        elif self._stealth_moves() and not self._followed:
            self._begin_ambush_boot()

    def open_gear_inv(self, state: WorldState) -> str | None:
        """F7 / hunt: send `i` now so gear does not wait for a refresh."""
        if self.mode != "gear" or self._pry_sent:
            return None
        if self._listed_fight(state):
            self._done_gear()
            return None
        self._pry_sent = True
        self._await_inv = True
        self._inv_after = state.inv_seq
        self._i_prompt = state.prompt_seq
        self._wait_prompt = state.prompt_seq + 1
        self._sent_at = time.monotonic()
        self.next_action = "i"
        return "i"

    def takeover(self) -> None:
        self.mode = "manual"
        self.next_action = "manual"
        self._attacking = ""
        self._last_verb = ""
        self._last_aim = ""
        self._want_look = False
        self._sitting = False
        self._sneaking = False
        self._sneak_wait = False
        self._sneak_armed = False
        self._sneak_flop = False
        self._sneak_block = False
        self._sneak_ready_at = 0.0
        self._clear_ambush_boot()
        self._ambush_out = False
        self._pit_fight = False
        self._drop_scan = False
        self._evaded = False
        self._need_break = False
        self._need_swing = False
        self._hidden = False
        self._pending_step = ""
        self._panic_until = 0.0
        self._want_train = False
        self._train_hold = False
        self._clear_rescue()

    def hunting(self) -> bool:
        return self.mode != "manual"

    def _me(self, name: str) -> bool:
        tokens = [w.strip(".,!;:").lower() for w in name.split() if w.strip(".,!;:")]
        mine = {part for part in self.me.replace(",", " ").split() if part}
        return any(token in mine for token in tokens)

    def _mine(self, name: str, state: WorldState | None = None) -> bool:
        extras = set(self._aka)
        if state:
            extras |= state.self_names
        return paths.is_self(name, extras)

    def _remember_self(self, state: WorldState) -> None:
        who = state.last_actor.strip()
        state.last_actor = ""
        if not who:
            return
        if not (self._attacking or self._sitting or state.resting or state.in_combat):
            return
        if paths.is_player(who) or paths.is_home_account(who):
            low = who.lower()
            self._aka.add(low)
            state.self_names.add(low)

    def _leading(self) -> bool:
        if not self.leader:
            return True
        mine = {part for part in self.me.replace(",", " ").split() if part}
        return self.leader.lower() in mine

    def _following(self) -> bool:
        return bool(self.leader) and not self._leading()

    def _leader_down(self, state: WorldState) -> bool:
        """Leader is mortal or we are mid-rescue — we may move on our own."""
        if not self.leader:
            return True
        if self._rescue and self._same_toon(self._rescue_who, self.leader):
            return True
        who = state.ally_mortal.strip()
        return bool(who and self._same_toon(who, self.leader))

    def _with_leader(self, state: WorldState) -> bool:
        """Following Matt: no own `u` / `d`. Ninja party still sns and bs."""
        if self._leader_down(state):
            return False
        return bool(self._followed or state.following)

    def _ninja_party(self, state: WorldState) -> bool:
        """Default klymacks party: follow, backrank, rest/heal, sn until hidden, bs."""
        return self._ninja() and self._with_leader(state)

    def _stealthed(self) -> bool:
        return bool(self._hidden or self._sneaking)

    def _own_ambush(self, state: WorldState) -> bool:
        """Solo sneak-and-move. Gear walks in the open. Party sneak is `_ninja_party`."""
        if self.mode == "gear":
            return False
        return self._stealth_moves() and not self._with_leader(state)

    def _pvp_sense(self, state: WorldState) -> bool:
        if not state.friendly_fire:
            return False
        self.bail = f"hit {paths.attack_name(state.friendly_fire)}"
        self.takeover()
        self.next_action = "logoff"
        return True

    def _ninja(self) -> bool:
        return self.klass == "ninja"

    def _paladin(self) -> bool:
        return self.klass in {"paladin", "pal"}

    def _stealth_moves(self) -> bool:
        if not self._ninja():
            return False
        if self.stealth == "always":
            return True
        if self.stealth == "walk":
            return False
        return not self._followed

    def toggle_stealth(self) -> str:
        if not self._ninja():
            self.next_action = "ambush off"
            return "walk"
        self.stealth = "walk" if self._stealth_moves() else "always"
        self.next_action = f"ambush {self.stealth}"
        return self.stealth

    def _clear_ambush_boot(self) -> None:
        self._ambush_boot = False
        self._boot_looked = False
        self._boot_asked = False
        self._boot_plan = []

    def _begin_ambush_boot(self) -> None:
        """F7 hunt / F8 ambush-on: look before sn, bs, attack, or leaving."""
        self._ambush_boot = True
        self._boot_looked = False
        self._boot_asked = False
        self._boot_plan = []
        self._need_break = False
        self._sneak_wait = False
        self._sneak_armed = False
        self._sneak_flop = False
        self._sneak_block = False
        self._sneak_ready_at = 0.0

    def _queue_boot_look(self, send, state: WorldState) -> None:
        if self._boot_asked:
            return
        self._boot_asked = True
        state.look_scan = True
        state.saw_here = False
        state.saw_see = False
        self._cmd(send, "look", state)

    def on_ambush_on(self, state: WorldState) -> list[str]:
        """Commands to pace when F8 turns ambush on. No takeover.

        Own ambush: `look` first unless Also here already listed the room.
        A listed lop is a fight — do not leave to sneak. Empty room: one
        `sn`. Following Matt: `sn` only on an empty room; do not walk off
        with u/s.
        """
        cmds: list[str] = []

        def collect(text: str) -> None:
            cmds.append(text)

        if not self._ninja() or not state.in_realm:
            return cmds
        if self._with_leader(state):
            if not self._ninja_party(state) or state.in_combat or self._lops_here(state):
                return cmds
            if self._down(state):
                self._sitting = False
                self._cmd(collect, "break", state)
                self._cmd(collect, "sn", state)
                self._sneak_wait = True
                return cmds
            if self._send_sneak(collect, state):
                self._sneak_wait = True
            return cmds
        if not self._stealth_moves():
            return cmds
        self._begin_ambush_boot()
        self._queue_boot_look(collect, state)
        return cmds

    def _run_ambush_boot(self, state: WorldState, send) -> bool:
        """Own ambush start: look if the listing is stale, else sn or fight."""
        if not self._ambush_boot:
            return False
        if not self._ninja() or not self._stealth_moves() or self._with_leader(state):
            self._clear_ambush_boot()
            return False
        if self._boot_plan:
            return self._boot_next(state, send)
        if self._lops_here(state) and (state.saw_here or self._boot_looked):
            self._clear_ambush_boot()
            return False
        if not self._boot_looked:
            if state.saw_here:
                self._boot_looked = True
            elif self._boot_asked:
                if state.look_scan:
                    self.next_action = "looking"
                    return True
                self._boot_looked = True
            else:
                self._queue_boot_look(send, state)
                return True
        if self._stealthed():
            self._clear_ambush_boot()
            return False
        if self._lops_here(state):
            self._clear_ambush_boot()
            return False
        if self._down(state):
            self._sitting = False
            self._cmd(send, "break", state)
            self._boot_plan = ["sn"]
            return True
        if self._send_sneak(send, state):
            self._sneak_wait = True
        self._clear_ambush_boot()
        return True

    def _boot_next(self, state: WorldState, send) -> bool:
        if not self._boot_plan:
            self._clear_ambush_boot()
            return False
        cmd = self._boot_plan.pop(0)
        if cmd == "break":
            self._sitting = False
            self._attacking = ""
            state.in_combat = False
            self._need_break = False
            self._cmd(send, "break", state)
            return True
        if cmd == "sn":
            if self._down(state):
                self._boot_plan.insert(0, "sn")
                self._sitting = False
                self._cmd(send, "break", state)
                return True
            if self._send_sneak(send, state):
                self._sneak_wait = True
            self._clear_ambush_boot()
            return True
        if cmd == "u":
            self._cmd(send, "u", state)
            self._need_break = False
            return True
        if cmd == "s":
            self._cmd(send, "s", state)
            self._need_break = False
            self._clear_ambush_boot()
            return True
        self._cmd(send, cmd, state)
        if not self._boot_plan:
            self._clear_ambush_boot()
        return True

    def stealth_label(self) -> str:
        if not self._ninja():
            return ""
        return "ambush" if self._stealth_moves() else "walk"

    def aa_label(self) -> str:
        return "aa" if self.aa else "aa off"

    def f8_label(self) -> str:
        """F8 word: ninja ambush/walk, else aa / aa off."""
        if self._ninja():
            return self.stealth_label()
        return self.aa_label()

    def toggle_aa(self) -> bool:
        """Flip paladin auto-swing. Ninja F8 is ambush — do not call this."""
        self.aa = not self.aa
        self.next_action = self.aa_label()
        return self.aa

    def _opens_swing(self, state: WorldState) -> bool:
        """Start a new swing. Ninja hunt always; paladin follows `aa` (bash)."""
        if self._ninja() or state.in_combat or self._attacking:
            return True
        return self.aa

    def toggle_auto_join(self) -> bool:
        """Flip invite auto-join. No takeover — works while hunting or manual."""
        self.auto_join = not self.auto_join
        self.next_action = "join" if self.auto_join else "join off"
        return self.auto_join

    def join_label(self) -> str:
        return "join" if self.auto_join else "join off"

    def _same_toon(self, left: str, right: str) -> bool:
        a = left.strip().lower()
        b = right.strip().lower()
        if not a or not b:
            return False
        if a == b:
            return True
        return a in b.split() or b in a.split()

    def on_invite(self, state: WorldState, send) -> bool:
        """Join a follow invite even in manual. Hunt tick is not required."""
        if not self.allowed or not self.auto_join or not state.in_realm:
            return False
        if self._rescue or state.ally_mortal:
            return False
        self._sync_party(state)
        who = state.invited_by.strip()
        if not who or self._me(who):
            return False
        if state.following and self._same_toon(state.following, who):
            return False
        if self.leader and not self._same_toon(self.leader, who):
            return False
        now = time.monotonic()
        if self._party_at and now - self._party_at < 6:
            return False
        self._got_invite = True
        self._party_at = now
        self._cmd(send, f"follow {who}", state)
        return True

    def on_follow(self, state: WorldState, send) -> bool:
        """backrank after following, including from manual. Then hunt with the party."""
        if not self.allowed or not state.in_realm:
            return False
        self._sync_party(state)
        if not (state.following or self._followed):
            return False
        sent = False
        if self.rank in {"back", "backrank"} and not self._ranked:
            self._ranked = True
            self._party_at = time.monotonic()
            self._cmd(send, "backrank", state)
            sent = True
        self._maybe_party_hunt(state)
        return sent

    def _maybe_party_hunt(self, state: WorldState) -> None:
        """After follow+backrank onto the configured leader, hunt without F7.

        F9 join-off does not start hunt. A random PC follow does not.
        Hunt already on stays on — never toggle off.
        """
        if not self.auto_join or not self.leader:
            return
        if self._leading():
            return
        who = (state.following or "").strip()
        if who and not self._same_toon(who, self.leader):
            return
        if not (state.following or self._followed):
            return
        if self.rank in {"back", "backrank"} and not self._ranked:
            return
        self._start_hunt()

    def _in_party(self, state: WorldState) -> bool:
        """Grouped with someone — do not unfollow or pit-flee away from them."""
        if state.following or self._followed:
            return True
        if self.leader and self._leading() and state.followers:
            return True
        return self._party_pending(state)

    def panic(self, state: WorldState, send) -> None:
        """Break autocombat and reset the heal lock. Stay in hunt.

        Matt down: start rescue (leave / drag / aid), then solo. Do not
        hold the hunter — after aid we hunt on our own until a real invite.
        Matt up and partied: break only — no `u`, no unfollow. A short hold
        stops an immediate re-aggro. Solo in the pit may `u` to the road.
        """
        self._attacking = ""
        self._sneak_wait = False
        self._sneak_armed = False
        self._sneaking = False
        self._sneak_flop = False
        self._sneak_block = False
        self._sneak_ready_at = 0.0
        self._ambush_out = False
        self._pit_fight = False
        self._drop_scan = False
        self._evaded = False
        self._need_break = False
        self._sitting = False
        state.in_combat = False
        self._last_cast = ""
        self._cast_at = 0.0
        self._panic_until = time.monotonic() + PANIC_HOLD
        self.next_action = "panic"
        self._want_train = False
        self._train_hold = False
        self._cmd(send, "break", state)
        if self._arm_leader_rescue(state) or self._rescue:
            self._panic_until = 0.0
            self.next_action = "rescue"
            return
        if self._in_party(state):
            return
        if self._in_pit(state):
            self._cmd(send, "u", state)

    def _inout(self) -> bool:
        return self._ninja() and self.ambush == "inout"

    def _note_sneak(self, state: WorldState) -> None:
        """Fail wins the payload. 1.11p is quiet on hide — no fail is success.

        `You don't think you're sneaking` / sound / not hidden → flop.
        `You may not sneak right now` → block `sn`. One `break` if needed,
        wait, then one `sn` — never a KEY_GAP storm.
        `Attempting` is not ready — wait SNEAK_SETTLE, then assume hidden.
        `Sneaking...` confirms immediately. try+fail together still fails.
        """
        failed = state.sneak_fail
        confirmed = state.sneak_ok
        tried = state.sneak_try
        busy = state.sneak_busy
        state.sneak_fail = False
        state.sneak_ok = False
        state.sneak_try = False
        state.sneak_busy = False
        if state.in_combat and not self._attacking:
            self._sneaking = False
            self._sneak_armed = False
            self._sneak_wait = False
            self._sneak_ready_at = 0.0
            self._hidden = False
        if failed:
            self._sneaking = False
            self._sneak_armed = False
            self._sneak_wait = False
            self._sneak_ready_at = 0.0
            self._hidden = False
            if busy:
                self._need_break = True
                self._sneak_block = True
                self._attacking = ""
                self._sneak_flop = False
            else:
                self._sneak_flop = True
                self._sneak_block = False
            return
        if confirmed:
            self._sneaking = True
            self._sneak_armed = False
            self._sneak_wait = False
            self._sneak_ready_at = 0.0
            self._sneak_flop = False
            self._sneak_block = False
            self._hidden = True
            return
        if tried:
            self._sneak_wait = False
            self._sneak_flop = False
            self._sneak_armed = True
            self._sneak_ready_at = time.monotonic() + SNEAK_SETTLE
            self._sneaking = False
        self._assume_sneak()

    def _assume_sneak(self) -> None:
        """Armed and settled with no fail line — treat as hidden. Do not wait forever."""
        if self._hidden or self._sneaking or self._sneak_flop:
            return
        if not self._sneak_armed or not self._sneak_settled():
            return
        self._sneaking = True
        self._hidden = True
        self._sneak_armed = False
        self._sneak_wait = False
        self._sneak_ready_at = 0.0

    def _swing_name(self, name: str) -> str:
        """Species swing name — `paths.attack_name`, nothing else."""
        return paths.attack_name(name)

    def _swing_verb(self, state: WorldState) -> str:
        """Hidden ninja `bs`. Paladin bash is `aa`. Else `att`. Never `k`."""
        if self._ninja() and self._stealthed():
            return "bs"
        if self._paladin():
            return "aa"
        return "att"

    def _strike(self, send, state: WorldState, aim: str) -> bool:
        aim = self._swing_name(aim)
        if not aim:
            return False
        if not _still_here(state, aim):
            return False
        self._attacking = aim.lower()
        self._need_swing = False
        state.in_combat = True
        self._pit_fight = True
        verb = self._swing_verb(state)
        if verb == "bs":
            self._sneaking = False
            self._sneak_armed = False
            self._sneak_wait = False
            self._hidden = False
            if self._inout():
                self._ambush_out = True
        self._sneak_wait = False
        self._cmd(send, f"{verb} {aim}", state)
        return True

    def _spell(self, kind: str) -> str:
        return spells.of_kind(self._spells, kind)

    def _have_mana(self, cost: int, state: WorldState) -> bool:
        if state.ma is None:
            return True
        return state.ma >= cost

    def _note_cast_fail(self, state: WorldState) -> None:
        reason = state.cast_fail
        state.cast_fail = ""
        buff = self._last_cast.startswith("buff:")
        if buff and state.spell_skip:
            state.spell_skip = False
            if not reason:
                reason = "level"
        if not reason:
            return
        tried = self._last_cast.split(":", 1)[-1] if self._last_cast else ""
        # Can't-cast-yet is not "don't have it." Keep bless (and other buffs).
        if reason == "unknown" and tried and not buff:
            self._spells = [name for name in self._spells if name != tried]
        if reason == "mana" and state.ma is None:
            state.ma = 0
        if buff:
            state.blessed = False
            if reason in {"level", "unknown", "fail"}:
                self._bless_hold = state.level if state.level is not None else 1
        self._last_cast = ""
        self._cast_at = 0.0

    def _spell_ready(self) -> bool:
        if not self._cast_at:
            return True
        return time.monotonic() - self._cast_at >= spells.ROUND

    def _heal_name(self, seen: str, state: WorldState) -> str:
        extras = self._aka | state.self_names
        aim = paths.party_name(seen, extras) or paths.attack_name(seen)
        if not aim:
            return ""
        first = aim.split()[0]
        if paths.is_dir_token(first) or paths.lop_in([aim]):
            return ""
        if not (
            paths.is_given_name(aim, extras)
            or paths.is_player(aim)
            or paths.is_home_account(aim)
        ):
            return ""
        if paths.is_home_account(aim):
            return aim.lower()
        return aim

    def _heal_allies_here(self, state: WorldState) -> list[str]:
        extras = self._aka | state.self_names
        found: list[str] = []
        seen_low: set[str] = set()
        for name in (
            *self._alts_here(state),
            *state.ally_hurt.values(),
            *state.heal_asks.values(),
        ):
            if not name or not self._mine(name, state) or self._me(name):
                continue
            key = (paths.party_name(name, extras) or name).lower()
            if key in seen_low:
                continue
            seen_low.add(key)
            found.append(name)
        return found

    def _ally_heal_gate(self) -> int:
        """Damage that puts assumed ally HP at or below HEAL_RATIO. Backup to `heal me`."""
        return max(1, ALLY_HP_ASSUME - int(ALLY_HP_ASSUME * HEAL_RATIO))

    def _ally_asked(self, state: WorldState, name: str) -> bool:
        extras = self._aka | state.self_names
        key = (paths.party_name(name, extras) or name).lower()
        return key in state.heal_asks or name.lower() in state.heal_asks

    def _ally_needs_heal(self, state: WorldState, name: str) -> bool:
        if self._ally_asked(state, name):
            return True
        extras = self._aka | state.self_names
        key = (paths.party_name(name, extras) or name).lower()
        taken = max(state.ally_taken(key), state.ally_taken(name))
        return taken >= self._ally_heal_gate()

    def _hurt_ally(self, state: WorldState) -> str | None:
        extras = self._aka | state.self_names
        dead = state.last_kill.lower()
        for name in self._heal_allies_here(state):
            key = (paths.party_name(name, extras) or name).lower()
            if dead and (key in dead or name.lower() in dead):
                continue
            asked = self._ally_asked(state, name)
            hurt = key in state.ally_hurt or name.lower() in state.ally_hurt
            if not asked and not hurt:
                continue
            if self._ally_needs_heal(state, name):
                return name
        return None

    def _try_ally_heal(self, state: WorldState, send, spell: str) -> bool:
        seen = self._hurt_ally(state)
        if not seen:
            return False
        target = self._heal_name(seen, state)
        if not target:
            return False
        cost = spells.cost(spell)
        reserve = cost if self._needs_heal(state) else 0
        if not self._have_mana(cost + reserve, state):
            return False
        extras = self._aka | state.self_names
        key = (paths.party_name(seen, extras) or seen).lower()
        state.forget_ally(key, seen, target)
        self._last_cast = f"heal:{spell}:{target}"
        self._cast_at = time.monotonic()
        self._cmd(send, spells.command(spell, target), state)
        return True

    def _clear_heal_ask(self) -> None:
        self._asked_heal = False
        self._asked_heal_hp = None

    def _heal_ask_cleared(self, state: WorldState) -> None:
        """Ask once until HP is back above HEAL_RATIO or a heal lands."""
        if not self._asked_heal:
            return
        if not self._needs_heal(state):
            self._clear_heal_ask()
            return
        hp = state.hp
        if hp is not None and self._asked_heal_hp is not None and hp > self._asked_heal_hp:
            self._clear_heal_ask()

    def _try_ask_heal(self, state: WorldState, send) -> bool:
        """Follower with no heal spell: speak `heal me` once at HEAL_RATIO or below."""
        if self._spell("heal"):
            return False
        if not self._with_leader(state):
            self._clear_heal_ask()
            return False
        self._heal_ask_cleared(state)
        if not self._needs_heal(state):
            return False
        if self._asked_heal:
            return False
        self._asked_heal = True
        self._asked_heal_hp = state.hp
        self._cmd(send, HEAL_ASK, state)
        return True

    def _try_heal(self, state: WorldState, send) -> bool:
        name = self._spell("heal")
        if not name:
            return self._try_ask_heal(state, send)
        if not self._spell_ready():
            return False
        if self._needs_heal(state):
            if not self._have_mana(spells.cost(name), state):
                return False
            self._last_cast = f"heal:{name}"
            self._cast_at = time.monotonic()
            self._cmd(send, spells.command(name), state)
            return True
        return self._try_ally_heal(state, send, name)

    def _harm_reason(self, state: WorldState, target: str) -> bool:
        """Boss kill-shot, or desperation. Never stacked Newhaven trash."""
        if not paths.is_living(target):
            return False
        if not _is_trash(target):
            return True
        ratio = state.hp_ratio()
        return ratio is not None and ratio < HARM_DESPERATE

    def _try_harm(self, state: WorldState, send, aim: str) -> bool:
        """Default never. Save MA for heals. Kill shot only, boss or desperate."""
        name = self._spell("harm")
        if not name or not aim:
            return False
        if self._opening(state):
            return False
        target = aim if paths.is_living(aim) else ""
        if not target:
            return False
        if not self._attacking or not paths.same_mob(self._attacking, target):
            return False
        if not self._harm_reason(state, target):
            return False
        if not self._spell_ready():
            return False
        heal = self._spell("heal") or "minor healing"
        reserve = 2 * spells.cost(heal)
        if not self._have_mana(spells.cost(name) + reserve, state):
            return False
        key = f"harm:{target.lower()}"
        if self._last_cast == key:
            return False
        self._last_cast = key
        self._cast_at = time.monotonic()
        self._cmd(send, spells.command(name, target), state)
        return True

    def _try_bless(self, state: WorldState, send) -> bool:
        """Self `cast bless` when hunt is idle. Not mid-swing. Heal wins the round."""
        name = self._spell("buff")
        if not name:
            return False
        if state.in_combat or self._attacking:
            return False
        if _trusted_live(state) or paths.lop_in(state.mobs):
            return False
        if self._want_look:
            return False
        if state.blessed:
            return False
        if not spells.can_cast(name, state.level):
            return False
        if self._bless_hold is not None and (
            state.level is None or state.level <= self._bless_hold
        ):
            return False
        if not self._spell_ready():
            return False
        if state.ma is None:
            return False
        heal = self._spell("heal") or "minor healing"
        reserve = 2 * spells.cost(heal)
        if not self._have_mana(spells.cost(name) + reserve, state):
            return False
        self._last_cast = f"buff:{name}"
        self._cast_at = time.monotonic()
        state.blessed = True
        self._cmd(send, spells.command(name), state)
        return True

    def _sync_maxes(self, state: WorldState) -> None:
        if state.trained:
            self._asked_health = False
            state.trained = False

    def _need_maxes(self, state: WorldState) -> bool:
        """Ask `health` for missing max HP, and for max MA only if we have a pool."""
        if state.hp is None:
            return False
        if not state.max_hp_known:
            return True
        if self._ninja():
            return False
        return state.ma is not None and state.max_ma is None

    def _ask_health(self, state: WorldState, send) -> bool:
        """Send `health` once when max HP/MA are unknown. Again after train."""
        self._sync_maxes(state)
        if not self._need_maxes(state) or self._asked_health:
            return False
        if state.in_combat or self._attacking:
            return False
        if self.mode != "manual" and (self._aim(state) or paths.lop_in(state.mobs)):
            return False
        self._asked_health = True
        self._cmd(send, "health", state)
        return True

    def _ask_exp(self, state: WorldState, send) -> bool:
        """Send `exp` once until chrome has current/total/percent. Never twice."""
        if not state.needs_exp():
            return False
        if state.in_combat or self._attacking:
            return False
        if self.mode != "manual" and (self._aim(state) or paths.lop_in(state.mobs)):
            return False
        if self.next_action == "exp":
            return False
        state.exp_asked = True
        self._cmd(send, "exp", state)
        return True

    def train_holding(self) -> bool:
        """Brain paused at the trainer. Keyboard stays with the player."""
        return self._train_hold

    def begin_train_hold(self) -> None:
        """Stop hunt/sneak/aa/party/gear/heal/look. Do not type train or stats."""
        self.takeover()
        self._train_hold = True
        self.next_action = "train hold"

    def request_train(self, state: WorldState | None = None) -> None:
        """Walk to the Newhaven guild, then pause. Never types train or stats."""
        if state is not None and paths.is_trainer(state.room):
            self.begin_train_hold()
            return
        self._want_train = True
        self._train_hold = False
        self.next_action = "train"

    def cancel_train(self) -> None:
        was_hold = self._train_hold
        self._want_train = False
        self._train_hold = False
        if was_hold:
            self.next_action = "manual"

    def _go_train(self, state: WorldState, send) -> bool:
        """Walk to the guild and wait. Leader owns movement. Do not spend points."""
        if self._train_hold:
            self.next_action = "train hold"
            return True
        if not self._want_train:
            return False
        if state.in_combat or self._attacking or self._lops_here(state):
            return False
        if state.mortal or state.bleeding:
            return False
        if paths.is_trainer(state.room):
            if self._down(state):
                self._sitting = False
                self._cmd(send, "break", state)
                return True
            self.begin_train_hold()
            return True
        if self._with_leader(state):
            return False
        if self._down(state):
            self._sitting = False
            self._cmd(send, "break", state)
            return True
        step = paths.step_toward_guild(state.room, state.exits)
        if not step:
            route = self._atlas.path(state.room, "Newhaven, Guild")
            if route:
                step = route[0]
                if state.exits and step not in state.exits:
                    step = ""
        if not step:
            self.next_action = "train"
            return False
        if step == self._last_step:
            self.next_action = "train"
            return True
        self._cmd(send, step, state)
        self.next_action = "train"
        return True

    def tick(self, state: WorldState, send, pending: bool, cancel=None) -> None:
        if not self.allowed:
            return
        if not state.in_realm:
            if self._train_hold:
                self.cancel_train()
            return
        if self._train_hold:
            if state.trained or not paths.is_trainer(state.room):
                self.cancel_train()
            else:
                self.next_action = "train hold"
                return
        if self.mode == "manual":
            if pending:
                return
            if not self._realm_maxes:
                self._asked_health = False
                self._realm_maxes = True
            if self._party(state, send):
                return
            if self._ask_health(state, send):
                return
            if self._run_ambush_boot(state, send):
                return
            if self._dump_extras(state, send):
                return
            if self._go_train(state, send):
                return
            if self._want_train and self._with_leader(state):
                self.next_action = "train (follow)"
                return
            self.next_action = "manual"
            return
        state.self_names |= self._aka
        self._remember_self(state)
        if self._pvp_sense(state):
            return
        self._note_cast_fail(state)
        self._note_sneak(state)
        self._assume_sneak()
        self._atlas.observe(state.room, state.exits, self._last_step, self._step_room)
        if state.saw_here or _trusted_live(state) or paths.lop_in(state.mobs):
            self._drop_scan = False
        # Kill / Off clear _last_aim. Keep the queued swing name so a late
        # `at giant rat` can be dropped after the corpse line.
        queued_aim = self._last_aim
        queued_verb = self._last_verb
        dead = state.last_kill
        self._resolve_fight(state)
        self._note_evasion(state)
        self._note_wound(state)
        if self.mode != "gear" and self._rescue_tick(state, send):
            return
        if self.mode != "gear" and self._party(state, send):
            return
        live_now = self._aim(state)
        aim_now = self._swing_name(live_now).lower() if live_now else ""
        engaged = bool(self._attacking or state.in_combat)
        new_mob = bool(live_now and aim_now != self._attacking and not engaged)
        stale_swing = self._queued_swing_gone(
            pending, queued_aim, queued_verb, dead, state
        )
        retarget = new_mob or stale_swing
        if pending:
            if retarget and cancel is not None and not self._party_pending(state):
                cancel()
            else:
                return
        if state.prompt_seq < self._wait_prompt:
            if retarget:
                self._wait_prompt = state.prompt_seq
            elif self.next_action == "health" and state.max_hp_known:
                # Hits after `health` is enough — do not idle for another prompt.
                self._wait_prompt = state.prompt_seq
            elif time.monotonic() - self._sent_at < 6:
                return
            else:
                self._wait_prompt = state.prompt_seq

        if self._break_after_leave(send, state):
            return

        if (
            state.geared
            and not self.gear_done
            and self._inv_has_light(state)
            and self._spells_shopped
        ):
            self._torch_bought = True
            self.gear_done = True
            if self.mode == "gear":
                self.mode = "hunt"

        listed = self._listed_fight(state)
        down = self._need_rest(state) or state.mortal or state.bleeding
        may_rest = (
            not self._with_leader(state)
            or self._ninja_party(state)
            or state.mortal
            or state.bleeding
            or self._recovering
        )
        if listed and self.mode == "gear":
            self._done_gear()
        if listed and self.mode == "rest" and not (state.mortal or state.bleeding):
            self.mode = "hunt"
        if down and self.mode != "rest" and may_rest:
            if self._try_heal(state, send):
                return
            if not (listed and not (state.mortal or state.bleeding)):
                self.mode = "rest"
        if self.mode == "rest":
            self._rest(state, send)
            return
        if not listed and self._dump_extras(state, send):
            return
        if self.mode == "gear":
            self._gear(state, send)
            return
        if self.mode == "hunt":
            self._hunt(state, send)

    def _need_rest(self, state: WorldState) -> bool:
        if state.hp is None:
            return False
        ratio = state.hp_ratio()
        if ratio is not None:
            need = PARTY_REST_RATIO if self._ninja_party(state) else self.rest_ratio
            return ratio < need
        return state.hp < REST_ABS

    def _healed(self, state: WorldState) -> bool:
        if state.hp is None or not state.max_hp:
            return False
        return state.hp >= state.max_hp

    def _ready_to_hunt(self, state: WorldState) -> bool:
        if state.mortal or state.bleeding:
            return False
        if self._need_rest(state):
            return False
        if state.hp is not None and state.hp < 1:
            return False
        return True

    def _needs_heal(self, state: WorldState) -> bool:
        if state.hp is None:
            return False
        if state.max_hp_known:
            ratio = state.hp_ratio()
            if ratio is None:
                return False
            return ratio <= HEAL_RATIO
        return state.hp < REST_ABS

    def _in_pit(self, state: WorldState) -> bool:
        if paths.is_dangerous(state.room):
            return True
        low = state.room.lower()
        if any(
            word in low
            for word in ("road", "path", "entrance", "shop", "healer", "guild", "store")
        ):
            return False
        return self._in_camp

    def _party_ready(self, state: WorldState) -> bool:
        """Grouped enough to hunt. Leader does not need backrank text."""
        self._sync_party(state)
        if not self._leading():
            if not (state.following or self._followed):
                return False
            if self.rank in {"back", "backrank"}:
                return self._ranked
            return True
        if not self._invited:
            return False
        return any(self._mine(n, state) for n in state.followers)

    def _can_drop_arena(self, state: WorldState) -> bool:
        """Clear room with `d` to the pit once the party is ready."""
        if self._in_pit(state) or self._lops_here(state):
            return False
        if self._followed or self._wounded_bleeding(state):
            return False
        if not self._ready_to_hunt(state):
            return False
        if (
            self.leader
            and self._leading()
            and self._alts_here(state)
            and not self._party_ready(state)
        ):
            return False
        return paths.step_toward_arena(state.room, state.exits) == "d"

    def _down(self, state: WorldState) -> bool:
        return self._sitting or state.resting

    def _lops_here(self, state: WorldState) -> bool:
        return bool(_trusted_live(state) or paths.lop_in(state.mobs))

    def _listed_fight(self, state: WorldState) -> bool:
        """Join/look already printed a farm lop — swing before i/look/health."""
        if not self._lops_here(state) or not self._opens_swing(state):
            return False
        return bool(
            state.saw_here
            or state.saw_see
            or state.in_combat
            or self._attacking
            or (self._in_pit(state) and state.scanned)
        )

    def _swing_first(self, state: WorldState, send) -> bool:
        """A listed farm lop is a fight. Skip boot look when Also here already printed."""
        live = self._aim(state) or paths.lop_in(state.mobs)
        if not live or not self._opens_swing(state):
            return False
        if self._ambush_boot and not self._boot_looked and not state.saw_here:
            return False
        if self._ambush_boot:
            self._clear_ambush_boot()
        if self._engage_lop(state, send, live):
            self._evaded = False
            return True
        return False

    def _known_here(self, name: str, state: WorldState) -> bool:
        if self._mine(name, state) or self._me(name):
            return True
        if self.leader and self._same_toon(name, self.leader):
            return True
        return any(self._same_toon(name, n) for n in state.followers)

    def _strangers_here(self, state: WorldState) -> bool:
        """Other PCs (Coorwyn) or named NPCs (Corwyn). Cannot sneak with them."""
        extras = self._aka | state.self_names
        return any(
            not self._known_here(name, state)
            for name in paths.occupants_in(state.mobs, extras)
        )

    def _may_sit(self, state: WorldState) -> bool:
        """Sit only when no lop is here and the pit scan is trustworthy.

        A look in flight, a just-`d` drop, or an unscanned pit is not empty.
        """
        if _trusted_live(state) or paths.lop_in(state.mobs):
            return False
        if state.in_combat or self._attacking:
            return False
        if state.look_scan or self._drop_scan:
            return False
        if self._in_pit(state) and not state.scanned:
            return False
        return True

    def _busy_swing(self, state: WorldState) -> bool:
        """Look mid-swing or on the same prompt as attack/bs flickers combat."""
        if state.in_combat or self._attacking:
            return True
        if self._last_verb not in {"attack", "att", "bash", "aa", "bs"}:
            return False
        return state.prompt_seq <= self._wait_prompt

    def _ask_look(self, send, state: WorldState) -> bool:
        if self._busy_swing(state):
            self._want_look = False
            return False
        self._drop_scan = False
        state.look_scan = True
        state.saw_here = False
        state.saw_see = False
        self._cmd(send, "look", state)
        return True

    def _sit(self, send, state: WorldState) -> bool:
        if not self._may_sit(state):
            return False
        self._cmd(send, "rest", state)
        self._sitting = True
        return True

    def _wounded_bleeding(self, state: WorldState) -> bool:
        """Still bleeding in the room — do not leave the road to hunt."""
        if state.ally_mortal:
            return True
        return bool(state.bleeding and not state.aided)

    def _can_sneak_here(self, state: WorldState) -> bool:
        """`sn` only on an empty room. Combat, a lop, a stranger, or a pending look blocks."""
        if state.in_combat or self._lops_here(state) or self._strangers_here(state):
            return False
        if self._want_look or state.look_scan:
            return False
        if self._ninja_party(state):
            return True
        return self._own_ambush(state)

    def _note_evasion(self, state: WorldState) -> None:
        """*Combat Off* after leaving the pit is a successful flee.

        Drop the fight lock. Break first so the game fight is actually
        off, then sneak (empty) or swing (a followed lop).
        """
        off = state.combat_off
        state.combat_off = False
        if off:
            # *Combat Off* ends the swing — even in the pit. Ghost aim
            # (`acid slime` after the fight) must not fire on the next spawn.
            # A fight spends sneak. Look before the next `bs` — leftover
            # mobs make `bs` fail and retry-loop.
            fighting = bool(self._attacking or self._pit_fight)
            self._attacking = ""
            if fighting:
                self._hidden = False
                self._sneaking = False
                self._sneak_armed = False
                self._sneak_wait = False
                self._sneak_block = False
            if not self._lops_here(state):
                self._want_look = True
                # combat_off stripped leftover farm names — Also here is stale.
                state.scanned = False
                state.saw_here = False
                state.look_scan = False
        if not off or self._in_pit(state):
            self._evaded = False
            return
        self._evaded = True
        self._need_break = True
        self._attacking = ""
        self._in_camp = False
        self._pit_fight = False

    def _break_after_leave(self, send, state: WorldState) -> bool:
        """After leaving a fight room, `break` before sneak/look/rest/aid.

        Combat can stay on in the game after the room change. Other
        commands then fail or re-aggro. One break, then the next prompt.
        Still in the pit with a monster: stay in the fight.
        """
        if self._ambush_boot:
            return False
        if not self._need_break:
            return False
        if self._with_leader(state) and not self._sneak_block:
            self._need_break = False
            return False
        if self._in_pit(state) and self._lops_here(state):
            self._need_break = False
            return False
        self._need_break = False
        self._sitting = False
        self._attacking = ""
        state.in_combat = False
        self._cmd(send, "break", state)
        return True

    def _sneak_ready(self) -> bool:
        return bool(self._hidden or self._sneak_armed or self._sneaking)

    def _sneak_settled(self) -> bool:
        """Hidden already, or armed and the setup beat has passed."""
        if self._hidden or self._sneaking:
            return True
        if not self._sneak_armed:
            return False
        return time.monotonic() >= self._sneak_ready_at

    def _holding_sneak(self, state: WorldState) -> bool:
        """Armed after Attempting — look/`d` now would break sneak."""
        if state.in_combat or self._lops_here(state):
            return False
        if self._ninja_party(state):
            return bool(self._sneak_armed and not self._sneak_settled())
        if self._with_leader(state):
            return False
        return (
            self._sneak_armed
            and not self._sneak_settled()
            and not self._in_pit(state)
        )

    def _need_look(self, state: WorldState) -> bool:
        """No listed farm mob and Also here is missing or stale."""
        if self._busy_swing(state):
            return False
        if self._lops_here(state):
            return False
        if self._want_look:
            return True
        if self._in_pit(state) and self._pit_fight and not paths.coins_in(state.things):
            return False
        if state.in_combat and self._attacking and _still_here(state, self._attacking):
            return False
        # Ambush outside the pit: `sn` / `d`, not a look this tick.
        if self._own_ambush(state) and not self._in_pit(state) and not self._want_look:
            return False
        # Party ninja: stay stealthed; creep/Also here lists the next lop.
        if self._ninja_party(state) and not self._want_look:
            return False
        # Solo road drop — do not stall on look_scan from the last `d`.
        if not self._with_leader(state) and self._arena_drop(state) and not self._want_look:
            return False
        if state.look_scan or self._drop_scan or self._want_look:
            return True
        return not state.scanned

    def _arena_drop(self, state: WorldState) -> bool:
        return paths.step_toward_arena(state.room, state.exits) == "d"

    def _should_leave_to_sneak(self, state: WorldState) -> bool:
        """A listed lop is a fight. Do not walk off to sn first."""
        return False

    def _setup_sneak(self, send, state: WorldState) -> bool:
        """One `sn` on an empty room. True if we acted.

        `Attempting` is not ready. After settle with no fail, assume hidden.
        Sitting: break first. Busy fail: one `break`, wait, then one `sn`.
        Do not send another `sn` while `_sneak_wait` — that is the KEY_GAP storm.
        Other fail: flop — solo moves to another empty room, then `sn`.
        Party stays with Matt and `sn`s the next empty tick after the block.
        """
        if not self._can_sneak_here(state):
            return False
        if self._sneak_flop and not self._ninja_party(state):
            return False
        if self._hidden or self._sneak_armed or self._sneaking:
            return False
        if self._sneak_wait:
            # Already sent `sn`. Wait for try/fail/ok — never stack.
            return False
        if self._sneak_block and self._need_break:
            return False
        if self._down(state):
            self._sitting = False
            self._cmd(send, "break", state)
            return True
        if self._sneak_block:
            # Break settled. Room still empty — one retry, not a storm.
            self._sneak_block = False
        self._sneak_flop = False
        if self._send_sneak(send, state):
            self._sneak_wait = True
            return True
        return False

    def _send_sneak(self, send, state: WorldState) -> bool:
        """Sneak while standing, combat off, room empty."""
        if state.in_combat or self._lops_here(state):
            return False
        if self._down(state):
            self._sitting = False
            self._cmd(send, "break", state)
            return False
        self._cmd(send, "sn", state)
        return True

    def _party_sneak(self, state: WorldState, send) -> bool:
        """Following: `sn` only when the room is empty. Occupied rooms `bs`."""
        if not self._ninja_party(state) or state.in_combat:
            return False
        if self._lops_here(state):
            return False
        if self._stealthed():
            return False
        if self._setup_sneak(send, state):
            return True
        if self._sneak_armed or self._sneak_wait:
            self.next_action = "ambush"
            return True
        return False

    def _retry_after_flop(self, state: WorldState, send) -> bool:
        """Solo: after a sneak fail, leave this room, then `sn` on the next empty.

        Party stays with Matt — next empty tick retries `sn`. Occupied: `bs`.
        """
        if not self._sneak_flop:
            return False
        if self._lops_here(state) or state.in_combat:
            self._sneak_flop = False
            return False
        if self._ninja_party(state):
            return False
        self._sneak_flop = False
        if self._in_pit(state):
            self._travel(send, "u", state, sneak=False)
            return True
        if self._arena_drop(state):
            self._travel(send, "d", state, sneak=False)
            return True
        step = paths.step_toward_arena(state.room, state.exits)
        if not step:
            return False
        if state.exits and step not in state.exits:
            return False
        self._travel(send, step, state, sneak=False)
        return True

    def _cmd(self, send, text: str, state: WorldState) -> None:
        verb, sep, rest = text.partition(" ")
        if sep and verb.lower() in {"attack", "att", "bash", "aa", "bs"} and rest:
            aim = self._swing_name(rest)
            if not aim:
                return
            text = f"{verb.lower()} {aim}"
            self._last_aim = aim
        self._last_verb = text.split()[0].lower()
        self.next_action = text
        send(text)
        self._wait_prompt = state.prompt_seq + 1
        self._sent_at = time.monotonic()
        if text == "break":
            self._need_break = False
        parts = text.split()
        step = ""
        if text in {"n", "s", "e", "w", "u", "d"}:
            step = text
        elif (
            len(parts) == 3
            and parts[0].lower() == "drag"
            and parts[2].lower() in {"n", "s", "e", "w", "u", "d"}
        ):
            step = parts[2].lower()
        if step:
            self._last_aim = ""
            if state.in_combat or self._attacking:
                self._need_break = True
            if step == "u" and self._ninja() and self._stealth_moves() and not self._ambush_boot:
                self._need_break = True
            self._last_step = step
            self._step_room = state.room
            self._hidden = False
            self._sneaking = False
            self._sneak_armed = False
            self._sneak_block = False
            self._sneak_ready_at = 0.0
        if step == "d":
            self._in_camp = True
            self._pit_fight = True
            self._drop_scan = True
            state.mobs = []
            state.things = []
            state.scanned = False
            state.look_scan = True
            state.saw_here = False
            state.saw_see = False
            if "arena" not in state.room.lower():
                state.room = "Newhaven, Arena"
            state.exits = [x for x in state.exits if x != "d"]
        elif step == "u":
            self._in_camp = False
            self._pit_fight = False
            self._drop_scan = False
            self._attacking = ""
            state.mobs = []
            state.things = []
            state.scanned = False
            if "arena" in state.room.lower():
                state.room = "Newhaven, Narrow Road"
                state.exits = ["n", "e", "w", "d", "s"]

    def _travel(
        self, send, step: str, state: WorldState, *, sneak: bool = True
    ) -> None:
        """Move. Ninja ambush sneaks first on an empty room; never with lops."""
        if step in realm_map.DIRS and state.exits and step not in state.exits:
            self.next_action = "looking"
            if not self._busy_swing(state):
                self._cmd(send, "look", state)
            return
        if (
            sneak
            and self._own_ambush(state)
            and step in realm_map.DIRS
            and not state.in_combat
            and not self._attacking
        ):
            if self._setup_sneak(send, state):
                self._pending_step = self._pending_step or step
                return
            if (
                step == "d"
                and not self._sneak_ready()
                and not self._lops_here(state)
                and not self._in_pit(state)
            ):
                return
            if self._holding_sneak(state):
                self._pending_step = self._pending_step or step
                self.next_action = "ambush"
                return
            self._pending_step = ""
        self._pending_step = ""
        self._cmd(send, step, state)

    def _clear_landed_step(self, state: WorldState) -> None:
        """Same heading from a new room is a new walk — Betram `n` then weapons `n`."""
        here = (state.room or "").strip()
        left = (self._step_room or "").strip()
        if self._last_step and here and left and here != left:
            self._last_step = ""

    def _go(self, send, step: str, state: WorldState) -> bool:
        if not step:
            return False
        if state.exits and step not in state.exits:
            return False
        if not state.exits and self.mode == "gear":
            return False
        self._clear_landed_step(state)
        if step == self._last_step:
            self.next_action = "waiting"
            return True
        self._travel(send, step, state)
        return True

    def _map_step(self, state: WorldState, send) -> bool:
        if self._followed:
            return False
        hint = self._atlas.suggest(
            state.room, state.exits, self._last_step, state.scanned
        )
        if hint.action == "look":
            if self._busy_swing(state):
                return False
            self._cmd(send, "look", state)
            if hint.chrome:
                self.next_action = hint.chrome
            return True
        if hint.action in {"path", "guess"} and hint.step:
            if self._go(send, hint.step, state):
                if hint.chrome:
                    self.next_action = hint.chrome
                return True
        return False

    def _rest(self, state: WorldState, send) -> None:
        live = _trusted_live(state) or paths.lop_in(state.mobs)
        if live or state.in_combat or self._attacking:
            self.mode = "hunt" if self.gear_done else "gear"
            self._hunt(state, send)
            return
        if self._in_pit(state) and not self._may_sit(state):
            if state.look_scan:
                self.next_action = "looking"
                return
            if self._drop_scan:
                if self._ask_look(send, state):
                    return
        if self._healed(state) or (self._recovering and self._ready_to_hunt(state)):
            self._recovering = False
            self._attacking = ""
            self.mode = "hunt" if self.gear_done else "gear"
            self.next_action = self.mode
            if self.mode == "hunt" and self._stealth_moves():
                self._hunt(state, send)
                return
            self._sitting = False
            return
        if self._try_heal(state, send):
            return
        if self._in_pit(state):
            if state.mortal or state.bleeding:
                if self._sitting:
                    self.next_action = "healing"
                    return
                if self._sit(send, state):
                    return
                self.next_action = "looking" if state.look_scan else "waiting"
                return
            if self._in_party(state):
                if self._sitting:
                    self.next_action = "healing"
                    return
                if self._sit(send, state):
                    return
                self.next_action = "looking" if state.look_scan else "waiting"
                return
            self._sitting = False
            self._attacking = ""
            self._travel(send, "u", state)
            return
        room = state.room.lower()
        if state.dark:
            if not self._tried_torch:
                self._tried_torch = True
                self._cmd(send, f"use {paths.STARTER_LIGHT}", state)
                return
            if "general" in room:
                self._cmd(send, f"buy {paths.STARTER_LIGHT}", state)
                self._torch_bought = True
                self._await_inv = True
                self._pry_sent = False
                return
            step = paths.step_toward_store(state.room, state.exits)
            if step:
                self._sitting = False
                self._go(send, step, state)
                return
        if "general" in room:
            step = paths.step_toward_arena(state.room, state.exits)
            self._sitting = False
            if step:
                self._go(send, step, state)
            return
        if self._sitting:
            self.next_action = "healing"
            return
        if not self._sit(send, state):
            self.next_action = "waiting"

    def _extra_name(self, state: WorldState) -> str | None:
        if self._await_inv:
            return None
        return paths.extra_starter(
            state.inventory, state.extras, self._skip_sell, state.worn
        )

    def _note_sales(self, state: WorldState) -> None:
        """Sold / a leftover `You are carrying` on screen is not a fresh `i`."""
        if state.flooded:
            state.flooded = False
            self._selling = ""
            self._await_inv = True
        sold = (state.last_sold or "").strip().lower()
        if sold:
            state.last_sold = ""
            self._selling = ""
            self._await_inv = True
        if state.shop_vague and self._selling:
            self._skip_sell.add(self._selling)
            self._selling = ""
            state.shop_vague = False
            self._await_inv = True
        if (
            self._pry_sent
            and state.inv_seq > self._inv_after
            and state.prompt_seq > self._i_prompt
        ):
            self._inv_seen = state.inv_seq
            self._await_inv = False
            self._pry_sent = False

    def _ask_inv(self, send, state: WorldState) -> bool:
        if self._pry_sent:
            if state.inv_seq > self._inv_after:
                self._inv_seen = state.inv_seq
                self._await_inv = False
                self._pry_sent = False
                return False
            return True
        self._pry_sent = True
        self._await_inv = True
        self._inv_after = state.inv_seq
        self._i_prompt = state.prompt_seq
        self._cmd(send, "i", state)
        return True

    def _in_sell_shop(self, state: WorldState) -> bool:
        room = state.room.lower()
        here = " ".join(state.mobs).lower()
        return (
            state.in_shop
            or paths.is_armour_shop(room)
            or paths.is_weapon_shop(room)
            or "shop" in room
            or "store" in room
            or "betram" in here
            or "bertram" in here
        )

    def _sell_extra(self, state: WorldState, send) -> bool:
        """Sell one spare from the last `i`. Do not guess after a miss."""
        self._note_sales(state)
        if self._await_inv:
            return self._ask_inv(send, state)
        extra = self._extra_name(state)
        if not extra or state.in_combat or state.shop_vague:
            return False
        if not self._in_sell_shop(state):
            return False
        self._selling = extra
        self._await_inv = True
        self._pry_sent = False
        self._cmd(send, f"sell {extra}", state)
        return True

    def _dump_extras(self, state: WorldState, send) -> bool:
        """Sell stacks until `i` has no extras. Walk to Betram if needed."""
        self._note_sales(state)
        if self._await_inv:
            return self._ask_inv(send, state)
        extra = self._extra_name(state)
        if not extra or state.in_combat or state.shop_vague:
            return False
        if self._sell_extra(state, send):
            return True
        room = state.room.lower()
        if "village entrance" in room:
            if self._go(send, "s", state):
                self._await_inv = True
                self._pry_sent = False
                return True
            return False
        return False

    def _note_already_worn(self, state: WorldState) -> None:
        item = (state.already_worn or "").strip().lower()
        if not item:
            return
        state.already_worn = ""
        if item not in state.worn:
            state.worn.append(item)
        if paths.STARTER_WEAPON in item:
            self._weapon_worn = True
            self._wearing = False
            return
        for i, name in enumerate(paths.ARMOUR_ITEMS):
            if name in item or item in name:
                if self._armour_i <= i:
                    self._armour_i = i + 1
                self._wearing = False
                return
        if self._wearing:
            self._wearing = False
            self._armour_i += 1

    def _skip_worn_armour(self, state: WorldState) -> None:
        while self._armour_i < len(paths.ARMOUR_ITEMS):
            item = paths.ARMOUR_ITEMS[self._armour_i]
            if item in state.worn:
                self._wearing = False
                self._armour_i += 1
                continue
            break

    def _inv_has_light(self, state: WorldState) -> bool:
        held = " ".join(state.inventory + state.worn + state.extras).lower()
        return paths.STARTER_LIGHT in held

    def _sync_gear_from_inv(self, state: WorldState) -> None:
        """Last `i` worn list is truth — do not bounce south for a vest we have on."""
        self._skip_worn_armour(state)
        if state.geared or any(paths.STARTER_WEAPON in w for w in state.worn):
            self._weapon_worn = True
            self._weapon_bought = True
        if self._inv_has_light(state):
            self._torch_bought = True

    def _kit_ready(self) -> bool:
        return (
            self._armour_i >= len(paths.ARMOUR_ITEMS)
            and self._weapon_worn
            and self._torch_bought
        )

    def _advance_spell(self) -> None:
        self._spell_i += 1
        self._spell_buying = False
        self._spell_reading = False
        self._spell_alt = False
        if self._spell_i >= len(self._learn):
            self._spells_shopped = True

    def _shop_one_spell(self, state: WorldState, send) -> bool:
        """Buy then `read` one scroll. Minor healing is first in `_learn`."""
        if self._spells_shopped or self._spell_i >= len(self._learn):
            self._spells_shopped = True
            return False
        name = self._learn[self._spell_i]
        held = list(state.inventory) + list(state.extras)
        if spells.have_known(held, name):
            self._advance_spell()
            return self._shop_one_spell(state, send)
        if spells.have_scroll(held, name):
            if not self._spell_reading:
                self._cmd(send, spells.read_command(name), state)
                self._spell_reading = True
                return True
            self._advance_spell()
            return True
        if not self._spell_buying:
            self._cmd(send, f"buy {spells.buy_name(name, alt=self._spell_alt)}", state)
            self._spell_buying = True
            return True
        if not self._spell_reading:
            self._cmd(send, spells.read_command(name), state)
            self._spell_reading = True
            return True
        self._advance_spell()
        return True

    def _done_gear(self) -> None:
        self.gear_done = True
        self.mode = "hunt"
        self.next_action = "hunt"
        self._await_inv = False
        self._pry_sent = False

    def _gear(self, state: WorldState, send) -> None:
        if self._listed_fight(state):
            self._done_gear()
            return
        if state.blocked:
            state.blocked = False
            self._last_step = ""
            self._cmd(send, "look", state)
            return
        self._note_already_worn(state)
        self._sync_gear_from_inv(state)
        if state.learned or state.spell_skip:
            state.learned = False
            state.spell_skip = False
            if self._spell_buying or self._spell_reading:
                self._advance_spell()
        if self._sell_extra(state, send):
            return
        room = state.room.lower()
        if state.shop_vague:
            state.shop_vague = False
            if self._spell_reading:
                self._advance_spell()
                self.next_action = "shop"
                return
            if self._spell_buying:
                if not self._spell_alt and self._spell_i < len(self._learn):
                    self._spell_alt = True
                    name = self._learn[self._spell_i]
                    self._cmd(send, f"buy {spells.buy_name(name, alt=True)}", state)
                    return
                self._advance_spell()
                self.next_action = "shop"
                return
            if self._wearing:
                self._wearing = False
                self._armour_i += 1
            elif not self._weapon_worn:
                self._weapon_bought = True
            elif not self._torch_bought and paths.is_general_store(room):
                self._torch_bought = True
            self.next_action = "shop"
            return
        if not self._looked:
            self._looked = True
            self._cmd(send, "look", state)
            return
        extra = self._extra_name(state)
        if extra and "village entrance" in room:
            if not self._go(send, "s", state):
                self._cmd(send, "look", state)
            return
        if paths.is_armour_shop(room):
            self._skip_worn_armour(state)
            if self._armour_i < len(paths.ARMOUR_ITEMS):
                item = paths.ARMOUR_ITEMS[self._armour_i]
                if item in state.worn:
                    self._wearing = False
                    self._armour_i += 1
                    return
                if not self._wearing:
                    self._cmd(send, f"buy {item}", state)
                    self._wearing = True
                    self._await_inv = True
                    self._pry_sent = False
                    return
                self._cmd(send, f"wear {item}", state)
                self._wearing = False
                self._armour_i += 1
                self._await_inv = True
                self._pry_sent = False
                return
            if not self._go(send, "n", state):
                self._cmd(send, "look", state)
            return
        if paths.is_weapon_shop(room):
            if not self._weapon_bought:
                self._cmd(send, f"buy {paths.STARTER_WEAPON}", state)
                self._weapon_bought = True
                self._await_inv = True
                self._pry_sent = False
                return
            if paths.STARTER_WEAPON in state.worn or state.geared:
                self._weapon_worn = True
            if not self._weapon_worn:
                self._cmd(send, f"wear {paths.STARTER_WEAPON}", state)
                self._weapon_worn = True
                self._await_inv = True
                self._pry_sent = False
                return
            if not self._go(send, "s", state):
                self._cmd(send, "look", state)
            return
        if paths.is_general_store(room):
            if not self._torch_bought:
                self._cmd(send, f"buy {paths.STARTER_LIGHT}", state)
                self._torch_bought = True
                self._await_inv = True
                self._pry_sent = False
                return
            step = paths.leave_dead_end(state.room, state.exits)
            if not step or not self._go(send, step, state):
                self._cmd(send, "look", state)
            return
        if paths.is_spell_shop(room):
            if not self._spells_shopped and self._shop_one_spell(state, send):
                return
            if not self._go(send, "s", state):
                self._cmd(send, "look", state)
            return
        if paths.is_dangerous(room):
            self._done_gear()
            return
        if self._kit_ready() and self._spells_shopped:
            self._done_gear()
            return
        if "village entrance" in room:
            if self._armour_i < len(paths.ARMOUR_ITEMS):
                if not self._go(send, "s", state):
                    self._cmd(send, "look", state)
                return
            if not self._weapon_worn:
                if not self._go(send, "n", state):
                    self._cmd(send, "look", state)
                return
            if not self._torch_bought:
                if not self._go(send, "w", state):
                    self._cmd(send, "look", state)
                return
            if not self._spells_shopped:
                if not self._go(send, "w", state):
                    self._cmd(send, "look", state)
                return
            self._done_gear()
            return
        if "narrow path" in room:
            if not self._torch_bought:
                if not self._go(send, "s", state):
                    self._cmd(send, "look", state)
                return
            if not self._spells_shopped:
                if not self._go(send, "n", state):
                    self._cmd(send, "look", state)
                return
            if not self._go(send, "w", state):
                self._cmd(send, "look", state)
            return
        if "narrow road" in room:
            if not self._torch_bought:
                if not self._go(send, "e", state):
                    self._cmd(send, "look", state)
                return
            if not self._spells_shopped:
                if not self._go(send, "e", state):
                    self._cmd(send, "look", state)
                return
            self._done_gear()
            return
        if self._kit_ready() and not self._spells_shopped:
            step = paths.step_toward_spell_shop(state.room, state.exits)
            if step and self._go(send, step, state):
                return
            self._cmd(send, "look", state)
            return
        step = paths.step_toward_arena(state.room, state.exits)
        if step and self._go(send, step, state):
            return
        self._cmd(send, "look", state)

    def _leader_here(self, state: WorldState) -> bool:
        want = self.leader.lower()
        if not want:
            return False
        extras = self._aka | state.self_names
        for name in (*paths.players_in(state.mobs, extras), *state.mobs):
            low = name.lower()
            if want == low or want in low.split():
                return True
            tagged = paths.party_name(name, extras).lower()
            if tagged and want == tagged:
                return True
        return False

    def _clear_invite(self, state: WorldState) -> None:
        self._got_invite = False
        state.invited_by = ""

    def _sync_party(self, state: WorldState) -> None:
        if state.invited_by:
            self._got_invite = True
        if state.following:
            self._joined = True
            self._followed = True
            self._clear_invite(state)
        if state.left_party:
            state.left_party = False
            self._joined = False
            self._followed = False
            self._ranked = False
            self._clear_invite(state)
        if state.backrank:
            self._ranked = True
        if state.followers:
            self._invited = True
            if self._leading():
                # Follower-only "You have moved to the back ranks" is not
                # printed to the leader. They followed is enough.
                self._ranked = True
        reason = state.party_fail
        state.party_fail = ""
        if reason == "invite":
            self._joined = False
            self._followed = False
            self._clear_invite(state)
        if reason == "party":
            self._ranked = False
            self._clear_invite(state)
            if not state.following:
                self._joined = False
                self._followed = False

    def _alts_here(self, state: WorldState) -> list[str]:
        extras = self._aka | state.self_names
        found: list[str] = []
        for name in paths.players_in(state.mobs, extras):
            if self._mine(name, state) and not self._me(name) and name not in found:
                found.append(name)
        return found

    def _arm_rescue(self, state: WorldState, who: str) -> None:
        extras = self._aka | state.self_names
        self._rescue_who = paths.party_name(who, extras) or who
        self._rescue = "out"

    def _arm_leader_rescue(self, state: WorldState) -> bool:
        """F1 / panic: drag the configured leader if they are mortal."""
        who = state.ally_mortal.strip()
        if not who or self._me(who):
            return False
        if self.leader:
            if not self._same_toon(who, self.leader):
                return False
        elif not self._mine(who, state):
            return False
        self._arm_rescue(state, who)
        return True

    def _note_wound(self, state: WorldState) -> None:
        if state.mortal or state.bleeding:
            self._recovering = True
        who = state.ally_mortal.strip()
        if not who or self._me(who):
            return
        if not self._mine(who, state):
            return
        self._arm_rescue(state, who)

    def _still_need_aid(self, state: WorldState) -> bool:
        who = self._rescue_who
        if not who:
            return False
        if self._me(who):
            return False
        seen = state.ally_mortal.strip()
        return bool(seen) and self._same_toon(seen, who)

    def _drop_follow(self, state: WorldState) -> None:
        state.following = ""
        state.left_party = False
        self._joined = False
        self._followed = False
        self._ranked = False
        self._clear_invite(state)

    def _rescue_tick(self, state: WorldState, send) -> bool:
        """Healthy toon: drag the other home toon out of the pit, aid, then solo."""
        if state.mortal or state.bleeding:
            return False
        if not self._rescue:
            return False
        who = self._rescue_who
        if not who or self._me(who):
            self._clear_rescue()
            return False
        if self._break_after_leave(send, state):
            return True
        if state.afraid:
            state.afraid = False
            self._sitting = False
            self._attacking = ""
            state.in_combat = False
            self._cmd(send, "break", state)
            return True
        if state.drag_fail:
            state.drag_fail = False
            self._drag_on = False
            if self._still_need_aid(state) and not self._in_pit(state):
                self._cmd(send, f"aid {who}", state)
                return True
            self.next_action = "aid"
            return True
        if state.in_combat or self._attacking or self._down(state):
            self._sitting = False
            self._attacking = ""
            state.in_combat = False
            self._cmd(send, "break", state)
            return True
        if state.following or self._followed:
            self._cmd(send, "leave", state)
            self._drop_follow(state)
            return True
        if self._in_pit(state) and self._still_need_aid(state):
            self._drag_on = True
            self._cmd(send, f"drag {who} u", state)
            return True
        if self._still_need_aid(state):
            self._cmd(send, f"aid {who}", state)
            return True
        if self._drag_on or state.dragging:
            self._drag_on = False
            state.dragging = ""
            self._cmd(send, "drag", state)
            return True
        # Aid done. Solo ambush until a real invite — do not camp the road.
        self._clear_rescue()
        return False

    def _party_pending(self, state: WorldState) -> bool:
        if not self.leader:
            return False
        if self._rescue or state.ally_mortal:
            return False
        self._sync_party(state)
        if self._leading():
            if not self._ready_to_hunt(state):
                return False
            alts = self._alts_here(state)
            return bool(alts) and not self._party_ready(state)
        if not self._followed:
            # Invite only. Leader in the room is not a wait — still hunt / `d`.
            return bool(self._got_invite)
        return self.rank in {"back", "backrank"} and not self._ranked

    def _party(self, state: WorldState, send) -> bool:
        if not self.leader:
            return False
        self._sync_party(state)
        now = time.monotonic()
        if self._leading():
            if not self._ready_to_hunt(state):
                return False
            alts = self._alts_here(state)
            if not alts:
                return False
            if any(self._mine(n, state) for n in state.followers):
                return False
            if self._invited and (not self._party_at or now - self._party_at < 15):
                return False
            self._invited = True
            self._party_at = now
            extras = self._aka | state.self_names
            who = paths.party_name(alts[0], extras) or alts[0]
            self._cmd(send, f"invite {who}", state)
            return True
        if self._followed and (self._ranked or self.rank not in {"back", "backrank"}):
            return False
        if not self._followed:
            # Invite only — leader in the room is not a join.
            if not self.auto_join:
                return False
            if self._rescue or state.ally_mortal:
                return False
            if not self._got_invite:
                return False
            if self._party_at and now - self._party_at < 6:
                return False
            self._party_at = now
            self._cmd(send, f"follow {self.leader}", state)
            return True
        if self.rank in {"back", "backrank"} and not self._ranked:
            self._ranked = True
            self._party_at = now
            self._cmd(send, "backrank", state)
            self._maybe_party_hunt(state)
            return True
        return False

    def _camp(self, state: WorldState, send) -> None:
        if state.scanned or self._busy_swing(state):
            self.next_action = "camping"
            return
        now = time.monotonic()
        if now - self._sent_at >= LOOK_GAP:
            state.look_scan = True
            state.saw_here = False
            state.saw_see = False
            self._cmd(send, "look", state)
            self.next_action = "camping"
            return
        self.next_action = "camping"

    def _queued_swing_gone(
        self,
        pending: bool,
        aim: str,
        verb: str,
        dead: str,
        state: WorldState,
    ) -> bool:
        """True when a paced `at` / `bs` is aimed at a mob that just died."""
        if not pending or not aim:
            return False
        if verb not in {"attack", "att", "bash", "aa", "bs", "at"}:
            return False
        if dead and paths.same_mob(aim, dead):
            return True
        return not _still_here(state, aim)

    def _aim(self, state: WorldState) -> str | None:
        """Stay on the current fight, or open on a listed farm mob.

        Listing is arrive / Also here / a monster swing — not our echo.
        """
        if self._attacking:
            held = _still_here(state, self._attacking)
            if held:
                return held
        return _trusted_live(state)

    def _opening(self, state: WorldState) -> bool:
        return self._ninja() and not state.in_combat and (
            self._sneak_wait or self._sneaking or self._sneak_armed or self._sneak_flop
        )

    def _resolve_fight(self, state: WorldState) -> None:
        if state.whiff:
            self._attacking = ""
            self._last_aim = ""
            self._last_verb = ""
            state.whiff = False
            state.in_combat = False
        if state.last_kill:
            dead = state.last_kill
            if not state.scanned:
                state.mobs = paths.without_dead(state.mobs, dead)
            self._attacking = ""
            self._last_aim = ""
            self._last_verb = ""
            self._last_cast = ""
            self._sneaking = False
            self._sneak_wait = False
            self._sneak_armed = False
            self._sneak_block = False
            self._hidden = False
            state.last_kill = ""
            if self._own_ambush(state) and not self._in_pit(state):
                self._need_break = True
            empty = not paths.lop_in(state.mobs) and not paths.coins_in(state.things)
            if self._in_pit(state) and not paths.coins_in(state.things):
                # Next spawn prints itself. A look after Off lets it swing first.
                self._want_look = False
            elif empty and not state.scanned:
                self._want_look = True
        elif self._attacking and not self._opening(state):
            if not _still_here(state, self._attacking):
                if not state.in_combat or _trusted_live(state):
                    self._attacking = ""
        if state.needs_scan:
            state.needs_scan = False
            self._attacking = ""
            if not paths.lop_in(state.mobs) and not paths.coins_in(state.things):
                if not state.scanned and not self._busy_swing(state):
                    if not self._in_pit(state):
                        self._want_look = True
        if state.scanned:
            self._want_look = False
        if self._busy_swing(state):
            self._want_look = False

    def _engage_lop(self, state: WorldState, send, live: str) -> bool:
        """Hidden/sneaking → bs. Visible or sneak-fail → attack. Never sn here."""
        if self._party_pending(state) and not self._followed:
            return False
        if not live or self._mine(live, state):
            return False
        self._want_look = False
        self._sneak_wait = False
        self._sneak_armed = False
        self._sneak_block = False
        self._sneak_flop = False
        aim = self._swing_name(live)
        extras = self._aka | state.self_names
        if not aim:
            return False
        if (
            self._mine(aim, state)
            or paths.has_toon(aim, extras)
            or any(paths.is_given_name(word, extras) for word in aim.split())
        ):
            return False
        if not _still_here(state, aim) and not _still_here(state, live):
            return False
        if self._try_heal(state, send):
            return True
        held = self._attacking
        if held and not _still_here(state, held):
            self._attacking = ""
            held = ""
        if (
            not held
            and self._last_aim
            and self._swing_name(self._last_aim).lower() == aim.lower()
            and (_still_here(state, aim) or _still_here(state, live))
        ):
            held = aim.lower()
            self._attacking = held
        if held and not paths.same_mob(held, aim):
            if self._try_harm(state, send, paths.attack_name(held)):
                return True
            self.next_action = f"fighting {held}"
            return True
        if held and paths.same_mob(held, aim) and not self._opening(state):
            if self._need_swing:
                # `get` cancelled auto-combat. Same species is a new swing.
                self._need_swing = False
                return self._strike(send, state, aim)
            if self._try_harm(state, send, aim):
                return True
            if _still_here(state, held):
                self.next_action = f"fighting {aim}"
            else:
                self.next_action = "fighting"
            return True
        if state.in_combat:
            verb = self._swing_verb(state)
            self._attacking = aim.lower()
            self._need_swing = False
            self._pit_fight = True
            self._sneaking = False
            self._sneak_armed = False
            self._sneak_wait = False
            self._hidden = False
            self._cmd(send, f"{verb} {aim}", state)
            return True
        return self._strike(send, state, aim)

    def _pick_coins(self, state: WorldState, send) -> bool:
        """`get` breaks auto-combat. Only loot a clear room; swing again after."""
        if state.in_combat or self._attacking:
            return False
        if self._aim(state) or paths.lop_in(state.mobs):
            return False
        coins = paths.coins_in(state.things)
        if not coins:
            return False
        self._want_look = False
        coin = coins[0]
        state.things = [t for t in state.things if coin not in t.lower()]
        self._last_aim = ""
        self._need_swing = True
        self._cmd(send, f"get {coin}", state)
        return True

    def _hunt(self, state: WorldState, send) -> None:
        if paths.is_dangerous(state.room):
            self._in_camp = True
        if state.dark:
            self._cmd(send, f"use {paths.STARTER_LIGHT}", state)
            return
        if self._swing_first(state, send):
            return
        if self._run_ambush_boot(state, send):
            return
        if self._ask_health(state, send):
            return
        if self._holding_sneak(state) and not self._lops_here(state):
            self.next_action = "ambush"
            return
        if self._party(state, send):
            return
        if self._try_heal(state, send):
            return
        if self._try_bless(state, send):
            return
        if self._retry_after_flop(state, send):
            return
        if self._party_sneak(state, send):
            return
        if self._party_pending(state) and not self._can_drop_arena(state):
            live_wait = self._aim(state) or paths.lop_in(state.mobs)
            if not (self._followed and live_wait):
                self.next_action = "party"
                return
        if self._panic_until and time.monotonic() < self._panic_until:
            self.next_action = "panic"
            return
        live = self._aim(state) or paths.lop_in(state.mobs)
        if self._should_leave_to_sneak(state):
            self._travel(send, "u", state)
            return
        if live and self._opens_swing(state) and self._engage_lop(state, send, live):
            self._evaded = False
            return
        if live and not self._opens_swing(state):
            self.next_action = "aa off"
            return
        if self._need_look(state):
            if state.look_scan:
                self.next_action = "looking"
                return
            self._want_look = False
            if self._ask_look(send, state):
                return
        if self._inout() and self._ambush_out:
            self._ambush_out = False
            self._sneaking = False
            if self._in_pit(state) and not self._lops_here(state):
                # Empty pit: `sn` here. Do not walk off just to sneak.
                self._attacking = ""
        if self.pvp and state.pvp_hit and not self._mine(state.pvp_hit, state):
            aim = self._swing_name(state.pvp_hit)
            if not aim:
                return
            if self._attacking == aim.lower():
                self.next_action = f"fighting {aim}"
                return
            self._attacking = aim.lower()
            state.in_combat = True
            self._cmd(send, f"{self._swing_verb(state)} {aim}", state)
            return
        if (state.in_combat or self._attacking) and (
            self._in_pit(state) or self._lops_here(state)
        ):
            self.next_action = "fighting"
            if time.monotonic() - self._sent_at > 20:
                self._attacking = ""
                state.in_combat = False
            return
        if not self._in_pit(state) and not self._lops_here(state):
            self._attacking = ""
            if state.in_combat and not self._evaded:
                # Left the fight room — break so combat is actually off.
                self._need_break = True
                if self._break_after_leave(send, state):
                    return
                self.next_action = "fighting"
                return
            # Evade / road / solo empty room: sn now. Party sneak ran earlier.
            may_sneak = self._own_ambush(state) and (
                self._evaded or self._arena_drop(state) or not self._followed
            )
            if may_sneak and self._setup_sneak(send, state):
                self._evaded = False
                return
        self._evaded = False
        self._attacking = ""
        if self._pick_coins(state, send):
            return
        if self._want_look:
            if self._setup_sneak(send, state):
                return
            self._want_look = False
            if self._ask_look(send, state):
                return
        if self._go_train(state, send):
            return
        if self._in_pit(state):
            leftover = self._aim(state) or paths.lop_in(state.mobs)
            if leftover and self._engage_lop(state, send, leftover):
                return
            if state.look_scan:
                self.next_action = "looking"
                return
            if not state.scanned or self._drop_scan:
                if self._ask_look(send, state):
                    return
            if self._try_heal(state, send):
                return
            if (
                self._ninja()
                and self._own_ambush(state)
                and not self._lops_here(state)
            ):
                if self._down(state):
                    self._sitting = False
                    self._cmd(send, "break", state)
                    return
                if self._stealthed() or self._sneak_armed or self._sneak_wait:
                    self.next_action = "ambush"
                    return
                if self._setup_sneak(send, state):
                    return
                return
            if not self._sitting:
                if not self._sit(send, state):
                    self.next_action = "looking" if state.look_scan else "waiting"
            else:
                self.next_action = "healing" if not self._healed(state) else "waiting"
            return
        if (
            self._own_ambush(state)
            and not self._wounded_bleeding(state)
            and not self._lops_here(state)
            and self._arena_drop(state)
        ):
            if self._setup_sneak(send, state):
                return
            if self._sneak_ready():
                self._travel(send, "d", state)
                return
            return
        if self._with_leader(state):
            self.next_action = f"follow {self.leader}"
            return
        if not self._in_pit(state) and not self._ready_to_hunt(state):
            if self._try_heal(state, send):
                return
            self.mode = "rest"
            self._rest(state, send)
            return
        if state.blocked:
            state.blocked = False
            self._in_camp = True
            if self._last_step == "d" or not state.room or "road" in state.room.lower():
                state.room = "Newhaven, Arena"
                state.exits = [x for x in state.exits if x != "d"]
            else:
                self._last_step = ""
        if self._in_camp and paths.is_dangerous(state.room):
            self._camp(state, send)
            return
        if self._in_camp:
            step = paths.step_toward_arena(state.room, state.exits)
            if step and self._go(send, step, state):
                return
            if self._map_step(state, send):
                return
            self._camp(state, send)
            return
        step = paths.step_toward_arena(state.room, state.exits)
        if step and self._go(send, step, state):
            return
        if self._map_step(state, send):
            return
        self._cmd(send, "look", state)
