from collections.abc import Callable
from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from aidm.core.base import EntityId
from aidm.core.dice import Magnitude
from aidm.core.facts import Fact
from aidm.core.tools import TurnContext

from . import features, mechanics, progression, rolls, spells
from .access import Dnd5eWorld
from .content.records.spells import MAX_SPELL_LEVEL, SpellLevel
from .content.vocabulary import CONDITION_NAMES, ConditionName, RestType
from .identity import ENGINE_ID
from .ruleset import Ruleset
from .state import Dnd5eRules, FeatureKey, SpellKey
from .values import ABILITIES, Ability

DIRECTOR_INSTRUCTIONS = """The 5e rules roll every die, spend every resource, and decide every \
outcome. Where an amount is uncertain, give the dice — '1d6', '2d6 + 3' — and let them fall rather \
than choosing the number yourself. All ids MUST be exact ids from the lists above.

Whether a blow lands, a spell takes hold, or a save is made is never yours to decide. Call \
`roll_check` or `roll_save` first, read the result, and only then apply what follows."""

TargetArg = Annotated[
    EntityId | None,
    Field(description="Id of the `actor` affected, here with the player; omit for them."),
]


class Dnd5eTools:
    """The Director's 5e tools, built once with the ruleset they resolve against."""

    def __init__(self, ruleset: Ruleset) -> None:
        self._ruleset = ruleset

    def toolset(self) -> FunctionToolset[TurnContext[Dnd5eRules]]:
        return FunctionToolset[TurnContext[Dnd5eRules]](
            [
                self.attack,
                self.roll_check,
                self.roll_save,
                self.cast,
                self.use_feature,
                self.rest,
                self.damage,
                self.heal,
                self.apply_condition,
                self.level_up,
            ]
        )

    def _apply(
        self, deps: TurnContext[Dnd5eRules], resolve: Callable[[Dnd5eWorld], list[Fact]]
    ) -> str:
        facts = resolve(Dnd5eWorld(state=deps.draft, rng=deps.rng, ruleset=self._ruleset))
        return deps.record(facts)

    def attack(
        self,
        ctx: RunContext[TurnContext[Dnd5eRules]],
        weapon: Annotated[
            str,
            Field(
                description=(
                    "The attacker's own attack by name, or an item they carry, spelled as shown."
                )
            ),
        ],
        target_id: Annotated[
            EntityId | None,
            Field(description="Id of the `actor` struck at, here with the player; omit for them."),
        ] = None,
        attacker_id: Annotated[
            EntityId | None,
            Field(description="Id of the `actor` attacking; omit for the player."),
        ] = None,
    ) -> str:
        """Strike another actor; the rules determine the hit and damage.

        Use for a deliberate blow — the player swinging, or someone here swinging at them. Name the
        weapon exactly as you were shown it: one of the attacker's own attacks from their stat
        block, or an item they carry. The to-hit roll, the target's armour and the damage are all
        the rules' business, so there is nothing to roll beforehand. Nobody strikes at themselves,
        so name at most one of the two ids.
        """
        return self._apply(
            ctx.deps, lambda world: mechanics.attack(world, weapon, target_id, attacker_id)
        )

    def roll_check(
        self,
        ctx: RunContext[TurnContext[Dnd5eRules]],
        ability: Annotated[Ability, Field(description=f"One of: {', '.join(ABILITIES)}.")],
        dc: Annotated[int, Field(description="5 easy, 10 moderate, 15 hard, 20 very hard.")],
    ) -> str:
        """Roll the player's ability check against a DC and report success or failure.

        Use when something the player attempts can fail. Read the result, then apply what passing
        or failing does with further calls.
        """
        return self._apply(
            ctx.deps,
            lambda world: [rolls.roll_check(world.player(), ability, dc, world.rng).fact],
        )

    def roll_save(
        self,
        ctx: RunContext[TurnContext[Dnd5eRules]],
        ability: Annotated[Ability, Field(description=f"One of: {', '.join(ABILITIES)}.")],
        dc: Annotated[int, Field(description="5 easy, 10 moderate, 15 hard, 20 very hard.")],
        target_id: Annotated[
            EntityId | None,
            Field(description="Id of the `actor` resisting, here with the player; omit for them."),
        ] = None,
    ) -> str:
        """Make an actor resist something aimed at them and report success or failure.

        Use when something is done *to* someone and they may shrug it off — a trap's gas, a spell,
        a shove. The difference from `roll_check` is who rolls and which bonus applies; the rules
        know both. Read the result, then apply what follows.
        """
        return self._apply(ctx.deps, lambda world: self._saved(world, ability, dc, target_id))

    @staticmethod
    def _saved(
        world: Dnd5eWorld, ability: Ability, dc: int, target_id: EntityId | None
    ) -> list[Fact]:
        target = world.target(target_id)
        rolled = rolls.roll_save(target, ability, dc, world.rng)
        return [*mechanics.reveal(world, target), rolled.fact]

    def cast(
        self,
        ctx: RunContext[TurnContext[Dnd5eRules]],
        spell: Annotated[
            SpellKey, Field(description="Exact id of a spell from the player's spell list.")
        ],
        slot_level: Annotated[
            SpellLevel,
            Field(description=f"Level of the slot spent, 1-{MAX_SPELL_LEVEL}; 0 for a cantrip."),
        ],
        target_id: Annotated[
            EntityId | None,
            Field(description="Id of the `actor` aimed at, here with the player; omit for them."),
        ] = None,
    ) -> str:
        """Cast one of the player's spells; the rules spend the slot and resolve it.

        Copy the exact spell id, and give the level of the slot spent — the spell's own level or
        higher, or 0 for a cantrip. The rules verify the spell, the slot and any attack roll, save,
        damage or healing; whether it lands is never yours to decide. Whatever the spell's
        description does beyond that is yours to apply with further calls.
        """
        return self._apply(ctx.deps, lambda world: spells.cast(world, spell, slot_level, target_id))

    def use_feature(
        self,
        ctx: RunContext[TurnContext[Dnd5eRules]],
        feature: Annotated[
            FeatureKey, Field(description="Exact id of an owned feature marked `usable`.")
        ],
        amount: Annotated[
            int,
            Field(
                ge=1,
                description="Resource points spent; 1 unless the feature allows a chosen amount.",
            ),
        ] = 1,
    ) -> str:
        """Use one of the player's active class features.

        Use when the player invokes a feature marked `usable` in their feature list. Copy its exact
        feature id. The rules verify ownership and remaining uses, and apply effects marked
        `engine-resolved`. For a `description-guided` feature, apply the concrete consequences its
        description requires with further calls.
        """
        return self._apply(ctx.deps, lambda world: features.use(world, feature, amount))

    def rest(
        self,
        ctx: RunContext[TurnContext[Dnd5eRules]],
        rest: Annotated[RestType, Field(description="The completed rest: `short` or `long`.")],
    ) -> str:
        """Complete a short or long rest.

        Use only when the fiction establishes that the player completes the rest. This recharges
        the features and spell slots that the rest is long enough to restore; it does not invent
        healing or other rest benefits.
        """
        return self._apply(ctx.deps, lambda world: [_rested(world, rest)])

    def damage(
        self,
        ctx: RunContext[TurnContext[Dnd5eRules]],
        amount: Annotated[
            Magnitude, Field(description="Hit points lost: dice like '2d6', or a number >= 0.")
        ],
        target_id: TargetArg = None,
    ) -> str:
        """Reduce an actor's hit points by dice you roll, or by a flat amount.

        Use when someone here takes damage. Prefer dice — '1d6', '2d6 + 3' — and let them fall; a
        flat number is for harm with nothing left to chance. Whether a blow lands is never yours to
        decide: roll for it first.
        """
        return self._apply(
            ctx.deps, lambda world: mechanics.hp_facts(world, target_id, amount, sign=-1)
        )

    def heal(
        self,
        ctx: RunContext[TurnContext[Dnd5eRules]],
        amount: Annotated[
            Magnitude, Field(description="Hit points restored: dice like '1d4', or a number >= 0.")
        ],
        target_id: TargetArg = None,
    ) -> str:
        """Restore an actor's hit points by dice you roll, or by a flat amount.

        Use when someone here is healed; the same amount and target rules as `damage`.
        """
        return self._apply(
            ctx.deps, lambda world: mechanics.hp_facts(world, target_id, amount, sign=1)
        )

    def apply_condition(
        self,
        ctx: RunContext[TurnContext[Dnd5eRules]],
        condition: Annotated[
            ConditionName, Field(description=f"One of: {', '.join(CONDITION_NAMES)}.")
        ],
        ends: Annotated[
            bool, Field(description="True to lift the condition instead of applying.")
        ] = False,
        target_id: TargetArg = None,
    ) -> str:
        """Put an actor under an SRD condition, or lift one they are already under.

        Use when someone here is blinded, grappled, frightened, knocked prone and so on, and when
        that ends. A creature immune to the condition is unaffected — you do not need to check, the
        rules do. Whether it takes hold is not yours to decide when it could be resisted: roll a
        save first.
        """
        return self._apply(
            ctx.deps,
            lambda world: mechanics.change_condition(world, target_id, condition, ends=ends),
        )

    def level_up(self, ctx: RunContext[TurnContext[Dnd5eRules]]) -> str:
        """Unlock the player's next level-up.

        Use once when the player's achievements earn a new level. This unlocks the level-up UI
        where the player makes any character choices; it does not choose or apply the level itself.
        Do not use it while the player's state says an advancement is already waiting.
        """
        return self._apply(ctx.deps, lambda world: progression.offer(world.player()))


def _rested(world: Dnd5eWorld, rest: RestType) -> Fact:
    refilled = features.recharged(world, rest)
    slots = spells.recharged(world, rest)
    names = [*refilled, *(("spell slots",) if slots else ())]
    recharged = f"; recharged {', '.join(names)}" if names else ""
    trace = f"completed a {rest} rest{recharged}"
    return Fact(
        source=ENGINE_ID,
        kind="rested",
        trace=trace,
        narrator=trace,
        data={"rest": rest, "refilled": list(refilled), "slots": list(slots)},
    )
