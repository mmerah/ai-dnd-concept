from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random
from typing import Annotated, Literal

from pydantic import Field, JsonValue, ValidationError
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.toolsets import FunctionToolset

from .base import Entity, EntityId, Slug
from .dice import ConstantTerm, DiceExpr, DiceTerm, terms
from .facts import CORE, Fact
from .packs import Content, ContentMiss, ContentRef, LenientRecord
from .sheet import Counter, Sheet, SheetTag, pool
from .tools import TurnContext, require, require_actor_here

RollMode = Literal["sum", "keep-highest", "keep-lowest"]

TargetArg = Annotated[
    EntityId,
    Field(description="Exact id of the entity affected; an actor must be here with the player."),
]
CounterArg = Annotated[
    Slug, Field(description="Exact key of one of that entity's counters, as its sheet spells it.")
]


@dataclass(frozen=True, slots=True)
class Rolled:
    total: int
    dice: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Mechanics:
    content: Content
    refills: Mapping[str, Sequence[str]]

    def toolset(self) -> FunctionToolset[TurnContext[Sheet]]:
        return FunctionToolset[TurnContext[Sheet]](
            [
                self.roll,
                self.adjust,
                self.spend,
                self.recharge,
                self.add_tag,
                self.remove_tag,
                self.set_note,
                self.set_number,
                self.read_content,
            ]
        )

    def roll(
        self,
        ctx: RunContext[TurnContext[Sheet]],
        dice: Annotated[
            DiceExpr,
            Field(description="The whole expression, bonuses included: '1d20 + 5', '2d6 + 3'."),
        ],
        reason: Annotated[
            str, Field(min_length=1, description="What is being rolled, in a few words.")
        ],
        vs: Annotated[
            int | None,
            Field(description="Number the total must reach — a DC or an armour class; else omit."),
        ] = None,
        mode: Annotated[
            RollMode,
            Field(description="`keep-highest` for advantage, `keep-lowest` for disadvantage."),
        ] = "sum",
    ) -> str:
        """Roll dice; the result is the engine's, never yours to choose.

        Work out the bonuses yourself from the sheet and the rules text, and put them in the
        expression. Give `vs` whenever the roll can fail, and read the SUCCESS or FAILURE back
        before you apply anything that follows from it.
        """
        deps = ctx.deps
        first = _evaluate(dice, deps.rng)
        kept, dropped = first, None
        if mode != "sum":
            pair = sorted((first, _evaluate(dice, deps.rng)), key=lambda outcome: outcome.total)
            kept, dropped = (pair[-1], pair[0]) if mode == "keep-highest" else (pair[0], pair[-1])
        return deps.record([_rolled(dice, reason, vs, mode, kept, dropped)])

    def adjust(
        self,
        ctx: RunContext[TurnContext[Sheet]],
        entity_id: TargetArg,
        counter: CounterArg,
        delta: Annotated[int, Field(description="How much the pool moves: negative to reduce.")],
        reason: Annotated[
            str, Field(min_length=1, description="What changed the pool, in a few words.")
        ],
    ) -> str:
        """Move one of an entity's counters up or down.

        Use for damage, healing, stress, and any pool that is spent or restored by an amount. The
        change is clamped to the counter's own bounds, and the fact reports what actually landed.
        """
        deps = ctx.deps
        entity, sheet, seen = self._target(deps, entity_id)
        held = _counter_of(sheet, entity, counter)
        before = held.current
        held.current = held.clamped(before + delta)
        landed = held.current - before
        if landed == 0:
            return deps.record(seen)
        return deps.record([*seen, _changed(entity, counter, held, landed, reason)])

    def spend(
        self,
        ctx: RunContext[TurnContext[Sheet]],
        entity_id: TargetArg,
        counter: CounterArg,
        amount: Annotated[int, Field(ge=1, description="How much of the pool is spent.")],
    ) -> str:
        """Spend from a counter, which fails outright when the pool cannot cover it.

        Use for a resource that must be paid before its effect happens — a spell slot, a feature's
        uses. Spend it first, and drop the effect if this refuses.
        """
        deps = ctx.deps
        entity, sheet, seen = self._target(deps, entity_id)
        held = _counter_of(sheet, entity, counter)
        if held.current - amount < held.minimum:
            raise ModelRetry(
                f"{entity.name} holds {held.current} {counter} and cannot go below "
                f"{held.minimum}, so {amount} cannot be spent."
            )
        held.current -= amount
        return deps.record([*seen, _changed(entity, counter, held, -amount, f"spent {counter}")])

    def recharge(
        self,
        ctx: RunContext[TurnContext[Sheet]],
        entity_id: TargetArg,
        label: Annotated[
            str, Field(min_length=1, description="The rest or interval the fiction completed.")
        ],
    ) -> str:
        """Refill every counter this rest or interval restores.

        Use only once the fiction establishes that the entity completed it. It refills pools to
        their maximum and does nothing else — it invents no healing the rules do not give.
        """
        deps = ctx.deps
        refilled = self.refills.get(label)
        if refilled is None:
            known = ", ".join(sorted(self.refills)) or "(nothing)"
            raise ModelRetry(f"unknown recharge label {label!r}. This engine recharges on: {known}")
        entity, sheet, seen = self._target(deps, entity_id)
        keys: list[str] = []
        for key, held in sorted(sheet.counters.items()):
            maximum = held.maximum
            if maximum is None or held.recharge not in refilled or held.current == maximum:
                continue
            held.current = maximum
            keys.append(key)
        if not keys:
            return deps.record(seen)
        trace = f"{entity.name} took {label}: refilled {', '.join(keys)}"
        data: Mapping[str, JsonValue] = {"label": label, "counters": list(keys)}
        return deps.record([*seen, _fact(entity, "recharged", trace, data)])

    def add_tag(
        self,
        ctx: RunContext[TurnContext[Sheet]],
        entity_id: TargetArg,
        tag_id: Annotated[Slug, Field(description="Stable slug for the tag, such as `poisoned`.")],
        name: Annotated[str, Field(min_length=1, description="Short name shown on the sheet.")],
        text: Annotated[
            str, Field(description="The constraint or benefit it puts on the entity, in prose.")
        ] = "",
    ) -> str:
        """Put a lasting condition, edge, or burden on an entity.

        Use when something takes hold beyond this moment; whether it takes hold is not yours to
        decide when it could be resisted, so roll for that first.
        """
        deps = ctx.deps
        entity, sheet, seen = self._target(deps, entity_id)
        if sheet.tag(tag_id) is not None:
            raise ModelRetry(f"{entity.name} already carries the tag {tag_id!r}")
        sheet.tags.append(SheetTag(id=tag_id, name=name, text=text))
        trace = f"{entity.name} is {name}"
        return deps.record([*seen, _fact(entity, "tag_added", trace, {"tag_id": tag_id})])

    def remove_tag(
        self,
        ctx: RunContext[TurnContext[Sheet]],
        entity_id: TargetArg,
        tag_id: Annotated[Slug, Field(description="Exact id of a tag the entity carries.")],
    ) -> str:
        """Lift a tag an entity carries, when the fiction ends it."""
        deps = ctx.deps
        entity, sheet, seen = self._target(deps, entity_id)
        tag = sheet.tag(tag_id)
        if tag is None:
            held = ", ".join(sorted(t.id for t in sheet.tags)) or "(none)"
            raise ModelRetry(f"{entity.name} carries no tag {tag_id!r}. Their tags are: {held}")
        sheet.tags.remove(tag)
        trace = f"{entity.name} is no longer {tag.name}"
        return deps.record([*seen, _fact(entity, "tag_removed", trace, {"tag_id": tag_id})])

    def set_note(
        self,
        ctx: RunContext[TurnContext[Sheet]],
        entity_id: TargetArg,
        key: Annotated[Slug, Field(description="What the note is about, such as `concentration`.")],
        text: Annotated[str, Field(description="The note; empty clears whatever was noted.")],
    ) -> str:
        """Write freeform state onto an entity's sheet.

        Use for bookkeeping the fiction needs remembered and no counter or tag holds, such as what
        a caster is concentrating on. Writing a key again replaces what it held.
        """
        deps = ctx.deps
        entity, sheet, seen = self._target(deps, entity_id)
        if not text:
            if sheet.notes.pop(key, None) is None:
                return deps.record(seen)
            trace = f"{entity.name} note {key} cleared"
        else:
            sheet.notes[key] = text
            trace = f"{entity.name} note {key}: {text}"
        return deps.record([*seen, _fact(entity, "note_set", trace, {"key": key}, narrate=False)])

    def set_number(
        self,
        ctx: RunContext[TurnContext[Sheet]],
        entity_id: TargetArg,
        key: Annotated[Slug, Field(description="Exact key of a number already on that sheet.")],
        value: Annotated[int, Field(description="What the number becomes.")],
    ) -> str:
        """Set a number the fiction has lastingly changed.

        Use only for a standing change to what an entity is — armour worn, a permanent blessing.
        Never for the outcome of this turn: pools that go up and down are counters.
        """
        deps = ctx.deps
        entity, sheet, seen = self._target(deps, entity_id)
        if key not in sheet.numbers:
            held = ", ".join(sorted(sheet.numbers)) or "(none)"
            raise ModelRetry(f"{entity.name} has no number {key!r}. Their numbers are: {held}")
        before = sheet.numbers[key]
        sheet.numbers[key] = value
        trace = f"{entity.name} {key}: {before} -> {value}"
        data = {"key": key, "before": before, "after": value}
        return deps.record([*seen, _fact(entity, "number_set", trace, data, narrate=False)])

    def read_content(
        self,
        ref: Annotated[
            str, Field(description="A content ref written `pack/collection/index`, as shown.")
        ],
    ) -> str:
        """Read the rules text of one content record.

        Use before applying a spell, feature, or monster action whose wording you cannot quote. It
        reads canon and changes nothing.
        """
        found = self.content.get(_reference(ref), LenientRecord)
        if isinstance(found, ContentMiss):
            raise ModelRetry(found.summary)
        return _rendered(found, ref)

    @staticmethod
    def _target(deps: TurnContext[Sheet], entity_id: EntityId) -> tuple[Entity, Sheet, list[Fact]]:
        """A place or a thing is not revealed by being acted on, so no unlearned name leaks."""
        draft = deps.draft
        entity = require(draft, entity_id)
        seen = draft.reveal(require_actor_here(draft, entity_id)) if entity.kind == "actor" else []
        return entity, draft.world.record(entity_id).rules, seen


def _evaluate(expression: str, rng: Random) -> Rolled:
    total = 0
    dice: list[int] = []
    for term in terms(expression):
        match term:
            case DiceTerm(sign=sign, count=count, faces=faces):
                rolled = [rng.randint(1, faces) for _ in range(count)]
                dice.extend(rolled)
                total += sign * sum(rolled)
            case ConstantTerm(sign=sign, value=value):
                total += sign * value
    return Rolled(total=total, dice=tuple(dice))


def _rolled(
    dice: str, reason: str, vs: int | None, mode: RollMode, kept: Rolled, dropped: Rolled | None
) -> Fact:
    success = None if vs is None else kept.total >= vs
    verdict = "" if success is None else f" vs {vs}: {'SUCCESS' if success else 'FAILURE'}"
    against = "" if dropped is None else f" ({mode}, dropped {dropped.total})"
    faces = ", ".join(str(die) for die in kept.dice)
    return Fact(
        source=CORE,
        kind="dice_rolled",
        trace=f"{reason}: {dice} [{faces}] -> {kept.total}{against}{verdict}",
        narrator=None if success is None else f"{reason}: {'success' if success else 'failure'}",
        data={
            "dice": dice,
            "mode": mode,
            "rolled": list(kept.dice),
            "total": kept.total,
            "vs": vs,
            "success": success,
            "reason": reason,
        },
    )


def _counter_of(sheet: Sheet, entity: Entity, key: str) -> Counter:
    held = sheet.counters.get(key)
    if held is None:
        known = ", ".join(sorted(sheet.counters)) or "(none)"
        raise ModelRetry(f"{entity.name} has no counter {key!r}. Their counters are: {known}")
    return held


def _fact(
    entity: Entity,
    kind: str,
    trace: str,
    data: Mapping[str, JsonValue],
    *,
    narrate: bool = True,
) -> Fact:
    """An entity the player has not learned of narrates nothing, so no unknown name leaks."""
    return Fact(
        source=CORE,
        kind=kind,
        trace=trace,
        narrator=trace if narrate and entity.known else None,
        data={"entity_id": entity.id, **data},
    )


def _changed(entity: Entity, key: str, counter: Counter, delta: int, reason: str) -> Fact:
    data = {"counter": key, "delta": delta, "current": counter.current, "maximum": counter.maximum}
    trace = f"{reason}: {entity.name} {key} {delta:+d} -> {pool(counter)}"
    return _fact(entity, "counter_changed", trace, data)


def _reference(ref: str) -> ContentRef:
    parts = ref.split("/")
    if len(parts) != 3:
        raise ModelRetry(f"malformed ref {ref!r}: write it as `pack/collection/index`")
    try:
        return ContentRef(pack=parts[0], collection=parts[1], index=parts[2])
    except ValidationError as invalid:
        raise ModelRetry(f"malformed ref {ref!r}: {invalid.errors()[0]['msg']}") from invalid


def _rendered(record: LenientRecord, ref: str) -> str:
    numbers = ", ".join(f"{key} {value}" for key, value in sorted(record.numbers.items()))
    notes = "; ".join(f"{key}={value}" for key, value in sorted(record.notes.items()))
    options = ", ".join(str(option) for option in record.options)
    lines = [
        f"{record.name} [{ref}]",
        *([f"numbers: {numbers}"] if numbers else []),
        *([f"notes: {notes}"] if notes else []),
        *([f"tags: {', '.join(record.tags)}"] if record.tags else []),
        *([f"choose {record.choose} of: {options}"] if options else []),
        *([record.text] if record.text else []),
    ]
    return "\n".join(lines)
