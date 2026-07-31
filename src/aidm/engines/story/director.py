from collections.abc import Sequence
from random import Random

from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.output import OutputSpec

from aidm.base import PLAYER_ID, ActorEntity, Entity, EntityId, ItemEntity
from aidm.world import GameState

from .access import story_state
from .actions import (
    CoreAction,
    CoreActionUnion,
    DropItem,
    GiveItem,
    Move,
    TakeItem,
    action_references,
    is_core_action,
)
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
    StoryAction,
    StoryConsequence,
    StoryDirection,
    TakeStress,
    flatten,
)
from .rules import StoryProposalRejected, StoryRules
from .state import StoryActorState, StoryState

type StoryActorConsequence = Risk | TakeStress | RecoverStress | ApplyCondition | ClearCondition


def consequence_menu(
    types: Sequence[type[CoreAction] | type[StoryAction]],
) -> str:
    """Each consequence's docstring, GUIDANCE and field descriptions are prompt text."""
    lines: list[str] = []
    for consequence in types:
        action = consequence.model_fields["action"].default
        summary = consequence.__doc__
        if not isinstance(action, str) or summary is None:
            raise TypeError(f"{consequence.__name__} has incomplete prompt documentation")
        fields = "\n".join(
            f"  - `{name}`: {field.description}"
            for name, field in consequence.model_fields.items()
            if name != "action" and field.description
        )
        lines.append(f"### `{action}` — {summary}\n{consequence.GUIDANCE}\n{fields}")
    return "\n\n".join(lines)


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

    @property
    def output(self) -> OutputSpec[StoryDirection]:
        return NativeOutput(StoryDirection)

    def instructions(self) -> str:
        return MECHANICS

    def validate(
        self,
        ctx: RunContext[GameState],
        direction: StoryDirection,
    ) -> StoryDirection:
        state = ctx.deps
        engine = story_state(state)
        if direction.speaker_id == PLAYER_ID:
            raise ModelRetry("speaker_id names another actor, never the player")
        if direction.speaker_id is not None:
            speaker = self._require(state, direction.speaker_id, ActorEntity)
            if not speaker.known:
                raise ModelRetry(f"speaker {speaker.id!r} has not been revealed")
            if not state.is_here(speaker):
                raise ModelRetry(f"speaker {speaker.id!r} is not here with the player")
        for consequence in flatten(direction.mechanics):
            self._validate_consequence(state, engine, consequence)
        try:
            self._rules.resolve(direction, state, Random(0))
        except StoryProposalRejected as error:
            raise ModelRetry(str(error)) from error
        return direction

    def _validate_consequence(
        self,
        state: GameState,
        engine: StoryState,
        consequence: StoryConsequence,
    ) -> None:
        if isinstance(consequence, CoreAction):
            if not is_core_action(consequence):
                raise TypeError(f"unsupported core action {type(consequence).__name__}")
            fault = consequence.check()
            if fault is not None:
                raise ModelRetry(fault)
            for entity_id, reference in action_references(consequence):
                entity = state.world.entities.get(entity_id)
                if entity is None:
                    raise ModelRetry(f"unknown entity id {entity_id!r}")
                if reference.kind is not None and entity.kind != reference.kind:
                    raise ModelRetry(f"{entity_id!r} is a {entity.kind}, not a {reference.kind}")
                if reference.present and not state.is_here(entity):
                    raise ModelRetry(f"{entity_id!r} is not here with the player")
            self._validate_core_presence(state, consequence)
            return
        actor_id = self._actor_id(consequence)
        actor = (
            state.player if actor_id == PLAYER_ID else self._require(state, actor_id, ActorEntity)
        )
        if actor.id != PLAYER_ID:
            if not actor.known:
                raise ModelRetry(f"actor {actor.id!r} has not been revealed")
            if not state.is_here(actor):
                raise ModelRetry(f"actor {actor.id!r} is not here with the player")
        actor_state = engine.actor(actor.id)
        match consequence:
            case Risk():
                if actor_state.taken_out:
                    raise ModelRetry(f"actor {actor.id!r} is taken out")
                self._validate_factors(state, engine, actor, actor_state, consequence)
            case ClearCondition(condition_id=condition_id):
                if not any(condition.id == condition_id for condition in actor_state.conditions):
                    raise ModelRetry(f"condition {condition_id!r} is not active on {actor.id!r}")
            case ApplyCondition() | TakeStress() | RecoverStress():
                return

    @staticmethod
    def _actor_id(consequence: StoryActorConsequence) -> EntityId:
        return PLAYER_ID if consequence.actor_id is None else consequence.actor_id

    def _validate_factors(
        self,
        state: GameState,
        engine: StoryState,
        actor: ActorEntity,
        actor_state: StoryActorState,
        risk: Risk,
    ) -> None:
        match risk.helpful:
            case None:
                pass
            case HelpfulActorTag(id=tag_id):
                tag = next((tag for tag in actor_state.tags if tag.id == tag_id), None)
                if tag is None or tag.kind not in ("edge", "bond"):
                    raise ModelRetry(
                        f"helpful tag {tag_id!r} is not an edge or bond on {actor.id!r}"
                    )
            case HelpfulGear(item_id=item_id):
                item = self._require(state, item_id, ItemEntity)
                if item.container_id != actor.id:
                    raise ModelRetry(f"gear item {item.id!r} is not carried by {actor.id!r}")
                if engine.item(item_id).gear is None:
                    raise ModelRetry(f"item {item.id!r} has no gear benefit")
        match risk.hindering:
            case None:
                pass
            case HinderingBurden(id=tag_id):
                tag = next((tag for tag in actor_state.tags if tag.id == tag_id), None)
                if tag is None or tag.kind != "burden":
                    raise ModelRetry(f"hindering tag {tag_id!r} is not a burden on {actor.id!r}")
            case HinderingCondition(id=condition_id):
                if not any(condition.id == condition_id for condition in actor_state.conditions):
                    raise ModelRetry(f"condition {condition_id!r} is not active on {actor.id!r}")

    @staticmethod
    def _validate_core_presence(state: GameState, action: CoreActionUnion) -> None:
        here = state.player.location_id
        match action:
            case TakeItem(item_id=item_id):
                item = state.world.entities[item_id]
                if not isinstance(item, ItemEntity) or item.container_id != here:
                    raise ModelRetry(f"item {item_id!r} is not loose at the player's location")
            case DropItem(item_id=item_id) | GiveItem(item_id=item_id):
                item = state.world.entities[item_id]
                if not isinstance(item, ItemEntity) or item.container_id != PLAYER_ID:
                    raise ModelRetry(f"the player does not carry item {item_id!r}")
            case Move(actor_id=actor_id, location_id=location_id):
                if actor_id is not None and actor_id != PLAYER_ID:
                    actor = state.world.entities[actor_id]
                    if (
                        not isinstance(actor, ActorEntity)
                        or actor.location_id != here
                        and location_id != here
                    ):
                        raise ModelRetry(f"movement of actor {actor_id!r} would not be witnessed")
            case _:
                return

    @staticmethod
    def _require[T: Entity](
        state: GameState,
        entity_id: EntityId,
        expected: type[T],
    ) -> T:
        entity = state.world.entities.get(entity_id)
        if entity is None:
            raise ModelRetry(f"unknown entity id {entity_id!r}")
        if not isinstance(entity, expected):
            raise ModelRetry(f"{entity_id!r} is a {entity.kind}, not a {expected.__name__}")
        return entity
