"""Live snapshot of the MajorMUD session."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import paths


def pool_label(
    name: str,
    cur: int | None,
    mx: int | None = None,
    *,
    pct: int | None = None,
    stale: bool = False,
    ready: bool = False,
    ready_name: str = "TRAIN",
) -> str:
    """HP, MA, and EXP footer text. Flags pick the shape; one builder."""
    if ready:
        shown = pct if pct is not None else 100
        return f"{ready_name} {shown}%"
    if cur is None and pct is None:
        return ""
    mark = "?" if stale else ""
    if cur is not None and mx:
        core = f"{name} {cur}/{mx}"
        if pct is not None:
            return f"{core} {pct}%{mark}"
        return core
    if cur is not None:
        return f"{name} {cur}"
    if pct is not None:
        return f"{name} {pct}%{mark}"
    return ""


@dataclass
class WorldState:
    hp: int | None = None
    max_hp: int | None = None
    max_hp_known: bool = False
    ma: int | None = None
    max_ma: int | None = None
    cast_fail: str = ""
    blessed: bool = False
    room: str = ""
    exits: list[str] = field(default_factory=list)
    mobs: list[str] = field(default_factory=list)
    things: list[str] = field(default_factory=list)
    in_combat: bool = False
    combat_off: bool = False
    in_shop: bool = False
    resting: bool = False
    last_kill: str = ""
    prompt_seq: int = 0
    in_realm: bool = False
    dark: bool = False
    geared: bool = False
    needs_scan: bool = False
    scanned: bool = False
    look_scan: bool = False
    saw_here: bool = False
    saw_see: bool = False
    whiff: bool = False
    blocked: bool = False
    pvp_hit: str = ""
    self_names: set[str] = field(default_factory=set)
    last_actor: str = ""
    friendly_fire: str = ""
    invited_by: str = ""
    following: str = ""
    followers: list[str] = field(default_factory=list)
    backrank: bool = False
    party_fail: str = ""
    sneak_try: bool = False
    sneak_ok: bool = False
    sneak_fail: bool = False
    sneak_busy: bool = False
    mortal: bool = False
    ally_mortal: str = ""
    aided: bool = False
    bleeding: bool = False
    dragging: str = ""
    drag_fail: bool = False
    afraid: bool = False
    left_party: bool = False
    # lowercase given name -> spelling we saw. Observed hits only; no invented HP.
    ally_hurt: dict[str, str] = field(default_factory=dict)
    # lowercase given name -> damage seen since last heal / they left.
    ally_dmg: dict[str, int] = field(default_factory=dict)
    # lowercase given name -> they asked for a heal (`say heal`).
    heal_asks: dict[str, str] = field(default_factory=dict)
    # From `exp` / train. Max HP/MA stay put until a level or train.
    level: int | None = None
    trained: bool = False
    exp: int | None = None
    exp_needed: int | None = None
    exp_next: int | None = None
    exp_pct: int | None = None
    exp_known: bool = False
    exp_stale: bool = False
    exp_asked: bool = False
    # This fight's `You gain N` already counted. Kill must not re-ask `exp`.
    exp_gained: bool = False

    def apply(self, event: dict[str, object]) -> None:
        kind = event.get("kind")
        if kind == "prompt":
            self.hp = int(event["hp"])  # type: ignore[arg-type]
            self._note_max(event.get("max_hp"))
            self._note_ma(event.get("ma"), event.get("max_ma"))
            self.prompt_seq += 1
            self.in_realm = True
            self.resting = False
            self._note_hits()
            return
        if kind == "hits":
            self.hp = int(event["hp"])  # type: ignore[arg-type]
            self._note_max(event.get("max_hp"))
            self._note_ma(event.get("ma"), event.get("max_ma"))
            self._note_hits()
            return
        if kind == "mana":
            self._note_ma(event.get("ma"), event.get("max_ma"))
            return
        if kind == "trained":
            self.forget_maxes()
            self.forget_exp()
            lvl = event.get("level")
            if isinstance(lvl, int) and lvl > 0:
                self._note_level(lvl)
            return
        if kind == "level":
            lvl = event.get("level")
            if isinstance(lvl, int) and lvl > 0:
                self._note_level(lvl)
            self._note_exp(event)
            return
        if kind == "experience":
            self._gain_exp(event.get("amount"))
            return
        if kind == "cast_fail":
            self.cast_fail = str(event.get("reason") or "fail")
            return
        if kind == "buff":
            name = str(event.get("name") or "").strip().lower()
            if name == "bless":
                self.blessed = bool(event.get("on", True))
            return
        if kind == "invited":
            who = str(event.get("name") or "").strip()
            if who and not event.get("by_me"):
                self.invited_by = who
            return
        if kind == "following":
            self.following = str(event.get("name") or "").strip()
            self.invited_by = ""
            return
        if kind == "followed":
            who = str(event.get("name") or "").strip()
            if who and who not in self.followers:
                self.followers.append(who)
            return
        if kind == "backrank":
            self.backrank = True
            return
        if kind == "party_fail":
            self.party_fail = str(event.get("reason") or "fail")
            self.invited_by = ""
            if self.party_fail == "invite":
                self.following = ""
            if self.party_fail == "party":
                self.backrank = False
            return
        if kind == "sneak_try":
            self.sneak_try = True
            return
        if kind == "sneak_ok":
            self.sneak_ok = True
            return
        if kind == "sneak_fail":
            self.sneak_fail = True
            self.sneak_busy = event.get("reason") == "busy"
            return
        if kind == "mortal":
            who = str(event.get("name") or "").strip()
            if not who or who.lower() == "you":
                self.mortal = True
                self.bleeding = True
                self.aided = False
            else:
                self.ally_mortal = who
            return
        if kind == "aided":
            self.aided = True
            self.bleeding = False
            who = str(event.get("name") or "").strip()
            if not who or who.lower() == "you":
                self.mortal = False
                self.bleeding = False
            elif self.ally_mortal and who.lower() in self.ally_mortal.lower():
                self.ally_mortal = ""
            else:
                self.ally_mortal = ""
            return
        if kind == "drag_fail":
            self.drag_fail = True
            return
        if kind == "dragging":
            self.dragging = str(event.get("name") or "").strip()
            return
        if kind == "afraid":
            self.afraid = True
            return
        if kind == "left":
            self.following = ""
            self.backrank = False
            self.invited_by = ""
            self.left_party = True
            return
        if kind == "exits":
            self.exits = list(event.get("exits") or [])  # type: ignore[arg-type]
            if self.look_scan and not self.saw_here:
                self.mobs = []
            if self.look_scan and not self.saw_see:
                self.things = []
            self.look_scan = False
            self.scanned = True
            self.needs_scan = False
            return
        if kind == "also_here":
            mobs: list[str] = []
            for name in event.get("mobs") or []:
                if not isinstance(name, str):
                    continue
                mobs.extend(paths.peel_presence(name, self.self_names))
            self.mobs = mobs
            self.saw_here = True
            self.look_scan = False
            self.scanned = True
            self.needs_scan = False
            present = {n.lower() for n in paths.players_in(self.mobs, self.self_names)}
            self.ally_hurt = {
                k: v for k, v in self.ally_hurt.items() if k in present or v.lower() in present
            }
            self.ally_dmg = {k: v for k, v in self.ally_dmg.items() if k in self.ally_hurt}
            self.heal_asks = {
                k: v for k, v in self.heal_asks.items() if k in present or v.lower() in present
            }
            return
        if kind == "you_see":
            self.things = list(event.get("things") or [])  # type: ignore[arg-type]
            self.saw_see = True
            self.scanned = True
            return
        if kind == "heal_ask":
            who = str(event.get("name") or "").strip()
            if not who or who.lower() == "you":
                return
            if not self._is_toon(who):
                return
            self._remember_toon(who)
            self.heal_asks[who.lower()] = who
            return
        if kind == "said":
            self.whiff = True
            self.in_combat = False
            aimed = str(event.get("aimed") or "")
            if aimed:
                self.mobs = [m for m in self.mobs if not paths.same_mob(m, aimed)]
                if paths.is_home_account(aimed) or paths.is_self(aimed, self.self_names):
                    self.friendly_fire = aimed
            return
        if kind == "drop":
            name = str(event.get("name") or "")
            if name and name not in self.things:
                self.things.append(name)
            return
        if kind == "killed":
            self.last_kill = str(event.get("name") or "")
            self.in_combat = False
            self.needs_scan = True
            dead = self.last_kill
            self.mobs = paths.without_dead(self.mobs, dead)
            self._drop_ally_hurt(dead)
            if self.ally_mortal and dead.lower() in self.ally_mortal.lower():
                self.ally_mortal = ""
            # A full Exp: line is enough. Kill must not flip needs_exp.
            if not self.has_exp_reading() and not self.exp_gained:
                self.exp_stale = True
                self.exp_asked = False
            self.exp_gained = False
            return
        if kind == "combat":
            self.in_combat = True
            actor = event.get("actor")
            if isinstance(actor, str) and actor.strip():
                self.last_actor = actor.strip()
                if paths.is_self(actor, self.self_names):
                    self.self_names.add(actor.strip().lower())
                self._remember_toon(actor)
            name = event.get("name")
            if isinstance(name, str) and name:
                for piece in paths.peel_presence(name, self.self_names):
                    toon = self._is_toon(piece)
                    if toon and not paths.is_self(piece, self.self_names):
                        self.pvp_hit = piece
                    if not toon and paths.is_self(piece, self.self_names):
                        continue
                    if piece not in self.mobs:
                        self.mobs.append(piece)
                        self.saw_here = True
                        self.look_scan = False
            self._note_ally_hit(event)
            return
        if kind == "actor":
            who = str(event.get("name") or "").strip()
            if who:
                self.last_actor = who
            return
        if kind == "combat_off":
            self.in_combat = False
            self.pvp_hit = ""
            self.combat_off = True
            # Fight is over — drop leftover farm names. Keep party / PCs.
            # A later arrive / Also here / combat line is the live list.
            self.mobs = [m for m in self.mobs if not paths.lop_in([m])]
            # Already had Also here / a move scan — do not treat Off as empty.
            if not paths.lop_in(self.mobs) and not self.scanned:
                self.needs_scan = True
            return
        if kind == "inventory":
            blob = str(event.get("text") or "").lower()
            self.geared = "(weapon" in blob or "weapon hand" in blob
            return
        if kind == "arrive":
            name = str(event.get("name") or "")
            for piece in paths.peel_presence(name, self.self_names):
                if piece and piece not in self.mobs:
                    self.mobs.append(piece)
                if piece:
                    self._remember_toon(piece)
            self.saw_here = True
            self.look_scan = False
            self.scanned = True
            self.needs_scan = False
            return
        if kind == "leave":
            name = str(event.get("name") or "").lower()
            if name:
                self.mobs = [
                    m for m in self.mobs if name not in m.lower() and m.lower() not in name
                ]
                self._drop_ally_hurt(name)
            return
        if kind == "rest":
            self.resting = True
            self.in_combat = False
            actor = event.get("actor")
            if isinstance(actor, str) and actor.strip():
                self.last_actor = actor.strip()
            return
        if kind == "shop":
            self.in_shop = True
            return
        if kind == "bought":
            return
        if kind == "room":
            title = str(event.get("title") or "")
            if self.in_combat and not _looks_like_place(title):
                return
            moved = bool(self.room) and title != self.room
            self.room = title
            self.dark = False
            if moved:
                if self.in_combat:
                    self.combat_off = True
                self.mobs = []
                self.things = []
                self.scanned = False
                self.in_combat = False
                self._wipe_allies()
            if _looks_like_place(title) and not self.in_combat:
                self.look_scan = True
                self.saw_here = False
                self.saw_see = False
            return
        if kind == "dark":
            self.dark = True
            return
        if kind == "cannot":
            text = str(event.get("text") or "").lower()
            if "may not drag" in text or "cannot drag" in text or "can't drag" in text:
                self.drag_fail = True
            if "no exit" in text or "can't go" in text or "cannot go" in text:
                self.blocked = True
                if "d" in self.exits:
                    self.exits = [x for x in self.exits if x != "d"]
            return

    def _is_toon(self, name: str) -> bool:
        extras = self.self_names
        return (
            paths.is_given_name(name, extras)
            or paths.is_player(name)
            or paths.is_home_account(name)
        )

    def _remember_toon(self, name: str) -> None:
        """Keep the other PC in the room list so party can invite/join."""
        extras = self.self_names
        for piece in paths.peel_presence(name, extras):
            if not piece or not self._is_toon(piece):
                continue
            if piece not in self.mobs:
                self.mobs.append(piece)
                self.saw_here = True
                self.look_scan = False

    def _note_ally_hit(self, event: dict[str, object]) -> None:
        victim = event.get("victim")
        if not isinstance(victim, str):
            return
        who = victim.strip()
        if not who or who.lower() == "you":
            return
        if not self._is_toon(who):
            return
        self._remember_toon(who)
        dmg = event.get("damage")
        if isinstance(dmg, int) and dmg > 0:
            self.ally_hurt[who.lower()] = who
            self.ally_dmg[who.lower()] = self.ally_dmg.get(who.lower(), 0) + dmg

    def ally_taken(self, key: str) -> int:
        return int(self.ally_dmg.get(key.strip().lower(), 0))

    def forget_ally(self, *names: str) -> None:
        lows = {name.strip().lower() for name in names if name and name.strip()}
        if not lows:
            return
        self.ally_hurt = {
            k: v
            for k, v in self.ally_hurt.items()
            if k not in lows and v.lower() not in lows
        }
        self.ally_dmg = {k: v for k, v in self.ally_dmg.items() if k not in lows}
        self.heal_asks = {
            k: v
            for k, v in self.heal_asks.items()
            if k not in lows and v.lower() not in lows
        }

    def _wipe_allies(self) -> None:
        self.ally_hurt.clear()
        self.ally_dmg.clear()
        self.heal_asks.clear()

    def _drop_ally_hurt(self, raw: str) -> None:
        low = raw.strip().lower()
        if not low:
            return
        self.ally_hurt = {
            k: v
            for k, v in self.ally_hurt.items()
            if k not in low and v.lower() not in low and low not in k
        }
        self.ally_dmg = {
            k: v for k, v in self.ally_dmg.items() if k not in low and low not in k
        }
        self.heal_asks = {
            k: v
            for k, v in self.heal_asks.items()
            if k not in low and v.lower() not in low and low not in k
        }

    def empty_if_look_missed(self, kinds: set[str], screen: str = "") -> None:
        if "exits" not in kinds:
            return
        if self.saw_here or "also_here" in kinds or "arrive" in kinds:
            return
        if "also here:" in screen.lower():
            return
        self.mobs = []
        self._wipe_allies()
        self.scanned = True
        self.look_scan = False

    def needs_maxes(self) -> bool:
        """True when the footer cannot show a real max HP and/or max MA."""
        if self.hp is None:
            return False
        if not self.max_hp_known:
            return True
        return self.ma is not None and self.max_ma is None

    def forget_maxes(self) -> None:
        """Level/train changes pools. Keep last numbers on the bar until `health`."""
        self.max_hp_known = False
        self.max_ma = None
        self.trained = True

    def forget_exp(self) -> None:
        """Level/train resets the exp bar. Ask `exp` again."""
        self.exp_known = False
        self.exp_stale = True
        self.exp_asked = False
        self.exp_pct = None
        self.exp_gained = False

    def has_exp_reading(self) -> bool:
        """True when chrome has current, total, and percent from `Exp:`."""
        return (
            bool(self.exp_known)
            and self.exp is not None
            and self.exp_next is not None
            and self.exp_pct is not None
        )

    def needs_exp(self) -> bool:
        """True only when we have no current/total/percent yet."""
        if self.hp is None:
            return False
        if self.has_exp_reading():
            return False
        if self.exp_asked:
            return False
        if self.exp_stale:
            return True
        return not self.exp_known

    def can_train(self) -> bool:
        if not self.exp_known:
            return False
        if self.exp_needed is not None and self.exp_needed <= 0:
            return True
        return self.exp_pct is not None and self.exp_pct >= 100

    def at_trainer(self) -> bool:
        return paths.is_trainer(self.room)

    def exp_label(self) -> str:
        """Footer progress: TRAIN when ready, else EXP current/total percent."""
        if self.can_train():
            return pool_label(
                "EXP",
                self.exp,
                self.exp_next,
                pct=self.exp_pct,
                ready=True,
            )
        if self.exp_pct is None:
            return ""
        return pool_label(
            "EXP",
            self.exp,
            self.exp_next,
            pct=self.exp_pct,
            stale=self.exp_stale,
        )

    def _note_level(self, lvl: int) -> None:
        if self.level is not None and lvl > self.level:
            self.forget_maxes()
            self.forget_exp()
        self.level = lvl

    def _note_exp(self, event: dict[str, object]) -> None:
        """Set from the `Exp:` status line. Replace current; never add a gain."""
        exp = event.get("exp")
        if not isinstance(exp, int):
            return
        self.exp = exp
        needed = event.get("needed")
        nxt = event.get("next")
        pct = event.get("pct")
        if isinstance(needed, int):
            self.exp_needed = needed
        if isinstance(nxt, int) and nxt > 0:
            self.exp_next = nxt
        if isinstance(pct, int):
            self.exp_pct = pct
        elif self.exp_next:
            self.exp_pct = min(999, (self.exp * 100) // self.exp_next)
        self.exp_known = True
        self.exp_stale = False
        self.exp_asked = True
        self.exp_gained = False

    def _gain_exp(self, amount: object) -> None:
        if not isinstance(amount, int) or amount <= 0:
            if self.exp_known:
                self.exp_stale = True
                self.exp_asked = False
            return
        if not self.exp_known or self.exp is None:
            self.exp_stale = True
            self.exp_asked = False
            return
        self.exp += amount
        if self.exp_needed is not None:
            self.exp_needed = max(0, self.exp_needed - amount)
        if self.exp_next and self.exp_next > 0:
            self.exp_pct = min(999, (self.exp * 100) // self.exp_next)
        self.exp_stale = False
        self.exp_gained = True

    def _note_max(self, mx: object) -> None:
        if isinstance(mx, int) and mx > 0:
            self.max_hp = max(self.max_hp or 0, mx)
            self.max_hp_known = True
        elif self.hp is not None:
            self.max_hp = max(self.max_hp or 0, self.hp)

    def _note_ma(self, ma: object, mx: object) -> None:
        if isinstance(ma, int):
            self.ma = ma
            # Prompt [HP=n/MA=n] is current only. Never stamp max from that.
            if self.max_ma is not None and ma > self.max_ma:
                self.max_ma = ma
        if isinstance(mx, int) and mx > 0:
            self.max_ma = max(self.max_ma or 0, mx)

    def hp_label(self) -> str:
        """Footer vitals: current/max when a max is known. Prompt MA is current only."""
        hits = pool_label("HP", self.hp, self.max_hp)
        if not hits or self.ma is None:
            return hits
        ma = pool_label("MA", self.ma, self.max_ma)
        return f"{hits}  {ma}" if ma else hits

    def _note_hits(self) -> None:
        if self.hp is None:
            return
        if self.hp <= 0 and not self.aided:
            self.mortal = True
            self.bleeding = True
        elif self.hp >= 1:
            self.mortal = False
            self.bleeding = False

    def hp_ratio(self) -> float | None:
        if self.hp is None or not self.max_hp:
            return None
        return self.hp / self.max_hp


def _looks_like_place(title: str) -> bool:
    low = title.lower()
    return any(
        word in low
        for word in (
            "newhaven",
            "arena",
            "shop",
            "road",
            "path",
            "entrance",
            "guild",
            "healer",
            "square",
            "store",
        )
    )
