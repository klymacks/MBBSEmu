"""Play MajorMUD: gear up, hunt lops, rest. Localhost only."""

from __future__ import annotations

import time

from . import paths, realm_map, spells
from .state import WorldState

REST_RATIO = 0.60
REST_ABS = 12
# Self-heal and party `say heal` at this ratio or below. Sit-down rest stays on REST_RATIO.
HEAL_RATIO = 0.80
HEAL_ASK = "say heal"
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
        self._spells = spells.known_spells(self.klass, spell_list)
        self._last_cast = ""
        self._cast_at = 0.0
        self._sneaking = False
        self._sneak_wait = False
        self._sneak_armed = False
        self._sneak_flop = False
        self._sneak_ready_at = 0.0
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
            self._sneak_ready_at = 0.0
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
        self._sneak_ready_at = 0.0
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
        """Following Matt: no own `u` / `d` / `sn`. Swing and heal only."""
        if self._leader_down(state):
            return False
        return bool(self._followed or state.following)

    def _own_ambush(self, state: WorldState) -> bool:
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

    def on_ambush_on(self, state: WorldState) -> list[str]:
        """Commands to pace when F8 turns ambush on. No takeover.

        Empty room (road or outside, no lops): `sn` now — break first if
        sitting. Pit with a lop: `u` so hunt can `sn` on the road. Marks
        `_sneak_wait` so `_note_sneak` treats this `sn` like a hunt send.
        """
        cmds: list[str] = []
        if not self._ninja() or not self._stealth_moves() or not state.in_realm:
            return cmds
        if self._with_leader(state):
            return cmds

        def collect(text: str) -> None:
            cmds.append(text)

        if self._lops_here(state):
            if self._in_pit(state) and not (self._hidden or self._sneaking):
                self._cmd(collect, "u", state)
            return cmds
        if self._in_pit(state) or state.in_combat:
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

    def stealth_label(self) -> str:
        if not self._ninja():
            return ""
        return "ambush" if self._stealth_moves() else "walk"

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
        self._cmd(send, f"join {who}", state)
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
        """Fail wins the payload. Armed is setup-OK, not a guaranteed hide.

        `You don't think you're sneaking` → not armed; next tick retries `sn`.
        `You may not sneak right now` → break first, then `sn` again.
        `Attempting` (or no fail) without that line → `_sneak_armed`. Wait
        ~2s, then `d`. Going down on that same prompt breaks sneak.
        After the move, `Sneaking...` → hidden (`bs`). Sound or no sneak line
        → visible (`attack`). try+fail together still fails.
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
            self._sneak_flop = True
            self._hidden = False
            if busy:
                self._need_break = True
                self._attacking = ""
            return
        if confirmed:
            self._sneaking = True
            self._sneak_armed = False
            self._sneak_wait = False
            self._sneak_ready_at = 0.0
            self._sneak_flop = False
            self._hidden = True
            return
        if not tried:
            return
        self._sneak_wait = False
        self._sneak_flop = False
        self._sneak_armed = True
        self._sneak_ready_at = time.monotonic() + SNEAK_SETTLE
        # Setup stuck — not hidden until Sneaking... after the move.
        self._sneaking = False

    def _swing_name(self, name: str) -> str:
        """Species swing name — `paths.attack_name`, nothing else."""
        return paths.attack_name(name)

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
        if self._ninja() and (self._sneaking or self._hidden):
            self._sneaking = False
            self._sneak_armed = False
            self._sneak_wait = False
            self._hidden = False
            if self._inout():
                self._ambush_out = True
            self._cmd(send, f"bs {aim}", state)
            return True
        self._sneak_wait = False
        self._cmd(send, f"attack {aim}", state)
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
        if not reason:
            return
        tried = self._last_cast.split(":", 1)[-1] if self._last_cast else ""
        if reason == "unknown" and tried:
            self._spells = [name for name in self._spells if name != tried]
        if reason == "mana" and state.ma is None:
            state.ma = 0
        if self._last_cast.startswith("buff:"):
            state.blessed = False
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
        """Damage that puts assumed ally HP at or below HEAL_RATIO. Backup to a `say heal`."""
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
        """Follower with no heal spell: `say heal` once at HEAL_RATIO or below."""
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
        if state.blessed:
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

    def request_train(self) -> None:
        """Opt in to walk to the Newhaven guild and train. No takeover."""
        self._want_train = True
        self.next_action = "train"

    def cancel_train(self) -> None:
        self._want_train = False

    def _go_train(self, state: WorldState, send) -> bool:
        """Walk to the guild and type `train`. Leader owns movement."""
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
            self._want_train = False
            self._cmd(send, "train", state)
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
            return
        if self.mode == "manual":
            if pending:
                return
            if not self._realm_maxes:
                self._asked_health = False
                self._realm_maxes = True
            if self._ask_health(state, send):
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

        if state.geared and not self.gear_done:
            self.gear_done = True
            if self.mode == "gear":
                self.mode = "hunt"

        down = self._need_rest(state) or state.mortal or state.bleeding
        may_rest = (
            not self._with_leader(state)
            or state.mortal
            or state.bleeding
            or self._recovering
        )
        if down and self.mode != "rest" and may_rest:
            if self._try_heal(state, send):
                return
            self.mode = "rest"
        if self.mode == "rest":
            self._rest(state, send)
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
            return ratio < self.rest_ratio
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
        if self._last_verb not in {"attack", "bs"}:
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
        """Sneak setup outside the pit. Never in combat, never with a lop."""
        if not self._own_ambush(state):
            return False
        if state.in_combat or self._in_pit(state) or self._lops_here(state):
            return False
        return True

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
            self._attacking = ""
        if not off or self._in_pit(state):
            self._evaded = False
            return
        self._evaded = True
        self._need_break = True
        self._attacking = ""
        self._want_look = False
        self._in_camp = False
        self._pit_fight = False
        if not self._lops_here(state):
            state.needs_scan = False

    def _break_after_leave(self, send, state: WorldState) -> bool:
        """After leaving a fight room, `break` before sneak/look/rest/aid.

        Combat can stay on in the game after the room change. Other
        commands then fail or re-aggro. One break, then the next prompt.
        Still in the pit with a monster: stay in the fight.
        """
        if not self._need_break:
            return False
        if self._with_leader(state):
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
        if self._with_leader(state):
            return False
        return (
            self._sneak_armed
            and not self._sneak_settled()
            and not self._in_pit(state)
            and not self._lops_here(state)
        )

    def _need_look(self, state: WorldState) -> bool:
        """No listed farm mob and Also here is missing or stale."""
        if self._busy_swing(state):
            return False
        if self._lops_here(state):
            return False
        if state.in_combat and self._attacking and _still_here(state, self._attacking):
            return False
        # Ambush outside the pit: `sn` / `d`, not a look this tick.
        if self._own_ambush(state) and not self._in_pit(state) and not self._want_look:
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
        """Visible ambush in the pit with lops: go set `sn` on the road.

        Just-arrived (`d`) or already in a fight: stay and swing. Hidden: `bs`.
        """
        if not self._own_ambush(state) or not self._in_pit(state):
            return False
        if not self._lops_here(state):
            return False
        if self._hidden or self._sneaking:
            return False
        if state.in_combat or self._attacking:
            return False
        if not self._healed(state):
            return False
        if self._pit_fight or self._last_step == "d":
            return False
        return True

    def _setup_sneak(self, send, state: WorldState) -> bool:
        """Retry `sn` until Attempting sticks without a fail. True if we acted.

        After aid: call on the road when nobody is still bleeding and no lops,
        wait, then `d`. Never `sn` while sitting — break first. Fail (including
        try+fail in one payload) is not armed; next tick `sn` again.
        """
        if not self._can_sneak_here(state):
            return False
        if self._hidden or self._sneak_armed or self._sneaking:
            return False
        if self._down(state):
            self._sitting = False
            self._cmd(send, "break", state)
            return True
        if self._sneak_wait:
            # New prompt without Attempting — retry now. Do not hang.
            self._sneak_wait = False
        self._sneak_flop = False
        if self._send_sneak(send, state):
            self._sneak_wait = True
            return True
        return False

    def _send_sneak(self, send, state: WorldState) -> bool:
        """Sneak only while standing, off the pit, combat off, no monsters."""
        if state.in_combat or self._in_pit(state) or self._lops_here(state):
            return False
        if self._down(state):
            self._sitting = False
            self._cmd(send, "break", state)
            return False
        self._cmd(send, "sn", state)
        return True

    def _cmd(self, send, text: str, state: WorldState) -> None:
        verb, sep, rest = text.partition(" ")
        if sep and verb.lower() in {"attack", "bs"} and rest:
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
            if step == "u" and self._ninja() and self._stealth_moves():
                self._need_break = True
            self._last_step = step
            self._step_room = state.room
            self._hidden = False
            self._sneaking = False
            self._sneak_armed = False
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
                state.exits = ["n", "e", "w", "d"]

    def _travel(self, send, step: str, state: WorldState) -> None:
        """Move. Ninja ambush always/auto sneaks first; never in pit or with lops."""
        if (
            self._own_ambush(state)
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

    def _go(self, send, step: str, state: WorldState) -> bool:
        if state.exits and step not in state.exits:
            return False
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
                return
            step = paths.step_toward_store(state.room, state.exits)
            if step:
                self._sitting = False
                self._go(send, step, state)
                return
        if "general" in room:
            step = paths.step_toward_arena(state.room, state.exits) or "n"
            self._sitting = False
            self._go(send, step, state)
            return
        if self._sitting:
            self.next_action = "healing"
            return
        if not self._sit(send, state):
            self.next_action = "waiting"

    def _gear(self, state: WorldState, send) -> None:
        if not self._looked:
            self._looked = True
            self._cmd(send, "look", state)
            return
        room = state.room.lower()
        if "armour shop" in room or "armor shop" in room:
            if self._armour_i < len(paths.ARMOUR_ITEMS):
                item = paths.ARMOUR_ITEMS[self._armour_i]
                if not self._wearing:
                    self._cmd(send, f"buy {item}", state)
                    self._wearing = True
                    return
                self._cmd(send, f"wear {item}", state)
                self._wearing = False
                self._armour_i += 1
                return
            self._travel(send, "n" if "n" in state.exits else "e", state)
            return
        if "weapon shop" in room:
            if not self._weapon_bought:
                self._cmd(send, f"buy {paths.STARTER_WEAPON}", state)
                self._weapon_bought = True
                return
            if not self._weapon_worn:
                self._cmd(send, f"wear {paths.STARTER_WEAPON}", state)
                self._weapon_worn = True
                return
            self._travel(send, "s" if "s" in state.exits else "w", state)
            return
        if "general store" in room:
            if not self._torch_bought:
                self._cmd(send, f"buy {paths.STARTER_LIGHT}", state)
                self._torch_bought = True
                return
            step = paths.leave_dead_end(state.room, state.exits) or "n"
            self._travel(send, step, state)
            return
        if paths.is_dangerous(room):
            self.gear_done = True
            self.mode = "hunt"
            self.next_action = "hunt"
            return
        if self._armour_i >= len(paths.ARMOUR_ITEMS) and self._weapon_worn and self._torch_bought:
            self.gear_done = True
            self.mode = "hunt"
            self.next_action = "hunt"
            return
        if "village entrance" in room:
            if self._armour_i < len(paths.ARMOUR_ITEMS):
                self._travel(send, "s", state)
                return
            if not self._weapon_worn:
                self._travel(send, "n", state)
                return
            if not self._torch_bought:
                self._travel(send, "w", state)
                return
            self.gear_done = True
            self.mode = "hunt"
            self.next_action = "hunt"
            return
        if "narrow path" in room:
            if not self._torch_bought:
                self._travel(send, "s", state)
                return
            self._travel(send, "w", state)
            return
        if "narrow road" in room:
            self.gear_done = True
            self.mode = "hunt"
            self.next_action = "hunt"
            return
        step = paths.step_toward_arena(state.room, state.exits)
        if step:
            self._travel(send, step, state)
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
            if self._rescue or state.ally_mortal:
                return False
            if not self._got_invite:
                return False
            if self._party_at and now - self._party_at < 6:
                return False
            self._party_at = now
            if not self._joined:
                self._cmd(send, f"join {self.leader}", state)
            else:
                self._cmd(send, f"follow {self.leader}", state)
            return True
        if self.rank in {"back", "backrank"} and not self._ranked:
            self._ranked = True
            self._party_at = now
            self._cmd(send, "backrank", state)
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
        if verb not in {"attack", "bs", "at"}:
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
            self._hidden = False
            state.last_kill = ""
            if self._own_ambush(state) and not self._in_pit(state):
                self._need_break = True
            empty = not paths.lop_in(state.mobs) and not paths.coins_in(state.things)
            if empty and not state.scanned:
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
                    self._want_look = True
        if state.scanned:
            self._want_look = False
        if self._busy_swing(state):
            self._want_look = False

    def _engage_lop(self, state: WorldState, send, live: str) -> bool:
        """Hidden/sneaking → bs. Else attack. Swing from sit. Never sn."""
        if self._party_pending(state) and not self._followed:
            return False
        if not live or self._mine(live, state):
            return False
        self._want_look = False
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
            self._attacking = aim.lower()
            self._need_swing = False
            self._pit_fight = True
            self._sneaking = False
            self._sneak_armed = False
            self._sneak_wait = False
            self._hidden = False
            self._cmd(send, f"attack {aim}", state)
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
        if self._ask_health(state, send):
            return
        if self._holding_sneak(state):
            self.next_action = "ambush"
            return
        if self._party(state, send):
            return
        if self._try_heal(state, send):
            return
        if self._try_bless(state, send):
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
        if live and self._engage_lop(state, send, live):
            self._evaded = False
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
            if (
                self._in_pit(state)
                and not self._lops_here(state)
                and not self._in_party(state)
            ):
                self._attacking = ""
                self._travel(send, "u", state)
                return
        if self.pvp and state.pvp_hit and not self._mine(state.pvp_hit, state):
            aim = self._swing_name(state.pvp_hit)
            if not aim:
                return
            if self._attacking == aim.lower():
                self.next_action = f"fighting {aim}"
                return
            self._attacking = aim.lower()
            state.in_combat = True
            self._cmd(send, f"attack {aim}", state)
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
            # Evade / road / solo empty room: sn now. Followers do not sneak.
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
                and self._healed(state)
                and not self._lops_here(state)
            ):
                if self._down(state):
                    self._sitting = False
                    self._cmd(send, "break", state)
                    return
                if self._hidden or self._sneaking or self._sneak_wait:
                    self.next_action = "ambush"
                    return
                self._travel(send, "u", state)
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
