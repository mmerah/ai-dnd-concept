"""Primitives shared by `domain/` and `content/`. They live here because `content/` must not import
`domain/`, and neither should own what the other also needs."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal, assert_never, get_args

from pydantic import AfterValidator, BaseModel, ConfigDict, PlainSerializer

# Spelled in full because that is how they are rendered to a role.
Ability = Literal["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]

ABILITIES: tuple[Ability, ...] = get_args(Ability)


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _immutable[K, V](mapping: Mapping[K, V]) -> Mapping[K, V]:
    return MappingProxyType(dict(mapping))


def _plain[K, V](mapping: Mapping[K, V]) -> dict[K, V]:
    return dict(mapping)


# `frozen=True` freezes a model's fields, never a dict one of them holds — so a keyed field on a
# `Frozen` model is writable, and `store.library()` is cached, which makes one edit permanent for
# every later turn. Every mapping field is declared with this. A field wanting an empty default
# needs `Field(default_factory=dict, validate_default=True)`: an unvalidated default skips the
# validator below and hands back the one mutable dict this exists to prevent.
type FrozenMap[K, V] = Annotated[Mapping[K, V], AfterValidator(_immutable), PlainSerializer(_plain)]


def updated[T: Frozen](obj: T, **changes: object) -> T:
    """Copy with changes, revalidated — `model_copy(update=)` would skip `extra="forbid"`."""
    return type(obj).model_validate(obj.model_dump() | changes)


class Attributes(Frozen):
    """`__getitem__` is exhaustive on `Ability`, so a drifting field is a type error."""

    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    def __getitem__(self, ability: Ability) -> int:
        match ability:
            case "strength":
                return self.strength
            case "dexterity":
                return self.dexterity
            case "constitution":
                return self.constitution
            case "intelligence":
                return self.intelligence
            case "wisdom":
                return self.wisdom
            case "charisma":
                return self.charisma
            case _:
                assert_never(ability)
