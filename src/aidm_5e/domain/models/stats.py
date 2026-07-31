from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.utils.models import Mutable

from ...content.vocabulary import ConditionName
from ...utils.models import Ability, Attributes

Wounds = Literal["unharmed", "hurt", "badly hurt", "down"]


class StatBlock(Mutable):
    attributes: Attributes = Attributes()
    max_hp: int = Field(default=4, ge=1)
    hp: int = Field(default=4, ge=0)
    ac: int = Field(default=10, ge=0)
    conditions: tuple[ConditionName, ...] = ()
    # Keep monster bonuses absolute because player bonuses are derived from progression.
    saving_throws: dict[Ability, int] = Field(default_factory=dict)
    condition_immunities: tuple[ConditionName, ...] = ()

    @model_validator(mode="after")
    def _consistent_stats(self) -> Self:
        if self.hp > self.max_hp:
            raise ValueError(f"hp {self.hp} exceeds max_hp {self.max_hp}")
        if held := sorted(set(self.conditions) & set(self.condition_immunities)):
            raise ValueError(f"immune to conditions it suffers: {held}")
        return self

    def apply_hp_delta(self, delta: int) -> int:
        """Clamp to the survivable range and report the change that actually landed."""
        before = self.hp
        self.hp = max(0, min(self.max_hp, before + delta))
        return self.hp - before

    def apply_condition(self, condition: ConditionName, *, active: bool) -> bool:
        if active and condition in self.condition_immunities:
            return False
        held: set[ConditionName] = set(self.conditions)
        if active:
            held.add(condition)
        else:
            held.discard(condition)
        changed = tuple(sorted(held))
        if changed == self.conditions:
            return False
        self.conditions = changed
        return True

    @property
    def wounds(self) -> Wounds:
        if self.hp == 0:
            return "down"
        if self.hp * 2 <= self.max_hp:
            return "badly hurt"
        return "hurt" if self.hp < self.max_hp else "unharmed"
