from collections.abc import Mapping, Sequence
from typing import Annotated

from pydantic import Field

from aidm.content.authored import Rules
from aidm.engines.counters import (
    Counter,
    CounterChange,
    adjust,
    pool,
    render_counters,
    spend,
    write_mechanics,
)
from aidm.engines.loader import EntityRenderer
from aidm.state.apply import apply_effect, entity_fact, explained_fact, reveal_target
from aidm.state.base import PLAYER_ID, Entity, EntityId, Kind, Mutable, Slug
from aidm.state.effects import WorldOp
from aidm.state.facts import Fact
from aidm.state.packs import CollectionName, Content, ContentRef, Record, fact_line, is_int_fact
from aidm.state.world import GameState

from .content import PROJECTING, lookup

type Dnd5eEffect = Annotated[WorldOp | CounterChange, Field(discriminator="op")]

ABILITIES: tuple[Slug, ...] = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)
ACTOR_NUMBERS: Mapping[Slug, int] = {**dict.fromkeys(ABILITIES, 10), "armor-class": 10}
ACTOR_COUNTERS: Mapping[Slug, Counter] = {"hp": Counter(current=1, maximum=1)}


def modifier(score: int) -> int:
    return (score - 10) // 2


class Sheet(Mutable):
    numbers: dict[Slug, int] = Field(default_factory=dict)
    counters: dict[Slug, Counter] = Field(default_factory=dict)
    notes: dict[Slug, str] = Field(default_factory=dict)
    refs: tuple[ContentRef, ...] = ()


class Mechanics(Mutable):
    sheets: dict[EntityId, Sheet] = Field(default_factory=dict)


def read(state: GameState) -> Mechanics:
    return Mechanics.model_validate(state.mechanics)


def write(state: GameState, mechanics: Mechanics) -> None:
    write_mechanics(state, mechanics)


def sheet_of(mechanics: Mechanics, entity: Entity) -> Sheet:
    held = mechanics.sheets.get(entity.id)
    if held is None:
        raise ValueError(f"{entity.name} has no 5e sheet")
    return held


def begin(content: Content, state: GameState, rules: Mapping[EntityId, Rules]) -> None:
    sheets = {
        entity.id: build(content, entity.kind, rules.get(entity.id, {}))
        for entity in state.world.entities.values()
    }
    write(state, Mechanics(sheets=sheets))


def commit(content: Content, state: GameState) -> None:
    """An entity that joined the world mid-turn is given a sheet by the commit that admits it;
    a payload missing the player is corruption, not a gap to fill."""
    mechanics = read(state)
    if PLAYER_ID not in mechanics.sheets:
        raise ValueError("the 5e mechanics name no player")
    for entity in state.world.entities.values():
        if entity.id not in mechanics.sheets:
            mechanics.sheets[entity.id] = build(content, entity.kind, {})
    if gone := sorted(set(mechanics.sheets) - state.world.all_ids()):
        raise ValueError(f"mechanics name entities the world does not hold: {gone}")
    for entity_id, sheet in mechanics.sheets.items():
        for ref in sheet.refs:
            if lookup(content, ref) is None:
                raise ValueError(f"{entity_id!r} refs missing content {ref}")
    write(state, mechanics)


def build(content: Content, kind: Kind, rules: Rules) -> Sheet:
    authored = Sheet.model_validate(rules)
    numbers = dict(ACTOR_NUMBERS) if kind == "actor" else {}
    counters = (
        {key: counter.model_copy() for key, counter in ACTOR_COUNTERS.items()}
        if kind == "actor"
        else {}
    )
    for key, value in _backing(authored.refs, content).items():
        if key in authored.numbers or key in authored.counters:
            continue
        declared = counters.get(key)
        if declared is None:
            numbers[key] = value
        else:
            # A record's number is a full pool: the giant rat's `hp: 7` is 7/7.
            counters[key] = declared.model_copy(update={"current": value, "maximum": value})
    authored.numbers = {**numbers, **authored.numbers}
    authored.counters = {**counters, **authored.counters}
    return authored


def _backing(refs: Sequence[ContentRef], content: Content) -> Mapping[Slug, int]:
    backing: dict[Slug, int] = {}
    claimed_by: dict[Slug, ContentRef] = {}
    for ref in refs:
        if ref.collection not in PROJECTING:
            continue
        record = content.require(ref)
        for key, value in record.facts.items():
            if not is_int_fact(value):
                continue
            held = claimed_by.get(key)
            # Two refs agreeing on a value lose nothing; only a disagreement drops one of them.
            if held is not None and backing[key] != value:
                raise ValueError(f"content fact {key!r} differs between {held} and {ref}")
            backing[key] = value
            claimed_by[key] = ref
    return backing


def render(content: Content, state: GameState) -> EntityRenderer:
    mechanics = read(state)
    return lambda entity: describe(content, mechanics, entity)


def describe(content: Content, mechanics: Mechanics, entity: Entity) -> str:
    sheet = mechanics.sheets.get(entity.id)
    if sheet is None:
        return ""
    sections = (
        ("numbers", ", ".join(f"{key} {value}" for key, value in sorted(sheet.numbers.items()))),
        ("counters", render_counters(sheet.counters)),
        ("notes", "; ".join(f"{key}={value}" for key, value in sorted(sheet.notes.items()))),
        ("content", _refs(sheet.refs, content)),
    )
    return "\n".join(
        f"{name}:{body}" if body.startswith("\n") else f"{name}: {body}"
        for name, body in sections
        if body
    )


def _refs(refs: tuple[ContentRef, ...], content: Content) -> str:
    return "".join(f"\n- {_ref_line(ref, content)}" for ref in refs)


def _ref_line(ref: ContentRef, content: Content) -> str:
    record = lookup(content, ref)
    if record is None:
        return str(ref)
    # An int fact of a projecting collection already stands in the sheet's own numbers or counters.
    projected = ref.collection in PROJECTING
    facts_left = (
        (key, value)
        for key, value in sorted(record.facts.items())
        if not (projected and is_int_fact(value))
    )
    rendered = (fact_line(key, value, ladder_full=False) for key, value in facts_left)
    facts = "; ".join((*(line for line in rendered if line is not None), *record.tags))
    return f"{record.name} [{ref}]" + (f" — {facts}" if facts else "")


def apply(draft: GameState, effect: Dnd5eEffect) -> list[Fact]:
    if not isinstance(effect, CounterChange):
        return apply_effect(draft, effect)
    mechanics = read(draft)
    entity, seen = reveal_target(draft, effect.entity_id)
    facts = [*seen, *move_counter(mechanics, entity, effect)]
    write(draft, mechanics)
    return facts


def move_counter(mechanics: Mechanics, entity: Entity, effect: CounterChange) -> list[Fact]:
    counter = counter_of(sheet_of(mechanics, entity), entity, effect.counter)
    if effect.mode == "adjust":
        return adjust(entity, effect.counter, counter, effect.amount, effect.why)
    return spend(entity, effect.counter, counter, effect.amount, effect.why)


def counter_of(sheet: Sheet, entity: Entity, key: str) -> Counter:
    held = sheet.counters.get(key)
    if held is None:
        known = ", ".join(sorted(sheet.counters)) or "(none)"
        raise ValueError(f"{entity.name} has no counter {key!r}. Their counters are: {known}")
    return held


def refill(entity: Entity, sheet: Sheet, label: str, recharges: Sequence[str]) -> list[Fact]:
    keys: list[str] = []
    for key, counter in sorted(sheet.counters.items()):
        maximum = counter.maximum
        if maximum is None or counter.recharge not in recharges or counter.current == maximum:
            continue
        counter.current = maximum
        keys.append(key)
    if not keys:
        return []
    trace = f"{entity.name} took {label}: refilled {', '.join(keys)}"
    return [entity_fact(entity, "recharged", trace, {"label": label, "counters": list(keys)})]


def set_note(entity: Entity, sheet: Sheet, key: Slug, text: str, why: str = "") -> list[Fact]:
    if not text:
        if sheet.notes.pop(key, None) is None:
            return []
        trace = f"{entity.name} note {key} cleared"
    else:
        sheet.notes[key] = text
        trace = f"{entity.name} note {key}: {text}"
    return [explained_fact(entity, "note_set", trace, {"key": key}, why, narrate=False)]


def set_number(entity: Entity, sheet: Sheet, key: Slug, value: int, why: str) -> list[Fact]:
    before = sheet.numbers.get(key)
    sheet.numbers[key] = value
    trace = f"{entity.name} {key}: {before} -> {value}"
    data = {"key": key, "before": before, "after": value}
    return [explained_fact(entity, "number_set", trace, data, why, narrate=False)]


def grant_counter(entity: Entity, sheet: Sheet, key: Slug, counter: Counter, why: str) -> Fact:
    if key in sheet.counters:
        raise ValueError(f"{entity.name} already has {key!r}; adjust it instead")
    sheet.counters[key] = counter
    trace = f"{entity.name} gains {key} at {pool(counter)}"
    data = {"counter": key, "current": counter.current, "maximum": counter.maximum}
    return explained_fact(entity, "counter_granted", trace, data, why, narrate=False)


def drop_counter(entity: Entity, sheet: Sheet, key: Slug, why: str) -> Fact:
    counter = sheet.counters.pop(key, None)
    if counter is None:
        raise ValueError(f"{entity.name} has no counter {key!r} to drop")
    trace = f"{entity.name} loses {key}"
    data = {"counter": key, "current": counter.current, "maximum": counter.maximum}
    return explained_fact(entity, "counter_dropped", trace, data, why, narrate=False)


def add_ref(entity: Entity, sheet: Sheet, ref: ContentRef, why: str) -> Fact:
    if ref in sheet.refs:
        raise ValueError(f"{entity.name} already holds content {ref}")
    sheet.refs = (*sheet.refs, ref)
    trace = f"{entity.name} gains content {ref}"
    return explained_fact(entity, "ref_added", trace, {"ref": str(ref)}, why, narrate=False)


def first_ref_record(
    sheet: Sheet, content: Content, collection: CollectionName, require_fact: Slug | None = None
) -> Record | None:
    for ref in sheet.refs:
        if ref.collection != collection:
            continue
        held = lookup(content, ref)
        if held is None or (require_fact is not None and require_fact not in held.facts):
            continue
        return held
    return None
