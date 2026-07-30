from typing import Literal, Self

from aidm.utils.models import EMPTY_FROZEN_MAP, FrozenMap
from pydantic import Field, model_validator

from ...content.vocabulary import ConditionName
from ...utils.models import Ability, Attributes, Frozen, updated

Wounds = Literal["unharmed", "hurt", "badly hurt", "down"]


class StatBlock(Frozen):
    attributes: Attributes = Attributes()
    max_hp: int = Field(default=4, ge=1)
    hp: int = Field(default=4, ge=0)
    ac: int = Field(default=10, ge=0)
    conditions: tuple[ConditionName, ...] = ()
    # Keep monster bonuses absolute because player bonuses are derived from progression.
    saving_throws: FrozenMap[Ability, int] = EMPTY_FROZEN_MAP
    condition_immunities: tuple[ConditionName, ...] = ()

    @model_validator(mode="after")
    def _consistent_stats(self) -> Self:
        if self.hp > self.max_hp:
            raise ValueError(f"hp {self.hp} exceeds max_hp {self.max_hp}")
        if held := sorted(set(self.conditions) & set(self.condition_immunities)):
            raise ValueError(f"immune to conditions it suffers: {held}")
        return self

    def with_hp_delta(self, delta: int) -> Self:
        return updated(self, hp=max(0, min(self.max_hp, self.hp + delta)))

    def with_condition(self, condition: ConditionName, *, active: bool) -> Self:
        if active and condition in self.condition_immunities:
            return self
        held = set(self.conditions) | {condition} if active else set(self.conditions) - {condition}
        return updated(self, conditions=tuple(sorted(held)))

    @property
    def wounds(self) -> Wounds:
        if self.hp == 0:
            return "down"
        if self.hp * 2 <= self.max_hp:
            return "badly hurt"
        return "hurt" if self.hp < self.max_hp else "unharmed"
