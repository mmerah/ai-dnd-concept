from random import Random

from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.output import OutputSpec

from aidm.actions import DropItem, GiveItem, Move, TakeItem
from aidm.base import PLAYER_ID, Entity, EntityId, Kind
from aidm.directing import check_proposal, consequence_menu, walk_consequences
from aidm.transition import Direction
from aidm.world import GameState

from .access import actor_state, item_state
from .direction import (
    STORY_CONSEQUENCE_TYPES,
    ApplyCondition,
    ClearCondition,
    HelpfulActorTag,
    HelpfulGear,
    HinderingBurden,
    HinderingCondition,
    RecoverStress,
    Risk,
    StoryConsequence,
    StoryDirection,
    TakeStress,
    branches,
    dump_direction,
)
from .rules import StoryProposalRejected, StoryRules
from .state import StoryActorState

type StoryActorConsequence = Risk | TakeStress | RecoverStress | ApplyCondition | ClearCondition


_MECHANICS_TEMPLATE = """`mechanics` — an ordered list of Story consequences. The deterministic \
engine applies them in order and decides every `risk` outcome. Use exact ids from the consolidated \
scene above. Leave the list empty only when the turn changes no location, ownership, discovery, \
injury, condition, pressure, or other Story state.

Story uses stress and conditions instead of hit points. Stress tracks mounting harm and pressure; \
maximum stress means taken out. Conditions hold persistent injuries and statuses with concrete \
fictional effects. Core consequences handle discovery, movement, and inventory.

The consequences you can place in the list:

{consequences}"""

MECHANICS = _MECHANICS_TEMPLATE.replace(
    "{consequences}",
    consequence_menu(STORY_CONSEQUENCE_TYPES),
)


class StoryDirector:
    def __init__(self, rules: StoryRules) -> None:
        self._rules = rules

    def output(self) -> OutputSpec[Direction]:
        def direct(ctx: RunContext[GameState], proposal: StoryDirection) -> Direction:
            return self.check(ctx.deps, proposal)

        return NativeOutput(direct, name="StoryDirection")

    def instructions(self) -> str:
        return MECHANICS

    def check(self, state: GameState, direction: StoryDirection) -> Direction:
        """Every fault the model can fix becomes a retry; the flat direction is what core keeps."""
        flat = dump_direction(direction)
        if fault := check_proposal(
            state,
            direction.mechanics,
            direction.speaker_id,
            branches,
            (self._check_core_presence,),
        ):
            raise ModelRetry(fault)
        for consequence in walk_consequences(direction.mechanics, branches):
            if isinstance(
                consequence,
                Risk | TakeStress | RecoverStress | ApplyCondition | ClearCondition,
            ):
                self._validate_actor_consequence(state, consequence)
        try:
            self._rules.resolve(flat, state, Random(0))
        except StoryProposalRejected as error:
            raise ModelRetry(str(error)) from error
        return flat

    def _validate_actor_consequence(
        self,
        state: GameState,
        consequence: StoryActorConsequence,
    ) -> None:
        actor_id = self._actor_id(consequence)
        actor = state.player if actor_id == PLAYER_ID else self._require(state, actor_id, "actor")
        if actor.id != PLAYER_ID:
            if not actor.known:
                raise ModelRetry(f"actor {actor.id!r} has not been revealed")
            if not state.is_here(actor):
                raise ModelRetry(f"actor {actor.id!r} is not here with the player")
        sheet = actor_state(state.world.record(actor.id, "actor").rules)
        match consequence:
            case Risk():
                if sheet.taken_out:
                    raise ModelRetry(f"actor {actor.id!r} is taken out")
                self._validate_factors(state, actor, sheet, consequence)
            case ClearCondition(condition_id=condition_id):
                if not any(condition.id == condition_id for condition in sheet.conditions):
                    raise ModelRetry(f"condition {condition_id!r} is not active on {actor.id!r}")
            case ApplyCondition() | TakeStress() | RecoverStress():
                return

    @staticmethod
    def _actor_id(consequence: StoryActorConsequence) -> EntityId:
        return PLAYER_ID if consequence.actor_id is None else consequence.actor_id

    def _validate_factors(
        self,
        state: GameState,
        actor: Entity,
        sheet: StoryActorState,
        risk: Risk,
    ) -> None:
        match risk.helpful:
            case None:
                pass
            case HelpfulActorTag(id=tag_id):
                tag = next((tag for tag in sheet.tags if tag.id == tag_id), None)
                if tag is None or tag.kind not in ("edge", "bond"):
                    raise ModelRetry(
                        f"helpful tag {tag_id!r} is not an edge or bond on {actor.id!r}"
                    )
            case HelpfulGear(item_id=item_id):
                item = self._require(state, item_id, "item")
                if item.parent_id != actor.id:
                    raise ModelRetry(f"gear item {item.id!r} is not carried by {actor.id!r}")
                if item_state(state.world.record(item_id, "item").rules).gear is None:
                    raise ModelRetry(f"item {item.id!r} has no gear benefit")
        match risk.hindering:
            case None:
                pass
            case HinderingBurden(id=tag_id):
                tag = next((tag for tag in sheet.tags if tag.id == tag_id), None)
                if tag is None or tag.kind != "burden":
                    raise ModelRetry(f"hindering tag {tag_id!r} is not a burden on {actor.id!r}")
            case HinderingCondition(id=condition_id):
                if not any(condition.id == condition_id for condition in sheet.conditions):
                    raise ModelRetry(f"condition {condition_id!r} is not active on {actor.id!r}")

    @staticmethod
    def _check_core_presence(state: GameState, action: StoryConsequence) -> str | None:
        here = state.player_location
        match action:
            case TakeItem(item_id=item_id):
                item = state.world.find(item_id)
                if item is None or item.kind != "item" or item.parent_id != here:
                    return f"item {item_id!r} is not loose at the player's location"
            case DropItem(item_id=item_id) | GiveItem(item_id=item_id):
                item = state.world.find(item_id)
                if item is None or item.kind != "item" or item.parent_id != PLAYER_ID:
                    return f"the player does not carry item {item_id!r}"
            case Move(actor_id=actor_id, location_id=location_id):
                if actor_id is not None and actor_id != PLAYER_ID:
                    actor = state.world.find(actor_id)
                    if (
                        actor is None
                        or actor.kind != "actor"
                        or actor.parent_id != here
                        and location_id != here
                    ):
                        return f"movement of actor {actor_id!r} would not be witnessed"
            case _:
                pass
        return None

    @staticmethod
    def _require(state: GameState, entity_id: EntityId, expected: Kind) -> Entity:
        entity = state.world.find(entity_id)
        if entity is None:
            raise ModelRetry(f"unknown entity id {entity_id!r}")
        if entity.kind != expected:
            raise ModelRetry(f"{entity_id!r} is a {entity.kind}, not a {expected}")
        return entity
