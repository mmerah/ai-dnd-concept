from typing import Annotated, Literal

from pydantic import Field

from aidm.state.base import EntityId, Frozen, Slug
from aidm.state.dice import DiceExpr, RollMode

SUCCESS: Slug = "success"
FAILURE: Slug = "failure"
CONTESTED = frozenset({SUCCESS, FAILURE})
UNCONTESTED = frozenset[Slug]()

Mode = Annotated[
    RollMode,
    Field(description="`advantage` or `disadvantage` when the fiction grants it; one roll either."),
]
Bonus = Annotated[int, Field(ge=-10, le=30)]
Target = Annotated[int, Field(ge=1, le=40)]


class Attack(Frozen):
    """One attack with a carried weapon, or one attack line off the attacker's own stat block."""

    act: Literal["attack"] = "attack"
    actor_id: EntityId = Field(description="Exact id of the attacker, here with the player.")
    target_id: EntityId = Field(description="Exact id of what is attacked, here with the player.")
    weapon_item_id: EntityId | None = Field(
        default=None,
        description="Exact id of a weapon item the attacker carries. Null when the attack comes "
        "from a stat block instead.",
    )
    attack_bonus: Bonus | None = Field(
        default=None,
        description="To-hit bonus copied off a stat block's attack line, such as 4 for `Bite +4 to "
        "hit`. Null whenever a weapon item is named.",
    )
    damage: DiceExpr | None = Field(
        default=None,
        description="Damage dice copied off that same line, such as `1d4+2`. Null whenever a "
        "weapon item is named.",
    )
    two_handed: bool = Field(
        default=False, description="True only for a versatile weapon wielded in both hands."
    )
    mode: Mode = "normal"


class CastSpell(Frozen):
    """One spell, resolved from its record: the engine spends the slot before anything follows."""

    act: Literal["cast-spell"] = "cast-spell"
    actor_id: EntityId = Field(description="Exact id of the caster, here with the player.")
    spell: str = Field(
        min_length=1,
        description="The spell's content ref, written `pack/collection/index` exactly as rendered.",
    )
    slot_level: Annotated[int, Field(ge=1, le=9)] | None = Field(
        default=None,
        description="The spell-slot level it is cast from; a higher one upcasts it. Null for a "
        "cantrip, which spends nothing.",
    )
    target_id: EntityId | None = Field(
        default=None,
        description="Exact id of the one creature it is aimed at, here with the player. Null only "
        "when the spell touches nobody.",
    )


class Check(Frozen):
    """An ability check or a saving throw against a difficulty the Director sets. The roll
    settles only what `branches` write: a check made to gain or shed a condition needs that
    tag change in its `success` branch."""

    act: Literal["check"] = "check"
    actor_id: EntityId = Field(description="Exact id of the actor rolling, here with the player.")
    bonus: Bonus = Field(
        description="The actor's own bonus: their ability modifier, plus `proficiency-bonus` only "
        "where they are proficient."
    )
    dc: Target = Field(
        description="What the roll must reach: 5 easy, 10 moderate, 15 hard, 20 very hard."
    )
    reason: str = Field(min_length=1, description="What is being tested, in a few words.")
    mode: Mode = "normal"


class UseFeature(Frozen):
    """Spend one use of a limited-use feature and apply what its own text gives."""

    act: Literal["use-feature"] = "use-feature"
    actor_id: EntityId = Field(description="Exact id of the actor using it, here with the player")
    counter: Slug = Field(
        description="Exact key of that feature's counter, as the sheet spells it."
    )
    heal: DiceExpr | None = Field(
        default=None,
        description="The healing dice the feature's own text gives, bonuses included, such as "
        "`1d10 + 3`. Null when it heals nothing.",
    )


class Rest(Frozen):
    """A rest the fiction has finished, refilling what that rest restores and nothing else.
    A turn that prepares and then sleeps is a rest, not a check on the preparations."""

    act: Literal["rest"] = "rest"
    actor_id: EntityId = Field(description="Exact id of the resting actor, here with the player.")
    label: Literal["short-rest", "long-rest"] = Field(description="Which rest was taken.")


class Improvise(Frozen):
    """The roll for anything the other actions do not model, this engine's rules included."""

    act: Literal["improvise"] = "improvise"
    dice: DiceExpr = Field(description="The whole expression, bonuses included: `1d20 + 3`.")
    vs: Target | None = Field(
        default=None, description="The number the total must reach; null when nothing is contested."
    )
    reason: str = Field(min_length=1, description="What is being rolled, in a few words.")
    mode: Mode = "normal"
