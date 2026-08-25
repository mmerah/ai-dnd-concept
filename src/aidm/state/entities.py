import re
from collections import Counter as Tally
from collections.abc import Iterable, Mapping
from typing import Annotated, Literal, NewType, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.config import SLUG_MAX, SLUG_PATTERN, Slug


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

PLAYER_ID = EntityId("player")

# Engine option ids may contain repeated hyphens, unlike `Slug`.
ContentSlug = Annotated[str, Field(pattern=r"^[a-z0-9-]+$", max_length=64)]


def content_id(value: str) -> Slug:
    """Narrow a routed id before it names a directory, so `Slug` downstream is a fact."""
    if re.fullmatch(SLUG_PATTERN, value) is None:
        raise ValueError(f"invalid content id {value!r}")
    return value


def slug(name: str, taken: Iterable[EntityId]) -> EntityId:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "entity"
    return EntityId(_unused(base, taken, "_"))


def text_slug(text: str, taken: Iterable[str]) -> Slug:
    words = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return _unused(_capped(words, SLUG_MAX), taken, "-", SLUG_MAX)


def _unused(base: str, taken: Iterable[str], join: str, limit: int | None = None) -> str:
    used, candidate, number = set(taken), base, 2
    while candidate in used:
        suffix = f"{join}{number}"
        room = base if limit is None else _capped(base, limit - len(suffix))
        candidate, number = f"{room}{suffix}", number + 1
    return candidate


def _capped(words: str, limit: int) -> str:
    return words[:limit].rstrip("-") or "entry"


def duplicates(ids: Iterable[str]) -> list[str]:
    return sorted(name for name, count in Tally(ids).items() if count > 1)


def require_unique(what: str, ids: Iterable[str]) -> None:
    if found := duplicates(ids):
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


class EntityDetail(Frozen):
    description: str
    when_reached: str


class Trait(Frozen):
    """A lasting quality."""

    id: Slug
    name: str
    text: str = ""


class Exit(Mutable):
    """A one-way exit from a location."""

    to: EntityId
    known: bool = False
    locked: bool = False


class Entity(Mutable):
    id: EntityId
    kind: Kind
    name: str
    brief: str
    detail: EntityDetail | None = None
    known: bool = False
    # Which kinds may hold which is one rule, in `world.check_placement`.
    parent_id: EntityId | None = None
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


_HOLDERS: Mapping[Kind, tuple[Kind, ...]] = {
    "actor": ("location",),
    "item": ("actor", "location"),
    "location": (),
}


def check_placement(entity: Entity, holder: Entity | None) -> None:
    allowed = _HOLDERS[entity.kind]
    if not allowed:
        if entity.parent_id is not None:
            raise ValueError(f"{entity.kind} {entity.id!r} cannot be inside anything")
        return
    if holder is None:
        raise ValueError(f"{entity.kind} {entity.id!r} is not in a valid {' or '.join(allowed)}")
    if holder.kind not in allowed:
        raise ValueError(f"{entity.kind} {entity.id!r} is in a {holder.kind}, which cannot hold it")
