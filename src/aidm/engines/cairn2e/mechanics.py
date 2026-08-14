from collections.abc import Mapping
from random import Random
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, TypeAdapter, model_validator

from aidm.engines.counters import (
    CounterChange,
    Pools,
    adjust,
    move_pool,
    pool,
    render_counters,
)
from aidm.engines.sheets import SheetBase, SheetMechanics
from aidm.state.apply import apply_effect, reveal_target
from aidm.state.base import Counter, Entity, EntityId, Mutable, Slug, Trait
from aidm.state.dice import roll_sum
from aidm.state.effects import WorldOp
from aidm.state.facts import Fact, entity_fact
from aidm.state.world import GameState

MAX_SLOTS = 10
MAX_ARMOR = 3
UNARMED_DIE = 4
DEPRIVED: Slug = "deprived"

type DamageDie = Literal[0, 4, 6, 8, 10, 12]
type Attribute = Literal["strength", "dexterity", "willpower"]

type Cairn2eEffect = Annotated[WorldOp | CounterChange, Field(discriminator="op")]
EFFECTS: TypeAdapter[Cairn2eEffect] = TypeAdapter(Cairn2eEffect)


class Sheet(SheetBase):
    """The one sheet shape, whether it belongs to the player or to a monster."""

    background: str = ""
    strength: Counter = Counter(current=10, maximum=10)
    dexterity: Counter = Counter(current=10, maximum=10)
    willpower: Counter = Counter(current=10, maximum=10)
    hp: Counter = Counter(current=4, maximum=4)
    gold: Counter = Counter(current=0)
    fatigue: Counter = Counter(current=0)
    # Natural armor, such as a monster's hide; worn armor is the carried items' own.
    armor: int = Field(default=0, ge=0, le=MAX_ARMOR)
    # The growth subsystem's own ledger, deliberately not offered to the Director below.
    growths: Counter = Counter(current=0)

    def counters(self) -> dict[Slug, Counter]:
        return {
            "hp": self.hp,
            "strength": self.strength,
            "dexterity": self.dexterity,
            "willpower": self.willpower,
            "gold": self.gold,
            "fatigue": self.fatigue,
        }

    @model_validator(mode="after")
    def _attributes_are_bounded(self) -> Self:
        """A scar and a week's rest both move a maximum, so every Cairn pool that has one is
        bounded."""
        unbounded = sorted(
            key
            for key, counter in (
                ("hp", self.hp),
                ("strength", self.strength),
                ("dexterity", self.dexterity),
                ("willpower", self.willpower),
            )
            if counter.maximum is None
        )
        if unbounded:
            raise ValueError(f"{unbounded} must carry a maximum")
        return self


def attribute_of(sheet: Sheet, name: Attribute) -> Counter:
    match name:
        case "strength":
            return sheet.strength
        case "dexterity":
            return sheet.dexterity
        case "willpower":
            return sheet.willpower


def saved(rolled: int, score: int) -> bool:
    """Cairn's save: roll under the attribute, where 1 always passes and 20 always fails."""
    if rolled == 1:
        return True
    if rolled == 20:
        return False
    return rolled <= score


def rolled_sheet(rng: Random) -> Sheet:
    """A newcomer is rolled up as Cairn rolls a hireling: 3d6 per attribute, 1d6 Hit Protection."""
    strength, _ = roll_sum((6, 6, 6), "strength", rng)
    dexterity, _ = roll_sum((6, 6, 6), "dexterity", rng)
    willpower, _ = roll_sum((6, 6, 6), "willpower", rng)
    hp, _ = roll_sum((6,), "hp", rng)
    return Sheet(
        strength=Counter(current=strength, maximum=strength),
        dexterity=Counter(current=dexterity, maximum=dexterity),
        willpower=Counter(current=willpower, maximum=willpower),
        hp=Counter(current=hp, maximum=hp),
    )


class ItemRules(Mutable):
    """What an item is worth in Cairn's inventory: its slots, its weapon die, its armor."""

    slots: int = Field(default=1, ge=0, le=2)
    damage: DamageDie = 0
    armor: int = Field(default=0, ge=0, le=MAX_ARMOR)
    uses: Counter | None = None

    def counters(self) -> dict[Slug, Counter]:
        return {} if self.uses is None else {"uses": self.uses}


class Mechanics(SheetMechanics[Sheet]):
    # Only authored items; anything else is one ordinary slot.
    items: dict[EntityId, ItemRules] = Field(default_factory=dict)

    def rules_of(self, item_id: EntityId) -> ItemRules:
        found = self.items.get(item_id)
        return found if found is not None else ItemRules()


# Cairn authors rules for items as well as actors, and both models forbid extra keys, so the
# payload's own keys decide which it is.
RULES: TypeAdapter[Sheet | ItemRules] = TypeAdapter(Sheet | ItemRules)


def build_mechanics(state: GameState, rules: Mapping[EntityId, dict[str, JsonValue]]) -> Mechanics:
    sheets: dict[EntityId, Sheet] = {}
    items: dict[EntityId, ItemRules] = {}
    for entity in state.world.entities.values():
        authored = rules.get(entity.id)
        match entity.kind:
            case "actor":
                sheets[entity.id] = Sheet.model_validate(authored or {})
            case "item":
                if authored:
                    items[entity.id] = ItemRules.model_validate(authored)
            case _:
                if authored:
                    raise ValueError(
                        f"cairn2e writes mechanics for actors and items only, not {entity.id!r}"
                    )
    return Mechanics(sheets=sheets, items=items)


def check_items(state: GameState, mechanics: Mechanics) -> None:
    if gone := sorted(set(mechanics.items) - state.world.all_ids()):
        raise ValueError(f"mechanics name items the world does not hold: {gone}")
    if wrong := sorted(
        item_id for item_id in mechanics.items if state.world.require(item_id).kind != "item"
    ):
        raise ValueError(f"mechanics name entities that are not items: {wrong}")


def armor_of(state: GameState, mechanics: Mechanics, actor: Entity) -> int:
    sheet = mechanics.sheets.get(actor.id)
    worn = sum(mechanics.rules_of(item.id).armor for item in state.world.children(actor.id, "item"))
    natural = sheet.armor if sheet is not None else 0
    return min(natural + worn, MAX_ARMOR)


def slots_used(state: GameState, mechanics: Mechanics, actor: Entity, sheet: Sheet) -> int:
    items = state.world.children(actor.id, "item")
    carried = sum(mechanics.rules_of(item.id).slots for item in items)
    return carried + sheet.fatigue.current


def _over_limit(actor: Entity, used: int) -> str:
    return (
        f"{actor.name} carries {used} slots, over the limit of {MAX_SLOTS}. Drop or leave "
        "something: a bulky item takes two slots, a petty one none, and each Fatigue takes one."
    )


def check_load(draft: GameState, mechanics: Mechanics) -> list[Fact]:
    """Cairn: ten filled slots leave a character at 0 HP, and nobody carries more than ten."""
    facts: list[Fact] = []
    for entity_id, sheet in mechanics.sheets.items():
        actor = draft.world.find(entity_id)
        if actor is None:
            continue
        used = slots_used(draft, mechanics, actor, sheet)
        if used > MAX_SLOTS:
            raise ValueError(_over_limit(actor, used))
        if used == MAX_SLOTS and sheet.hp.current > 0:
            emptied = adjust(actor, "hp", sheet.hp, -sheet.hp.current, "loaded to the last slot")
            facts.extend(emptied)
    return facts


def check_load_limits(state: GameState, mechanics: Mechanics) -> None:
    for entity_id, sheet in mechanics.sheets.items():
        actor = state.world.find(entity_id)
        if actor is None:
            continue
        used = slots_used(state, mechanics, actor, sheet)
        if used > MAX_SLOTS:
            raise ValueError(_over_limit(actor, used))


COLLAPSE: Mapping[Attribute, tuple[Slug, str, str]] = {
    "strength": ("dead", "Dead", "(condition) Dead."),
    "dexterity": (
        "paralysed",
        "Paralysed",
        "(condition) Unable to move or act until the attribute is restored.",
    ),
    "willpower": (
        "delirious",
        "Delirious",
        "(condition) Unable to act sensibly until the attribute is restored.",
    ),
}


def collapsed(entity: Entity, sheet: Sheet) -> list[Fact]:
    """Cairn's floors: 0 STR is death, 0 DEX is paralysis, 0 WIL is delirium."""
    facts: list[Fact] = []
    for key, (trait_id, name, text) in COLLAPSE.items():
        if attribute_of(sheet, key).current != 0 or entity.trait(trait_id) is not None:
            continue
        entity.traits.append(Trait(id=trait_id, name=name, text=text))
        data = {"attribute": key}
        facts.append(entity_fact(entity, "attribute_emptied", f"{entity.name} is {name}", data))
    return facts


def _slot_cost(slots: int) -> str:
    if slots == 0:
        return "petty (no slot)"
    if slots == 2:
        return "bulky (2 slots)"
    return "1 slot"


def _describe_item(rules: ItemRules) -> str:
    parts = (
        f"d{rules.damage} damage" if rules.damage else "",
        f"{rules.armor} armor" if rules.armor else "",
        _slot_cost(rules.slots),
        f"uses {pool(rules.uses)}" if rules.uses is not None else "",
    )
    return ", ".join(part for part in parts if part)


def describe_entity(state: GameState, mechanics: Mechanics, entity: Entity) -> str:
    sheet = mechanics.sheets.get(entity.id)
    if sheet is not None:
        lines = (
            f"background: {sheet.background}" if sheet.background else "",
            render_counters(sheet.counters()),
            f"armor {armor_of(state, mechanics, entity)}, "
            f"slots {slots_used(state, mechanics, entity, sheet)}/{MAX_SLOTS}",
        )
        return "\n".join(line for line in lines if line)
    rules = mechanics.items.get(entity.id)
    return _describe_item(rules) if rules is not None else ""


_RECOVERING_COUNTERS = frozenset({"hp", "strength", "dexterity", "willpower"})


def _recovers(effect: CounterChange) -> bool:
    """What deprivation blocks: anything that would restore HP, an attribute, or a slot."""
    if effect.counter in _RECOVERING_COUNTERS:
        return effect.mode == "adjust" and effect.amount > 0
    if effect.counter == "fatigue":
        return effect.mode == "spend" or (effect.mode == "adjust" and effect.amount < 0)
    return False


def _check_deprivation(entity: Entity, effect: CounterChange) -> None:
    if entity.trait(DEPRIVED) is not None and _recovers(effect):
        raise ValueError(
            f"{entity.name} is deprived and recovers no HP, attributes or slots until they eat "
            "and rest. The `deprived` trait must be lifted first."
        )


def _apply_counter_change(
    draft: GameState, mechanics: Mechanics, effect: CounterChange
) -> list[Fact]:
    entity, seen = reveal_target(draft, effect.entity_id)
    _check_deprivation(entity, effect)
    sheet = mechanics.sheets.get(entity.id)
    pools: Pools | None = sheet if sheet is not None else mechanics.items.get(entity.id)
    moved = move_pool(pools, entity, effect)
    collapse_facts = collapsed(entity, sheet) if sheet is not None else []
    return [*seen, *moved, *collapse_facts]


def apply(draft: GameState, effect: Cairn2eEffect) -> list[Fact]:
    mechanics = draft.mechanics_as(Mechanics)
    if isinstance(effect, CounterChange):
        facts = _apply_counter_change(draft, mechanics, effect)
    else:
        facts = apply_effect(draft, effect)
    # An item picked up or handed over is what fills the slots, and core knows nothing about them.
    facts.extend(check_load(draft, mechanics))
    return facts
