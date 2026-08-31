import re
from collections import Counter as Tally
from collections.abc import Iterable
from typing import Annotated, NewType, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SLUG_PATTERN = r"[a-z0-9]+(?:-[a-z0-9]+)*"
SLUG_MAX = 64
Slug = Annotated[str, Field(pattern=rf"^{SLUG_PATTERN}$", max_length=SLUG_MAX)]

EngineId = NewType("EngineId", str)
EntityId = NewType("EntityId", str)
# The grammar rides the field annotation: a `NewType` over an `Annotated` alias is not a type.
CheckedEntityId = Annotated[EntityId, Field(pattern=rf"^{SLUG_PATTERN}$", max_length=SLUG_MAX)]

PLAYER_ID = EntityId("player")

DEAD: Slug = "dead"


class Frozen(BaseModel):
    """A value nothing owns: a fact, a direction, or an authored record."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Mutable(BaseModel):
    """State a resolution mutates in place; commit revalidates the whole draft once."""

    model_config = ConfigDict(extra="forbid")


class Header(BaseModel):
    """Routes a document before its engine is known; the rest of the document is ignored."""

    model_config = ConfigDict(extra="ignore", frozen=True)


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


def content_id(value: str) -> Slug:
    """Narrow a routed id before it names a directory, so `Slug` downstream is a fact."""
    if re.fullmatch(SLUG_PATTERN, value) is None or len(value) > SLUG_MAX:
        raise ValueError(f"invalid content id {value!r}")
    return value


def slug(text: str, taken: Iterable[str]) -> Slug:
    words = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return _unused(_capped(words, SLUG_MAX), taken)


def require_unique(what: str, ids: Iterable[str]) -> None:
    if found := sorted(name for name, count in Tally(ids).items() if count > 1):
        raise ValueError(f"duplicate {what}: {found}")


def pool(counter: Counter) -> str:
    if counter.maximum is None:
        return str(counter.current)
    return f"{counter.current}/{counter.maximum}"


def _unused(base: str, taken: Iterable[str]) -> str:
    used, candidate, number = set(taken), base, 2
    while candidate in used:
        suffix = f"-{number}"
        candidate, number = f"{_capped(base, SLUG_MAX - len(suffix))}{suffix}", number + 1
    return candidate


def _capped(words: str, limit: int) -> str:
    return words[:limit].rstrip("-") or "entry"
