from typing import Annotated, Literal

from pydantic import Field

from aidm.state.base import EntityId, Frozen, Slug
from aidm.state.plan import Branched

from .mechanics import Attribute, Cairn2eEffect


class Save(Frozen):
    """A roll to avoid a bad outcome: d20 under the attribute, where 1 always passes and 20 always
    fails."""

    act: Literal["save"] = "save"
    actor_id: EntityId = Field(
        description="Exact id of the actor at risk: the player, or an actor here with them; when "
        "two sides oppose each other, whoever is most at risk saves."
    )
    attribute: Attribute = Field(
        description="Which attribute answers: strength for force and endurance, dexterity for "
        "speed, reflexes and stealth, willpower for nerve, persuasion, morale, panic and reading "
        "a spell."
    )
    risk: str = Field(min_length=1, description="What the actor avoids by passing, in one line.")


class Attack(Frozen):
    """One attack, which always hits: the weapon die less the target's armor comes off their HP."""

    act: Literal["attack"] = "attack"
    attacker_id: EntityId = Field(
        description="Exact id of the actor striking: the player, or an actor here with them."
    )
    target_id: EntityId = Field(
        description="Exact id of the actor being struck, who must be here too."
    )
    weapon_id: EntityId | None = Field(
        default=None,
        description="Exact id of a weapon the attacker carries; null is an unarmed blow, always "
        "d4.",
    )
    modifier: Literal["normal", "impaired", "enhanced"] = Field(
        default="normal",
        description="`impaired` (a position of weakness: cover, bound hands, a distant shot) "
        "rolls d4 whatever the weapon; `enhanced` (a position of advantage: a helpless foe, a "
        "daring manoeuvre) rolls d12.",
    )
    joined_by: tuple[EntityId, ...] = Field(
        default=(),
        description="Other actors here striking the same target in the same round; every damage "
        "die is rolled and only the single highest counts.",
    )


type Cairn2eAction = Annotated[Save | Attack, Field(discriminator="act")]


class TurnPlan(Branched[Cairn2eEffect]):
    action: Cairn2eAction | None = Field(
        default=None,
        description="The one action this turn resolves: a `save` when the fiction puts an actor "
        "at risk of a bad outcome, an `attack` when a blow actually lands, or null when nothing "
        "is risky enough to roll.",
    )


SAVE_LABELS = frozenset[Slug]({"pass", "fail"})
ATTACK_LABELS = frozenset[Slug]({"blocked", "hit", "wounded", "down"})
