from typing import Self

from pydantic import Field, model_validator

from aidm.state.base import Frozen
from aidm.state.creation import ContentSlug, CreationOption

from .mechanics import MAX_ARMOR, DamageDie


class Gear(Frozen):
    """One piece of starting equipment: the item the character holds, and what it is worth."""

    id: ContentSlug
    name: str
    brief: str
    slots: int = Field(default=1, ge=0, le=2)
    damage: DamageDie = 0
    armor: int = Field(default=0, ge=0, le=MAX_ARMOR)
    uses: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _weapon_or_armor_not_both(self) -> Self:
        if self.damage and self.armor:
            raise ValueError("a piece of gear is a weapon or armour, not both")
        return self


class Background(Frozen):
    """One of Cairn's twenty backgrounds: what they start carrying, and the table they roll on."""

    id: ContentSlug
    label: str
    detail: str = ""
    gold: int = Field(default=0, ge=0)
    gear: tuple[Gear, ...] = ()
    # The background's own d6 table, chosen rather than rolled because creation takes no rng.
    traits: tuple[CreationOption, ...] = ()
    chooses: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _invented_traits_fit_the_menu(self) -> Self:
        if self.chooses > len(self.traits):
            raise ValueError(f"{self.chooses} traits cannot be chosen from {len(self.traits)}")
        return self


class Spread(Frozen):
    """One pre-rolled set of 3d6 attributes and 1d6 Hit Protection."""

    id: ContentSlug
    label: str
    detail: str = ""
    strength: int = Field(ge=1)
    dexterity: int = Field(ge=1)
    willpower: int = Field(ge=1)
    hp: int = Field(ge=1)


class Pack(Frozen):
    """One published table set the player can build a character from."""

    name: str
    source: str
    license: str
    backgrounds: tuple[Background, ...] = Field(min_length=1)
    spreads: tuple[Spread, ...] = Field(min_length=1)
