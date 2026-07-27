"""Actor numbers: ability scores, hit points, and how they read to an onlooker."""

from typing import Literal, Self, assert_never

from pydantic import Field, model_validator

from .base import Ability, Frozen, updated


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


# All the Narrator may learn about another actor's hit points.
Condition = Literal["unharmed", "hurt", "badly hurt", "down"]


class StatBlock(Frozen):
    """Defaults are the SRD commoner, so an authored scenario or an invented actor can omit them."""

    attributes: Attributes = Attributes()
    max_hp: int = Field(default=4, ge=1)
    hp: int = Field(default=4, ge=0)

    @model_validator(mode="after")
    def _hp_within_max(self) -> Self:
        if self.hp > self.max_hp:
            raise ValueError(f"hp {self.hp} exceeds max_hp {self.max_hp}")
        return self

    def with_hp_delta(self, delta: int) -> Self:
        """The one clamp: the resolver describes and the reducer applies through this."""
        return updated(self, hp=max(0, min(self.max_hp, self.hp + delta)))

    @property
    def condition(self) -> Condition:
        if self.hp == 0:
            return "down"
        if self.hp * 2 <= self.max_hp:
            return "badly hurt"
        return "hurt" if self.hp < self.max_hp else "unharmed"
