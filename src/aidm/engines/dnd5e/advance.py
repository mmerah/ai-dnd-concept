from collections.abc import Mapping

from pydantic import Field, ValidationError

from aidm.engines.counters import Counter, adjust
from aidm.engines.loader import Advancement, AdvancementOffer, ProposalBase
from aidm.state.apply import apply_effect
from aidm.state.base import PLAYER_ID, Entity, Slug
from aidm.state.effects import TraitChange
from aidm.state.facts import Fact
from aidm.state.packs import Content, ContentRef, Record, is_int_fact
from aidm.state.world import GameState

from . import equipment, pools, spells
from .content import ENGINE_DIR, SUBCLASSES, lookup
from .mechanics import (
    ABILITIES,
    Mechanics,
    Sheet,
    add_ref,
    counter_of,
    drop_counter,
    grant_counter,
    modifier,
    read,
    set_number,
    sheet_of,
    write,
)

ADVANCEMENT_READY = "advancement-ready"
LEVEL = "level"
MILESTONE_LEVEL = "milestone-level"
MAX_ABILITY = 20
# What every class calls the feature that hands the player ability points. The rows also carry a
# running `ability-score-bonuses` tally, but the pack's rogue counts down as often as up (level 10
# says 3, level 11 says 2), so the feature is the signal and the tally never reaches a sheet.
IMPROVEMENT = "Ability Score Improvement"
ABILITY_TALLY = "ability-score-bonuses"
# The human word for each of `spells.KEYS`, in its order.
SPELL_KINDS = ("cantrip", "spell")
# A level row's int fact that is a pool rather than a dial, and what refills it. Every other int
# fact the rows carry — a die size, a range, a count of things known — is a plain number.
# ponytail: a pool the pack spells as anything but an int fact stays at the size creation gave it —
# rage ("2" ... "unlimited"), lay on hands, divine sense, bardic inspiration. They scale by class
# prose, not by a row fact; see `.scratch/advancement-correctness/spec.md`.
POOL_FACTS: Mapping[Slug, str] = {
    "action-surges": "short-rest",
    "channel-divinity-charges": "short-rest",
    "indomitable-uses": "long-rest",
    "ki-points": "short-rest",
    "mystic-arcanum-level-6": "long-rest",
    "mystic-arcanum-level-7": "long-rest",
    "mystic-arcanum-level-8": "long-rest",
    "mystic-arcanum-level-9": "long-rest",
    "sorcery-points": "long-rest",
}

# How many spells of one kind a level adds, and every spell it may take them from.
type SpellPool = tuple[int, tuple[ContentRef, ...]]


class LevelUp(ProposalBase):
    """One class level. Every number the level row carries the engine writes itself; this is
    what the row cannot answer."""

    picks: tuple[ContentRef, ...] = Field(
        default=(),
        description="Exactly the picks the offer asks for, from its options; a level that offers "
        "no alternatives takes none.",
    )
    spells: tuple[ContentRef, ...] = Field(
        default=(),
        description="Exactly the cantrips and spells the offer says this level adds, from the "
        "legal spells it lists.",
    )
    abilities: dict[Slug, int] = Field(
        default_factory=dict,
        description="Empty unless the offer says this level raises ability scores: then the new "
        f"value of each ability raised, spending every point the offer names, none above "
        f"{MAX_ABILITY}.",
    )
    why: str = Field(description="One short sentence the player reads before confirming.")


class Dnd5eAdvancement(Advancement):
    proposal_type = LevelUp

    def __init__(self, content: Content) -> None:
        super().__init__(ENGINE_DIR)
        self.content = content

    def offered(self, state: GameState) -> AdvancementOffer | None:
        player = state.player
        sheet = sheet_of(read(state), player)
        if player.trait(ADVANCEMENT_READY) is None and not _milestone_reached(state, sheet):
            return None
        record = self._next_row(sheet)
        if record is None:
            # The class runs out of level rows at 20, which is the end of advancement, not a fault.
            return None
        level = sheet.numbers[LEVEL] + 1
        rows = (record, *self._subclass_rows(sheet, level))
        asking = _asking(rows)
        deferred = None if asking is not None else self._deferred(sheet, level)
        asking = asking or deferred
        reading = rows if deferred is None else (*rows, deferred)
        return AdvancementOffer(
            prompt=f"{record.name} is ready to take.",
            text="\n\n".join(row.text for row in reading)
            + _spell_text(self.content, self._spell_pools(sheet, record))
            + _improvement_text(self._improvement(sheet, record)),
            granted=tuple(ref for row in rows for ref in row.granted),
            # A feature already held is off the offer for the same reason a known spell is: the
            # stale pick meets the offer's own refusal, not the opaque one `add_ref` raises.
            options=() if asking is None else _left(sheet, asking),
            choose=0 if asking is None else asking.choose or 0,
        )

    def _next_row(self, sheet: Sheet) -> Record | None:
        return lookup(self.content, level_ref(sheet, sheet.numbers[LEVEL] + 1))

    def _subclass_rows(self, sheet: Sheet, level: int) -> tuple[Record, ...]:
        """What the character's subclass carries at one level. A subclass is a second table of
        level rows, read beside the class's own from the level it was chosen at."""
        return tuple(
            row
            for ref in sheet.refs
            if ref.collection == SUBCLASSES
            for row in (lookup(self.content, ref.sibling("levels", f"{ref.index}-{level}")),)
            if row is not None
        )

    def _deferred(self, sheet: Sheet, level: int) -> Record | None:
        """The subclass row whose own choice is still owed. A subclass chosen at the level its
        table starts brings that level's row too late to pick from — a ranger meets Hunter's Prey
        at 3 and takes it at 4 — so an unanswered choice is carried until it is made. A row is
        answered by any of its options being held, which the fighter's shared fighting styles
        make generous: `champion-10` reads as answered by the style taken at level 1, and is
        offered at its own level rather than by this."""
        for below in range(1, level):
            for row in self._subclass_rows(sheet, below):
                taken = len(row.options) - len(_left(sheet, row))
                if row.choose is not None and row.choose > taken:
                    return row
        return None

    def _improvement(self, sheet: Sheet, row: Record) -> int:
        """How many ability points the level hands over: two for each improvement among the
        features it grants. A character already at the cap everywhere spends what room is left,
        so a maxed-out sheet cannot deadlock the level."""
        granted = sum(2 for ref in row.granted if self.content.require(ref).name == IMPROVEMENT)
        room = sum(MAX_ABILITY - sheet.numbers.get(ability, MAX_ABILITY) for ability in ABILITIES)
        return min(granted, room)

    def _require_row(self, sheet: Sheet) -> Record:
        row = self._next_row(sheet)
        if row is None:
            raise ValueError(f"there is no {level_ref(sheet, sheet.numbers[LEVEL] + 1)} to take")
        return row

    def _spell_pools(self, sheet: Sheet, row: Record) -> tuple[SpellPool, ...]:
        """What this level adds for each of `spells.KEYS`, with every spell it may take them from: a
        cantrip, or a spell up to the highest slot level the row leaves the character holding. A
        spell already on the sheet is left out, so a stale pick meets the offer's own refusal
        instead of the duplicate one `add_ref` raises further in."""
        klass = class_ref(sheet)
        name = self.content.require(klass).name
        highest = max((int(key[5:]) for key in row.facts if key.startswith("slot-")), default=0)
        pools: list[SpellPool] = []
        for kind, count in enumerate(spells.growth(klass.index, sheet.numbers, row)):
            levels = range(1) if kind == 0 else range(1, highest + 1)
            legal = (
                tuple(
                    ref
                    for level in levels
                    for ref in spells.castable(self.content, name, level)
                    if ref not in sheet.refs
                )
                if count
                else ()
            )
            pools.append((count, legal))
        return tuple(pools)

    def advance(self, draft: GameState, proposal: ProposalBase) -> tuple[Fact, ...]:
        assert isinstance(proposal, LevelUp)
        mechanics = read(draft)
        player = draft.player
        sheet = sheet_of(mechanics, player)
        why = proposal.why
        row = self._require_row(sheet)  # read before the level bump moves it
        owed = self._improvement(sheet, row)
        recharge = spells.slot_recharge(class_ref(sheet).index)
        facts = [
            *_apply_row(player, sheet, row, recharge, why),
            *_improve(player, sheet, owed, proposal.abilities, why),
        ]
        # What the row grants is never proposed: the model picks only what the offer offers, and
        # the pools a granted feature brings are read off the sheet once it holds the refs.
        for ref in (*row.granted, *proposal.picks, *proposal.spells):
            facts.append(add_ref(player, sheet, ref, why))
        # A subclass picked at this very level hands over its own row for it, so the second table
        # is read after the picks land rather than off the sheet the level began with.
        for extra in self._subclass_rows(sheet, sheet.numbers[LEVEL]):
            facts.extend(_apply_row(player, sheet, extra, recharge, why))
            facts.extend(add_ref(player, sheet, ref, why) for ref in extra.granted)
        modifiers = {ability: modifier(sheet.numbers[ability]) for ability in ABILITIES}
        facts.extend(_prose_pools(player, sheet, modifiers, why))
        facts.extend(self._armor_class(draft, mechanics, player, sheet, modifiers, why))
        facts.extend(
            _raise_pool(player, sheet, "hp", _hit_points(sheet) - _maximum(sheet, "hp"), why)
        )
        write(draft, mechanics)
        if player.trait(ADVANCEMENT_READY) is not None:
            change = TraitChange(
                mode="remove", entity_id=PLAYER_ID, trait_id=ADVANCEMENT_READY, why=why
            )
            facts.extend(apply_effect(draft, change))
        return tuple(facts)

    def _armor_class(
        self,
        draft: GameState,
        mechanics: Mechanics,
        player: Entity,
        sheet: Sheet,
        modifiers: Mapping[Slug, int],
        why: str,
    ) -> list[Fact]:
        """An improvement that raises Dexterity — or the ability a class's Unarmored Defense reads —
        moves the armour class with it. Creation derives this number the same way, off the armour
        the character carries; a level-up is the one moment play re-asks the question."""
        worn = tuple(
            ref
            for entity in draft.world.entities.values()
            if entity.parent_id == player.id
            for ref in (mechanics.sheets.get(entity.id) or Sheet()).refs
        )
        armor = equipment.armor_class(self.content, worn, modifiers, sheet.refs)
        if sheet.numbers.get("armor-class") == armor:
            return []
        return set_number(player, sheet, "armor-class", armor, why)

    def violation(
        self, state: GameState, offer: AdvancementOffer, proposal: ProposalBase
    ) -> str | None:
        assert isinstance(proposal, LevelUp)
        if outside := sorted(str(ref) for ref in proposal.picks if ref not in offer.options):
            allowed = ", ".join(str(ref) for ref in offer.options) or "(none)"
            return f"{', '.join(outside)} is not on offer here. The legal picks are: {allowed}"
        if len(proposal.picks) != offer.choose:
            return (
                f"this offer takes exactly {offer.choose} picks, the proposal makes "
                f"{len(proposal.picks)}"
            )
        named = (*proposal.picks, *proposal.spells)
        if twice := sorted({str(ref) for ref in named if named.count(ref) > 1}):
            return f"{', '.join(twice)} is named twice; a level takes each pick and spell once"
        if wrong := self._spell_violation(state, proposal.spells):
            return wrong
        draft = state.draft()
        try:
            _ = self.advance(draft, proposal)
            _ = draft.committed()
        except ValidationError as invalid:
            return f"the sheet this leaves is invalid: {invalid.errors()[0]['msg']}"
        except ValueError as refused:
            return str(refused)
        return None

    def _spell_violation(self, state: GameState, named: tuple[ContentRef, ...]) -> str | None:
        sheet = sheet_of(read(state), state.player)
        row = self._next_row(sheet)
        pools = self._spell_pools(sheet, row) if row is not None else ((0, ()), (0, ()))
        legal = tuple(ref for _, pool in pools for ref in pool)
        if outside := sorted(str(ref) for ref in named if ref not in legal):
            return (
                f"{', '.join(outside)} is not a spell this level adds. Name only spells the offer "
                "lists as legal"
            )
        for kind, (count, pool) in enumerate(pools):
            taken = sum(1 for ref in named if ref in pool)
            if taken != count:
                return f"this level adds exactly {_kinds(kind, count)}, the proposal names {taken}"
        return None


def _asking(rows: tuple[Record, ...]) -> Record | None:
    """The one row of a level that asks for a pick. An offer holds one pair, and once a subclass
    is on the sheet no level of the shipped pack reads two rows that both carry a choice — the
    two that do, `ranger-3` and `sorcerer-1`, are asking for the subclass itself."""
    return next((row for row in rows if row.choose is not None), None)


def _left(sheet: Sheet, row: Record) -> tuple[ContentRef, ...]:
    return tuple(ref for ref in row.options if ref not in sheet.refs)


def _kinds(kind: int, count: int) -> str:
    return f"{count} {SPELL_KINDS[kind]}{'' if count == 1 else 's'}"


def _improvement_text(owed: int) -> str:
    """The row's prose names the feature, never the points, and the advisor cannot spend what it
    cannot count."""
    if not owed:
        return ""
    return (
        f"\n\nRaises ability scores by {owed} points in all, every point spent, none of them "
        f"leaving a score above {MAX_ABILITY}."
    )


def _spell_text(content: Content, pools: tuple[SpellPool, ...]) -> str:
    """The advisor cannot pick from a list it cannot see, so the offer carries the legal spells."""
    lines = [
        f"Adds {_kinds(kind, count)}, from: "
        + ", ".join(f"{content.require(ref).name} [{ref}]" for ref in pool)
        for kind, (count, pool) in enumerate(pools)
        if count
    ]
    return "\n\n" + "\n".join(lines) if lines else ""


def _hit_points(sheet: Sheet) -> int:
    """The whole hit point maximum the sheet's level is worth, not the level's own share: 5e's
    fixed-hp rule is the full die at level 1 and its average after, and a Constitution modifier
    that rises is worth a point on every level already taken. Deriving the total rather than
    adding to it is what makes that retroactive raise fall out. The die is a class fact and lands
    on the sheet with the class ref."""
    die = sheet.numbers.get("hit-die")
    if die is None:
        raise ValueError("this character's class names no hit-die to size a level's hp from")
    level = sheet.numbers[LEVEL]
    grown = die + (level - 1) * (die // 2 + 1) + level * modifier(sheet.numbers["constitution"])
    return max(level, grown)


def _maximum(sheet: Sheet, key: Slug) -> int:
    held = sheet.counters.get(key)
    return 0 if held is None or held.maximum is None else held.maximum


def _improve(
    player: Entity, sheet: Sheet, owed: int, chosen: Mapping[Slug, int], why: str
) -> list[Fact]:
    facts: list[Fact] = []
    spent = 0
    for ability, value in sorted(chosen.items()):
        held = sheet.numbers.get(ability)
        if ability not in ABILITIES or held is None:
            raise ValueError(f"{ability!r} is not an ability score this character holds")
        if value > MAX_ABILITY:
            raise ValueError(f"an ability score cannot pass {MAX_ABILITY}: {ability} is {value}")
        if value <= held:
            raise ValueError(
                f"{ability} is already {held}, so raising it to {value} spends nothing"
            )
        spent += value - held
        facts.extend(set_number(player, sheet, ability, value, why))
    if spent != owed:
        raise ValueError(
            f"this level raises ability scores by {owed} points in all, the proposal raises {spent}"
        )
    return facts


def _prose_pools(
    player: Entity, sheet: Sheet, modifiers: Mapping[Slug, int], why: str
) -> list[Fact]:
    """A pool the pack counts nowhere still grows: rage with the level, lay on hands five hit
    points a level, a bard's inspiration with its Charisma. `pools` holds the class prose."""
    facts: list[Fact] = []
    for ref in sheet.refs:
        found = pools.feature_pool(ref.index, sheet.numbers[LEVEL], modifiers)
        if found is not None:
            key, counter = found
            facts.extend(_set_pool(player, sheet, key, counter.maximum or 0, counter.recharge, why))
    return facts


def _apply_row(player: Entity, sheet: Sheet, row: Record, recharge: str, why: str) -> list[Fact]:
    """Every int fact the level row carries, written the way the sheet holds it: the pools of
    `POOL_FACTS` and the spell slots as counters, the rest — the level itself, the proficiency
    bonus, the spell counts, each class's own dials — as numbers. A fact the row does not carry
    is left alone: a prepared caster's list size is prose, so no number claims to count it."""
    facts: list[Fact] = []
    slots: dict[Slug, int] = {}
    for key, value in sorted(row.facts.items()):
        if not is_int_fact(value):
            continue
        if key == ABILITY_TALLY:
            continue  # see IMPROVEMENT: the pack's rogue tally would render a number the refs deny
        if key.startswith("slot-"):
            slots[key] = value
        elif key in POOL_FACTS:
            facts.extend(_set_pool(player, sheet, key, value, POOL_FACTS[key], why))
        elif sheet.numbers.get(key) != value:
            facts.extend(set_number(player, sheet, key, value, why))
    for key, value in slots.items():
        facts.extend(_set_pool(player, sheet, key, value, recharge, why))
    return [*facts, *_drop_stale_slots(player, sheet, row, why)]


def _milestone_reached(state: GameState, sheet: Sheet) -> bool:
    here = sheet_of(read(state), state.world.require(state.player_location))
    earned = here.numbers.get(MILESTONE_LEVEL)
    return earned is not None and sheet.numbers[LEVEL] < earned


def _raise_pool(player: Entity, sheet: Sheet, key: Slug, added: int, why: str) -> list[Fact]:
    """A pool grows by its ceiling and by what fills the room, so a level-up is felt at once."""
    counter = counter_of(sheet, player, key)
    if added <= 0:
        return []
    counter.maximum = (counter.maximum or 0) + added
    return adjust(player, key, counter, added, why)


def _set_pool(
    player: Entity, sheet: Sheet, key: Slug, maximum: int, recharge: str | None, why: str
) -> list[Fact]:
    """A pool the character does not hold yet arrives full: no level grants a spent one, and the
    first level that opens a new slot level would otherwise have nothing to raise."""
    held = sheet.counters.get(key)
    if held is None:
        counter = Counter(current=maximum, maximum=maximum, recharge=recharge)
        return [grant_counter(player, sheet, key, counter, why)]
    # Font of Inspiration turns a bard's pool over on a short rest from level 5; nothing else moves.
    held.recharge = recharge
    return _raise_pool(player, sheet, key, maximum - (held.maximum or 0), why)


def _drop_stale_slots(player: Entity, sheet: Sheet, row: Record, why: str) -> list[Fact]:
    """Pact magic migrates its one slot key rather than accumulating: a warlock reaching level 3
    trades `slot-1` for `slot-2`. Every other table only ever adds, so nothing else is dropped."""
    named = {key for key in row.facts if key.startswith("slot-")}
    if not named:
        return []
    stale = sorted(key for key in sheet.counters if key.startswith("slot-") and key not in named)
    return [drop_counter(player, sheet, key, why) for key in stale]


def class_ref(sheet: Sheet) -> ContentRef:
    classes = [ref for ref in sheet.refs if ref.collection == "classes"]
    if len(classes) != 1:
        held = ", ".join(str(ref) for ref in classes) or "(none)"
        raise ValueError(f"a 5e character advances by exactly one class, and this one holds {held}")
    return classes[0]


def level_ref(sheet: Sheet, level: int) -> ContentRef:
    ref = class_ref(sheet)
    return ref.sibling("levels", f"{ref.index}-{level}")
