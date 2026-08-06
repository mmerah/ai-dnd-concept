from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .base import Entity, Frozen, Kind, Mutable, Slug
from .facts import CORE, Fact
from .packs import EMPTY_FROZEN_MAP, ContentRef, FrozenMap, LenientRecord, Value

type ResolveRef = Callable[[ContentRef], LenientRecord | None]

_NO_NUMBERS: Mapping[Slug, int] = MappingProxyType({})


class Counter(Mutable):
    current: int
    maximum: int | None = None  # None is unbounded: wealth, experience
    minimum: int = 0  # below zero for a pool like Ironsworn's momentum
    recharge: str | None = None  # a label the engine spec maps to what refills it

    @model_validator(mode="after")
    def _within_bounds(self) -> Self:
        if self.maximum is not None and self.maximum < self.minimum:
            raise ValueError(f"maximum {self.maximum} is below minimum {self.minimum}")
        if self.current < self.minimum:
            raise ValueError(f"{self.current} is below minimum {self.minimum}")
        if self.maximum is not None and self.current > self.maximum:
            raise ValueError(f"{self.current} is above maximum {self.maximum}")
        if self.maximum is None and self.recharge is not None:
            raise ValueError("an unbounded counter has no maximum to recharge to")
        return self

    def clamped(self, value: int) -> int:
        bounded = max(value, self.minimum)
        return bounded if self.maximum is None else min(bounded, self.maximum)


class CounterTemplate(Value):
    current: int = 0
    maximum: int | None = None
    minimum: int = 0
    recharge: str | None = None

    def runtime(self) -> Counter:
        return Counter.model_validate(self.model_dump())

    @model_validator(mode="after")
    def _instantiable(self) -> Self:
        """A bad template in `spec.json` fails at load, not on the turn that first grows one."""
        _ = self.runtime()
        return self


class SheetTag(Frozen):
    id: Slug
    name: str
    text: str = ""


class SheetTemplate(Value):
    """The canonical keys of one kind: every sheet the engine builds starts with these."""

    numbers: FrozenMap[Slug, int] = EMPTY_FROZEN_MAP
    counters: FrozenMap[Slug, CounterTemplate] = EMPTY_FROZEN_MAP


class Sheet(Mutable):
    kind: Kind
    numbers: dict[Slug, int] = Field(default_factory=dict)
    counters: dict[Slug, Counter] = Field(default_factory=dict)
    tags: list[SheetTag] = Field(default_factory=list)
    notes: dict[Slug, str] = Field(default_factory=dict)
    refs: tuple[ContentRef, ...] = ()

    @model_validator(mode="after")
    def _keys_are_unambiguous(self) -> Self:
        if clashing := sorted(set(self.numbers) & set(self.counters)):
            raise ValueError(f"keys are both a number and a counter: {clashing}")
        ids = [tag.id for tag in self.tags]
        if repeated := sorted({tag_id for tag_id in ids if ids.count(tag_id) > 1}):
            raise ValueError(f"duplicate tag ids: {repeated}")
        return self

    def tag(self, tag_id: str) -> SheetTag | None:
        return next((tag for tag in self.tags if tag.id == tag_id), None)


class SheetDefinition(Value):
    numbers: FrozenMap[Slug, int] = EMPTY_FROZEN_MAP
    counters: FrozenMap[Slug, CounterTemplate] = EMPTY_FROZEN_MAP
    tags: tuple[SheetTag, ...] = ()
    notes: FrozenMap[Slug, str] = EMPTY_FROZEN_MAP
    refs: tuple[ContentRef, ...] = ()

    def runtime(
        self,
        kind: Kind,
        template: SheetTemplate,
        record_numbers: Mapping[Slug, int] = _NO_NUMBERS,
    ) -> Sheet:
        """Template, then backing records, then the author: the most specific key wins."""
        numbers = dict(template.numbers)
        counters = dict(template.counters)
        for key, value in record_numbers.items():
            if key in self.numbers or key in self.counters:
                continue
            if (declared := counters.get(key)) is None:
                numbers[key] = value
            else:
                # A record's number is a full pool: the giant rat's `hp: 7` is 7/7.
                counters[key] = declared.model_copy(update={"current": value, "maximum": value})
        return Sheet(
            kind=kind,
            numbers={**numbers, **self.numbers},
            counters={key: c.runtime() for key, c in {**counters, **self.counters}.items()},
            tags=list(self.tags),
            notes=dict(self.notes),
            refs=self.refs,
        )


class DeltaItem(Frozen):
    why: str = Field(description="One short sentence saying what earns this change.")


class SetNumber(DeltaItem):
    op: Literal["set-number"] = "set-number"
    key: Slug = Field(description="The number's key, as the sheet spells it.")
    value: int = Field(description="What the number becomes.")


class GrantCounter(DeltaItem):
    op: Literal["grant-counter"] = "grant-counter"
    key: Slug = Field(description="Key for a pool the sheet does not have yet.")
    current: int
    maximum: int | None = Field(default=None, description="Omit for an unbounded pool.")
    minimum: int = 0
    recharge: str | None = Field(default=None, description="A recharge label of this engine.")


class ChangeCounter(DeltaItem):
    op: Literal["change-counter"] = "change-counter"
    key: Slug = Field(description="Key of a pool the sheet already has.")
    delta: int = Field(default=0, description="How much the current value moves.")
    maximum: int | None = Field(default=None, description="A new maximum; omit to keep it.")


class AddTag(DeltaItem):
    op: Literal["add-tag"] = "add-tag"
    tag: SheetTag


class RemoveTag(DeltaItem):
    op: Literal["remove-tag"] = "remove-tag"
    tag_id: Slug = Field(description="Exact id of a tag the sheet carries.")


class AddRef(DeltaItem):
    op: Literal["add-ref"] = "add-ref"
    ref: ContentRef = Field(description="One of the picks the offer allows.")


class SetNote(DeltaItem):
    op: Literal["set-note"] = "set-note"
    key: Slug
    text: str = Field(description="The note; empty clears the key.")


type DeltaChange = Annotated[
    SetNumber | GrantCounter | ChangeCounter | AddTag | RemoveTag | AddRef | SetNote,
    Field(discriminator="op"),
]


class AdvancementOffer(Frozen):
    """One pending advancement, already resolved out of content: the panel and the advisor read
    this and nothing else, so neither needs to reach into a pack."""

    prompt: str
    text: str = ""
    options: tuple[ContentRef, ...] = ()
    choose: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _choice_is_whole(self) -> Self:
        if self.choose > len(self.options):
            raise ValueError(f"cannot choose {self.choose} of {len(self.options)} options")
        return self


class SheetDelta(Frozen):
    """What advancement writes onto the player's sheet, each change carrying its reason."""

    changes: tuple[DeltaChange, ...] = ()


def apply_delta(sheet: Sheet, delta: SheetDelta) -> tuple[Fact, ...]:
    """Mutates a draft's sheet; the transaction's commit revalidates the whole copy."""
    return tuple(_applied(sheet, change) for change in delta.changes)


def _applied(sheet: Sheet, change: DeltaChange) -> Fact:
    match change:
        case SetNumber(key=key, value=value):
            # Advancement is where a sheet grows, so an unheld key is written, not refused.
            before = sheet.numbers.get(key)
            sheet.numbers[key] = value
            return _delta_fact(change, f"{key} {before} -> {value}")
        case GrantCounter(key=key):
            if key in sheet.counters:
                raise ValueError(f"counter {key!r} exists; change it instead of granting it")
            counter = Counter(
                current=change.current,
                maximum=change.maximum,
                minimum=change.minimum,
                recharge=change.recharge,
            )
            sheet.counters[key] = counter
            return _delta_fact(change, f"{key} granted at {pool(counter)}")
        case ChangeCounter(key=key, delta=amount, maximum=maximum):
            counter = _held_counter(sheet, key)
            if maximum is not None:
                counter.maximum = maximum
            counter.current = counter.clamped(counter.current + amount)
            return _delta_fact(change, f"{key} -> {pool(counter)}")
        case AddTag(tag=tag):
            if sheet.tag(tag.id) is not None:
                raise ValueError(f"tag {tag.id!r} is already on the sheet")
            sheet.tags.append(tag)
            return _delta_fact(change, f"gained {tag.name}[id={tag.id}]")
        case RemoveTag(tag_id=tag_id):
            held = sheet.tag(tag_id)
            if held is None:
                raise ValueError(f"no tag {tag_id!r} on the sheet")
            sheet.tags.remove(held)
            return _delta_fact(change, f"lost {held.name}[id={tag_id}]")
        case AddRef(ref=ref):
            if ref in sheet.refs:
                raise ValueError(f"content {ref} is already on the sheet")
            sheet.refs = (*sheet.refs, ref)
            return _delta_fact(change, f"gained content {ref}")
        case SetNote(key=key, text=text):
            if text:
                sheet.notes[key] = text
            elif sheet.notes.pop(key, None) is None:
                raise ValueError(f"no note {key!r} to clear")
            return _delta_fact(change, f"note {key}: {text or '(cleared)'}")


def _held_counter(sheet: Sheet, key: str) -> Counter:
    counter = sheet.counters.get(key)
    if counter is None:
        known = ", ".join(sorted(sheet.counters)) or "(none)"
        raise ValueError(f"no counter {key!r} on the sheet. Its counters are: {known}")
    return counter


def _delta_fact(change: DeltaItem, summary: str) -> Fact:
    return Fact(source=CORE, kind="advanced", trace=f"{summary} ({change.why})")


def render_sheet(_entity: Entity, sheet: Sheet, resolve: ResolveRef | None = None) -> str:
    """With a resolver, each ref renders as one line of its record's notes and tags — the key
    facts, not the text, which still enters a turn only through `read_content`."""
    counters = ", ".join(_counter(key, sheet.counters[key]) for key in sorted(sheet.counters))
    sections = (
        ("numbers", ", ".join(f"{key} {value}" for key, value in sorted(sheet.numbers.items()))),
        ("counters", counters),
        ("tags", ", ".join(_tag(tag) for tag in sheet.tags)),
        ("notes", "; ".join(f"{key}={value}" for key, value in sorted(sheet.notes.items()))),
        ("content", _refs(sheet.refs, resolve)),
    )
    return "\n".join(
        f"{name}:{body}" if body.startswith("\n") else f"{name}: {body}"
        for name, body in sections
        if body
    )


def _refs(refs: tuple[ContentRef, ...], resolve: ResolveRef | None) -> str:
    if resolve is None:
        return ", ".join(str(ref) for ref in refs)
    return "".join(f"\n- {_ref_line(ref, resolve(ref))}" for ref in refs)


def _ref_line(ref: ContentRef, record: LenientRecord | None) -> str:
    if record is None:
        return str(ref)
    facts = "; ".join(
        (*(f"{key}={value}" for key, value in sorted(record.notes.items())), *record.tags)
    )
    return f"{record.name} [{ref}]" + (f" — {facts}" if facts else "")


def pool(counter: Counter) -> str:
    if counter.maximum is None:
        return str(counter.current)
    return f"{counter.current}/{counter.maximum}"


def _counter(key: str, counter: Counter) -> str:
    recharge = f" ({counter.recharge})" if counter.recharge is not None else ""
    return f"{key} {pool(counter)}{recharge}"


def _tag(tag: SheetTag) -> str:
    return f"{tag.name}[id={tag.id}]" + (f" — {tag.text}" if tag.text else "")
