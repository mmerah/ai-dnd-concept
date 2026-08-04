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


class Value(BaseModel):
    """Keeps Pydantic's field hash, unlike `aidm.kernel.base.Frozen`: refs key the ruleset maps."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _immutable[K, V](mapping: Mapping[K, V]) -> Mapping[K, V]:
    return MappingProxyType(dict(mapping))


def _as_dict[K, V](mapping: Mapping[K, V], serialize: SerializerFunctionWrapHandler) -> object:
    return serialize(dict(mapping))


type FrozenMap[K, V] = Annotated[
    Mapping[K, V],
    AfterValidator(_immutable),
    WrapSerializer(_as_dict),
]
"""A pack loads once and every turn shares its records, so an edit would outlive its turn."""

EMPTY_FROZEN_MAP = Field(default_factory=dict, validate_default=True)

# Upstream indexes run hyphens together ('...red---fire-damage'), so laxer than `Slug`.
CONTENT_SLUG_MAX_LENGTH = 64
ContentSlug = Annotated[str, Field(pattern=r"^[a-z0-9-]+$", max_length=CONTENT_SLUG_MAX_LENGTH)]


Ability = Literal["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]

ABILITIES: tuple[Ability, ...] = get_args(Ability)


class Attributes(Value):
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    def __getitem__(self, ability: Ability) -> int:
        return cast(int, getattr(self, ability))


assert set(ABILITIES) <= set(Attributes.model_fields), "an Ability has no Attributes field"
