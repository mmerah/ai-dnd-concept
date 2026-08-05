from collections.abc import Mapping
from types import MappingProxyType
from typing import Self

from pydantic import Field, model_validator

from .base import Entity, Frozen, Kind, Mutable, Slug
from .packs import EMPTY_FROZEN_MAP, ContentRef, FrozenMap, Value
from .world import EngineRules

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


class Sheet(EngineRules):
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


def render_sheet(_entity: Entity, sheet: Sheet) -> str:
    """Refs render by name only: their text enters a turn through `read_content`, so a render
    stays a few lines however large the pack is."""
    counters = ", ".join(_counter(key, sheet.counters[key]) for key in sorted(sheet.counters))
    sections = (
        ("numbers", ", ".join(f"{key} {value}" for key, value in sorted(sheet.numbers.items()))),
        ("counters", counters),
        ("tags", ", ".join(_tag(tag) for tag in sheet.tags)),
        ("notes", "; ".join(f"{key}={value}" for key, value in sorted(sheet.notes.items()))),
        ("content", ", ".join(str(ref) for ref in sheet.refs)),
    )
    return "\n".join(f"{name}: {body}" for name, body in sections if body)


def pool(counter: Counter) -> str:
    if counter.maximum is None:
        return str(counter.current)
    return f"{counter.current}/{counter.maximum}"


def _counter(key: str, counter: Counter) -> str:
    recharge = f" ({counter.recharge})" if counter.recharge is not None else ""
    return f"{key} {pool(counter)}{recharge}"


def _tag(tag: SheetTag) -> str:
    return f"{tag.name}[id={tag.id}]" + (f" — {tag.text}" if tag.text else "")
