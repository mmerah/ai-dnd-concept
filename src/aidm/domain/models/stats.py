"""Actor numbers: hit points, armour, conditions, and how a body reads to an onlooker."""

from typing import Literal, Self

from pydantic import Field, model_validator

from ...content.vocabulary import ConditionName
from ...utils.models import Ability, Attributes, Frozen, FrozenMap, updated

# All the Narrator may learn about another actor's hit points. Named for the wound it describes,
# because `Condition` is the SRD's word for blinded/prone/stunned — a different idea entirely.
Wounds = Literal["unharmed", "hurt", "badly hurt", "down"]


class StatBlock(Frozen):
    """Every number the reducer touches, and the whole of what a content record is snapshotted into.
    Defaults are the SRD commoner, so an authored scenario or an invented actor can omit them."""

    attributes: Attributes = Attributes()
    max_hp: int = Field(default=4, ge=1)
    hp: int = Field(default=4, ge=0)
    ac: int = Field(default=10, ge=0)
    conditions: tuple[ConditionName, ...] = ()
    # Absolute save bonuses, not modifiers, and only where the actor is good at a save: a monster's
    # come from its record. A player's come from `Progression`, so this stays empty for them.
    saving_throws: FrozenMap[Ability, int] = Field(default_factory=dict, validate_default=True)
    # Snapshotted from the archetype like every other number the reducer reads: a pack bump must not
    # be able to make a saved devil newly poisonable.
    condition_immunities: tuple[ConditionName, ...] = ()

    @model_validator(mode="after")
    def _consistent_stats(self) -> Self:
        if self.hp > self.max_hp:
            raise ValueError(f"hp {self.hp} exceeds max_hp {self.max_hp}")
        if held := sorted(set(self.conditions) & set(self.condition_immunities)):
            raise ValueError(f"immune to conditions it suffers: {held}")
        return self

    def with_hp_delta(self, delta: int) -> Self:
        """The one clamp: the resolver describes and the reducer applies through this."""
        return updated(self, hp=max(0, min(self.max_hp, self.hp + delta)))

    def with_condition(self, condition: ConditionName, *, active: bool) -> Self:
        """The one place a condition moves. An immune or redundant change returns `self`, so a
        caller comparing the result is asking the rules rather than restating them — the same shape
        as `with_hp_delta`, where a clamped change simply moves nothing."""
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
