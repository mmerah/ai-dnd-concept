import json
from random import Random

from aidm.agents.context import DirectorScene
from aidm.domain.actions import (
    CoreAction,
    CoreActionUnion,
    DropItem,
    GiveItem,
    Move,
    TakeItem,
    action_references,
    is_core_action,
)
from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.definitions import ScenarioMeta
from aidm.domain.direction import DirectionRecord
from aidm.domain.engine import EngineStamp
from aidm.domain.entities import ActorEntity, Entity, ItemEntity
from aidm.domain.state import GameState
from pydantic import BaseModel
from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.output import OutputSpec

from .codecs import ACTOR_STATE_CODEC, ITEM_STATE_CODEC
from .constants import ENGINE_ID, SCHEMA_VERSION
from .direction import (
    STORY_MECHANICS_ADAPTER,
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
    flatten,
)
from .instructions import MECHANICS
from .models import StoryActorState
from .rules import StoryProposalRejected, StoryRules

type StoryActorConsequence = Risk | TakeStress | RecoverStress | ApplyCondition | ClearCondition


class StoryDirector:
    def __init__(self, rules: StoryRules, stamp: EngineStamp) -> None:
        self._rules = rules
        self._stamp = stamp

    @property
    def output(self) -> OutputSpec[BaseModel]:
        return NativeOutput(StoryDirection)

    def instructions(self) -> str:
        return MECHANICS

    def validate(
        self,
        ctx: RunContext[DirectorScene],
        direction: BaseModel,
    ) -> BaseModel:
        if not isinstance(direction, StoryDirection):
            raise TypeError(f"Story Director received {type(direction).__name__}")
        scene = ctx.deps
        if direction.speaker_id == PLAYER_ID:
            raise ModelRetry("speaker_id names another actor, never the player")
        if direction.speaker_id is not None:
            speaker = self._require(scene, direction.speaker_id, ActorEntity)
            if not speaker.known:
                raise ModelRetry(f"speaker {speaker.id!r} has not been revealed")
            if not scene.is_here(speaker):
                raise ModelRetry(f"speaker {speaker.id!r} is not here with the player")
        for consequence in flatten(direction.mechanics):
            self._validate_consequence(scene, consequence)
        state = GameState(
            engine=self._stamp,
            scenario=ScenarioMeta(title="validation", premise="validation"),
            world=scene.canon,
            rules=scene.game_rules,
        )
        try:
            self._rules.resolve(direction, state, Random(0))
        except StoryProposalRejected as error:
            raise ModelRetry(str(error)) from error
        return direction

    def record(self, direction: BaseModel) -> DirectionRecord:
        if not isinstance(direction, StoryDirection):
            raise TypeError(f"Story Director received {type(direction).__name__}")
        mechanics: object = json.loads(STORY_MECHANICS_ADAPTER.dump_json(direction.mechanics))
        return DirectionRecord.model_validate(
            {
                "engine": ENGINE_ID,
                "schema_version": SCHEMA_VERSION,
                "intent": direction.intent,
                "tone": direction.tone,
                "speaker_id": direction.speaker_id,
                "mechanics": mechanics,
            }
        )

    def _validate_consequence(
        self,
        scene: DirectorScene,
        consequence: StoryConsequence,
    ) -> None:
        if isinstance(consequence, CoreAction):
            if not is_core_action(consequence):
                raise TypeError(f"unsupported core action {type(consequence).__name__}")
            fault = consequence.check()
            if fault is not None:
                raise ModelRetry(fault)
            for entity_id, reference in action_references(consequence):
                entity = scene.canon.entities.get(entity_id)
                if entity is None:
                    raise ModelRetry(f"unknown entity id {entity_id!r}")
                if reference.kind is not None and entity.kind != reference.kind:
                    raise ModelRetry(f"{entity_id!r} is a {entity.kind}, not a {reference.kind}")
                if reference.present and not scene.is_here(entity):
                    raise ModelRetry(f"{entity_id!r} is not here with the player")
            self._validate_core_presence(scene, consequence)
            return
        actor_id = self._actor_id(consequence)
        actor = (
            scene.player if actor_id == PLAYER_ID else self._require(scene, actor_id, ActorEntity)
        )
        if actor.id != PLAYER_ID:
            if not actor.known:
                raise ModelRetry(f"actor {actor.id!r} has not been revealed")
            if not scene.is_here(actor):
                raise ModelRetry(f"actor {actor.id!r} is not here with the player")
        actor_state = self._actor_state(actor)
        match consequence:
            case Risk():
                if actor_state.taken_out:
                    raise ModelRetry(f"actor {actor.id!r} is taken out")
                self._validate_factors(scene, actor, actor_state, consequence)
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
        scene: DirectorScene,
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
                item = self._require(scene, item_id, ItemEntity)
                if item.container_id != actor.id:
                    raise ModelRetry(f"gear item {item.id!r} is not carried by {actor.id!r}")
                if item.rules is None or ITEM_STATE_CODEC.decode(item.rules).gear is None:
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
    def _validate_core_presence(scene: DirectorScene, action: CoreActionUnion) -> None:
        match action:
            case TakeItem(item_id=item_id):
                item = scene.canon.entities[item_id]
                if not isinstance(item, ItemEntity) or item.container_id != scene.where.id:
                    raise ModelRetry(f"item {item_id!r} is not loose at the player's location")
            case DropItem(item_id=item_id) | GiveItem(item_id=item_id):
                item = scene.canon.entities[item_id]
                if not isinstance(item, ItemEntity) or item.container_id != PLAYER_ID:
                    raise ModelRetry(f"the player does not carry item {item_id!r}")
            case Move(actor_id=actor_id, location_id=location_id):
                if actor_id is not None and actor_id != PLAYER_ID:
                    actor = scene.canon.entities[actor_id]
                    if (
                        not isinstance(actor, ActorEntity)
                        or actor.location_id != scene.where.id
                        and location_id != scene.where.id
                    ):
                        raise ModelRetry(f"movement of actor {actor_id!r} would not be witnessed")
            case _:
                return

    @staticmethod
    def _actor_state(actor: ActorEntity) -> StoryActorState:
        if actor.rules is None:
            raise ValueError(f"Story actor {actor.id!r} has no rules data")
        return ACTOR_STATE_CODEC.decode(actor.rules)

    @staticmethod
    def _require[T: Entity](
        scene: DirectorScene,
        entity_id: EntityId,
        expected: type[T],
    ) -> T:
        entity = scene.canon.entities.get(entity_id)
        if entity is None:
            raise ModelRetry(f"unknown entity id {entity_id!r}")
        if not isinstance(entity, expected):
            raise ModelRetry(f"{entity_id!r} is a {entity.kind}, not a {expected.__name__}")
        return entity
