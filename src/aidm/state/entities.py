import re
from collections import Counter as Tally
from collections.abc import Iterable
from typing import Annotated, Literal, NewType, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SLUG_PATTERN = r"[a-z0-9]+(?:-[a-z0-9]+)*"
SLUG_MAX = 64
Slug = Annotated[str, Field(pattern=rf"^{SLUG_PATTERN}$", max_length=SLUG_MAX)]


class Frozen(BaseModel):
    """A value nothing owns: a fact, a direction, or an authored record."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Mutable(BaseModel):
    """State a resolution mutates in place; commit revalidates the whole draft once."""

    model_config = ConfigDict(extra="forbid")


Kind = Literal["actor", "location", "item"]


def kind_word(kind: Kind) -> str:
    """Prompts and traces say 'npc', because 'actor' reads as the player too."""
    return "npc" if kind == "actor" else kind


EngineId = NewType("EngineId", str)
EntityId = NewType("EntityId", str)
# The grammar rides the field annotation: a `NewType` over an `Annotated` alias is not a type.
CheckedEntityId = Annotated[EntityId, Field(pattern=rf"^{SLUG_PATTERN}$", max_length=SLUG_MAX)]

PLAYER_ID = EntityId("player")


def content_id(value: str) -> Slug:
    """Narrow a routed id before it names a directory, so `Slug` downstream is a fact."""
    if re.fullmatch(SLUG_PATTERN, value) is None or len(value) > SLUG_MAX:
        raise ValueError(f"invalid content id {value!r}")
    return value


def slug(text: str, taken: Iterable[str]) -> Slug:
    words = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return _unused(_capped(words, SLUG_MAX), taken)


def _unused(base: str, taken: Iterable[str]) -> str:
    used, candidate, number = set(taken), base, 2
    while candidate in used:
        suffix = f"-{number}"
        candidate, number = f"{_capped(base, SLUG_MAX - len(suffix))}{suffix}", number + 1
    return candidate


def _capped(words: str, limit: int) -> str:
    return words[:limit].rstrip("-") or "entry"


def require_unique(what: str, ids: Iterable[str]) -> None:
    if found := sorted(name for name, count in Tally(ids).items() if count > 1):
        raise ValueError(f"duplicate {what}: {found}")


class Counter(Mutable):
    current: int
    maximum: int | None = None  # None is unbounded: wealth, experience

    @model_validator(mode="after")
    def _within_bounds(self) -> Self:
        if self.current < 0:
            raise ValueError(f"{self.current} is below zero")
        if self.maximum is not None and self.current > self.maximum:
            raise ValueError(f"{self.current} is above maximum {self.maximum}")
        return self

    def clamped(self, value: int) -> int:
        bounded = max(value, 0)
        return bounded if self.maximum is None else min(bounded, self.maximum)


class Trait(Frozen):
    """A lasting quality."""

    id: Slug
    name: str
    text: str = ""


DEAD: Slug = "dead"


class Exit(Mutable):
    """A one-way exit from a location."""

    to: CheckedEntityId
    known: bool = False
    locked: bool = False


class Entity(Mutable):
    id: CheckedEntityId
    kind: Kind
    name: str
    brief: str
    description: str = ""
    when_reached: str = ""
    known: bool = False
    # Which kinds may hold which is one rule, in `world.topology.validate_rooms`.
    parent_id: CheckedEntityId | None = None
    traits: list[Trait] = Field(default_factory=list)
    exits: list[Exit] = Field(default_factory=list)

    def trait(self, trait_id: str) -> Trait | None:
        return next((held for held in self.traits if held.id == trait_id), None)

    def exit_to(self, to_id: EntityId) -> Exit | None:
        return next((way for way in self.exits if way.to == to_id), None)

    @model_validator(mode="after")
    def _traits_are_unambiguous(self) -> Self:
        require_unique(f"trait ids on {self.id!r}", (held.id for held in self.traits))
        return self

    @model_validator(mode="after")
    def _exits_are_unambiguous(self) -> Self:
        require_unique(f"exits of {self.id!r}", (way.to for way in self.exits))
        if any(way.to == self.id for way in self.exits):
            raise ValueError(f"location {self.id!r} has an exit to itself")
        return self
