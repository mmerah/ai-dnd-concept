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

Ability = Literal["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]

ABILITIES: tuple[Ability, ...] = get_args(Ability)

Kind = Literal["actor", "location", "item"]

SLUG_MAX_LENGTH = 64
Slug = Annotated[str, Field(pattern=r"^[a-z0-9-]+$", max_length=SLUG_MAX_LENGTH)]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _immutable[K, V](mapping: Mapping[K, V]) -> Mapping[K, V]:
    return MappingProxyType(dict(mapping))


def _as_dict[K, V](mapping: Mapping[K, V], serialize: SerializerFunctionWrapHandler) -> object:
    """Delegate after converting the unsupported mapping proxy."""
    return serialize(dict(mapping))


# Pydantic freezes fields, not mutable values stored inside them.
type FrozenMap[K, V] = Annotated[
    Mapping[K, V], AfterValidator(_immutable), WrapSerializer(_as_dict)
]

# Validate empty defaults so they also become immutable.
EMPTY_FROZEN_MAP = Field(default_factory=dict, validate_default=True)


def updated[T: Frozen](obj: T, **changes: object) -> T:
    """Copy with validation, unlike `model_copy(update=)`."""
    return type(obj).model_validate(obj.model_dump() | changes)


class Attributes(Frozen):
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    def __getitem__(self, ability: Ability) -> int:
        return cast(int, getattr(self, ability))


assert set(ABILITIES) <= set(Attributes.model_fields), "an Ability has no Attributes field"
