"""Primitives shared by `domain/` and `content/`. They live here because `content/` must not import
`domain/`, and neither should own what the other also needs."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal, cast, get_args

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    WrapSerializer,
)

# Spelled in full because that is how they are rendered to a role.
Ability = Literal["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]

ABILITIES: tuple[Ability, ...] = get_args(Ability)

# The one asymmetric entry here: a `domain/` concept `content/` needs, because a collection states
# which kind of entity may name it.
Kind = Literal["actor", "location", "item"]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _immutable[K, V](mapping: Mapping[K, V]) -> Mapping[K, V]:
    return MappingProxyType(dict(mapping))


def _as_dict[K, V](mapping: Mapping[K, V], serialize: SerializerFunctionWrapHandler) -> object:
    """Wrapped, not plain: a `mappingproxy` is no dict, so the schema is handed one before it runs.
    Serializing in its place would stop here, which a map nested in a map needs it not to."""
    return serialize(dict(mapping))


# `frozen=True` freezes a model's fields, never a dict one of them holds — so a keyed field on a
# `Frozen` model is writable, and the packs are loaded once at startup, which makes one edit
# permanent for every later turn.
type FrozenMap[K, V] = Annotated[
    Mapping[K, V], AfterValidator(_immutable), WrapSerializer(_as_dict)
]

# A keyed field that ships empty. An unvalidated default would skip the validator above and hand
# back the one mutable dict it exists to prevent. Fields declared with it never share one mapping.
EMPTY_FROZEN_MAP = Field(default_factory=dict, validate_default=True)


def updated[T: Frozen](obj: T, **changes: object) -> T:
    """Copy with changes, revalidated — `model_copy(update=)` would skip `extra="forbid"`."""
    return type(obj).model_validate(obj.model_dump() | changes)


class Attributes(Frozen):
    """One field per `Ability`, named for it, so `__getitem__` is a lookup by name."""

    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    def __getitem__(self, ability: Ability) -> int:
        return cast(int, getattr(self, ability))


# `__getitem__` is a getattr, this is what keeps a drifting field a startup failure rather than
# an AttributeError mid-roll.
assert set(ABILITIES) <= set(Attributes.model_fields), "an Ability has no Attributes field"
