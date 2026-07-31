from collections.abc import Sequence
from random import Random

from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.entities import ActorEntity, Entity, ItemEntity
from aidm.domain.events import Event, RuleEvent
from aidm.domain.reducer import apply
from aidm.domain.state import GameState
from aidm.utils.models import updated

from .actions import (
    CoreAction,
    CoreActionRejected,
    is_core_action,
    resolve_core_action,
)
from .constants import ENGINE_ID, SCHEMA_VERSION
from .direction import (
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
)
from .events import (
    ApproachRaised,
    ConditionApplied,
    ConditionCleared,
    GearAcquired,
    GrowthMarked,
    GrowthReset,
    MaximumStressIncreased,
    Revived,
    RiskRolled,
    StoryOutcome,
    StressChanged,
    TagAdded,
    TagRemoved,
    TagRewritten,
    TakenOut,
    decode_story_event,
    encode_story_event,
)
from .models import StoryActorState, StoryItemState, StoryState
from .state import created_state, story_state


class StoryProposalRejected(ValueError):
    """A proposed direction the rules cannot resolve; the Director turns this into a retry."""


type _PlayerRuleEvent = (
    GrowthMarked
    | GrowthReset
    | ApproachRaised
    | TagAdded
    | TagRemoved
    | TagRewritten
    | MaximumStressIncreased
)


class StoryRules:
    def resolve(
        self,
        direction: StoryDirection,
        state: GameState,
        rng: Random,
    ) -> list[Event]:
        return self._fold(state, direction.mechanics, rng)

    def _fold(
        self,
        state: GameState,
        mechanics: Sequence[StoryConsequence],
        rng: Random,
    ) -> list[Event]:
        emitted: list[Event] = []
        provisional = state
        for consequence in mechanics:
            events = self._resolve_one(provisional, consequence, rng)
            emitted.extend(events)
            provisional = apply(provisional, events, self)
        return emitted

    def _resolve_one(
        self,
        state: GameState,
        consequence: StoryConsequence,
        rng: Random,
    ) -> list[Event]:
        if isinstance(consequence, CoreAction):
            if not is_core_action(consequence):
                raise TypeError(f"unsupported core action {type(consequence).__name__}")
            try:
                return resolve_core_action(consequence, state)
            except CoreActionRejected as error:
                raise StoryProposalRejected(str(error)) from error
        match consequence:
            case Risk():
                return self._risk(state, consequence, rng)
            case TakeStress():
                return self._take_stress(state, consequence)
            case RecoverStress():
                return self._recover_stress(state, consequence)
            case ApplyCondition():
                return self._apply_condition(state, consequence)
            case ClearCondition():
                return self._clear_condition(state, consequence)

    def _risk(self, state: GameState, risk: Risk, rng: Random) -> list[Event]:
        actor_id = PLAYER_ID if risk.actor_id is None else risk.actor_id
        actor, actor_state = self._actor(state, actor_id)
        if actor_state.taken_out:
            raise StoryProposalRejected(
                f"actor {actor.id!r} is taken out and cannot attempt a risk;"
                " recover_stress must bring them back below max_stress first"
            )
        helpful = self._helpful_modifier(state, actor_id, actor_state, risk)
        hindering = self._hindering_modifier(actor_state, risk)
        dice = (rng.randint(1, 6), rng.randint(1, 6))
        approach = actor_state.approaches.score(risk.approach)
        total = sum(dice) + approach + helpful + hindering - risk.difficulty
        outcome: StoryOutcome = "strong" if total >= 10 else "mixed" if total >= 7 else "setback"
        events: list[Event] = [
            encode_story_event(
                RiskRolled(
                    actor_id=actor.id,
                    actor_name=actor.name,
                    dice=dice,
                    approach=risk.approach,
                    approach_modifier=approach,
                    helpful_modifier=helpful,
                    hindering_modifier=hindering,
                    difficulty=risk.difficulty,
                    total=total,
                    outcome=outcome,
                ),
                ENGINE_ID,
                SCHEMA_VERSION,
            )
        ]
        if outcome == "setback" and actor.id == PLAYER_ID and actor_state.growth_marks < 3:
            events.append(
                encode_story_event(
                    GrowthMarked(
                        before=actor_state.growth_marks,
                        after=actor_state.growth_marks + 1,
                    ),
                    ENGINE_ID,
                    SCHEMA_VERSION,
                )
            )
        provisional = apply(state, events, self)
        branch = (
            risk.on_strong
            if outcome == "strong"
            else risk.on_mixed
            if outcome == "mixed"
            else risk.on_setback
        )
        return [*events, *self._fold(provisional, branch, rng)]

    def _helpful_modifier(
        self,
        state: GameState,
        actor_id: EntityId,
        actor: StoryActorState,
        risk: Risk,
    ) -> int:
        match risk.helpful:
            case None:
                return 0
            case HelpfulActorTag(id=tag_id):
                tag = next((tag for tag in actor.tags if tag.id == tag_id), None)
                if tag is None or tag.kind not in ("edge", "bond"):
                    raise StoryProposalRejected(
                        f"helpful tag {tag_id!r} is not an active edge or bond on {actor_id!r}"
                    )
                return 1
            case HelpfulGear(item_id=item_id):
                item = state.world.require_kind(item_id, ItemEntity)
                if item.container_id != actor_id:
                    raise StoryProposalRejected(
                        f"gear item {item_id!r} is not carried by {actor_id!r}"
                    )
                if story_state(state).item(item_id).gear is None:
                    raise StoryProposalRejected(f"item {item_id!r} has no Story gear benefit")
                return 1

    @staticmethod
    def _hindering_modifier(actor: StoryActorState, risk: Risk) -> int:
        match risk.hindering:
            case None:
                return 0
            case HinderingBurden(id=tag_id):
                tag = next((tag for tag in actor.tags if tag.id == tag_id), None)
                if tag is None or tag.kind != "burden":
                    raise StoryProposalRejected(f"hindering tag {tag_id!r} is not an active burden")
                return -1
            case HinderingCondition(id=condition_id):
                if not any(condition.id == condition_id for condition in actor.conditions):
                    raise StoryProposalRejected(
                        f"hindering condition {condition_id!r} is not active"
                    )
                return -1

    def _take_stress(self, state: GameState, action: TakeStress) -> list[Event]:
        actor, held = self._actor_for_action(state, action.actor_id)
        if held.stress == held.max_stress:
            return []
        after = min(held.max_stress, held.stress + action.amount)
        events: list[Event] = [
            encode_story_event(
                StressChanged(
                    actor_id=actor.id,
                    actor_name=actor.name,
                    before=held.stress,
                    after=after,
                    maximum=held.max_stress,
                ),
                ENGINE_ID,
                SCHEMA_VERSION,
            )
        ]
        if after == held.max_stress:
            events.append(
                encode_story_event(
                    TakenOut(actor_id=actor.id, actor_name=actor.name), ENGINE_ID, SCHEMA_VERSION
                )
            )
        return events

    def _recover_stress(self, state: GameState, action: RecoverStress) -> list[Event]:
        actor, held = self._actor_for_action(state, action.actor_id)
        if held.stress == 0:
            return []
        after = max(0, held.stress - action.amount)
        events: list[Event] = [
            encode_story_event(
                StressChanged(
                    actor_id=actor.id,
                    actor_name=actor.name,
                    before=held.stress,
                    after=after,
                    maximum=held.max_stress,
                ),
                ENGINE_ID,
                SCHEMA_VERSION,
            )
        ]
        if held.stress == held.max_stress and after < held.max_stress:
            events.append(
                encode_story_event(
                    Revived(actor_id=actor.id, actor_name=actor.name), ENGINE_ID, SCHEMA_VERSION
                )
            )
        return events

    def _apply_condition(self, state: GameState, action: ApplyCondition) -> list[Event]:
        actor, held = self._actor_for_action(state, action.actor_id)
        if any(condition.id == action.condition.id for condition in held.conditions):
            return []
        return [
            encode_story_event(
                ConditionApplied(
                    actor_id=actor.id,
                    actor_name=actor.name,
                    condition=action.condition,
                ),
                ENGINE_ID,
                SCHEMA_VERSION,
            )
        ]

    def _clear_condition(self, state: GameState, action: ClearCondition) -> list[Event]:
        actor, held = self._actor_for_action(state, action.actor_id)
        condition = next(
            (condition for condition in held.conditions if condition.id == action.condition_id),
            None,
        )
        if condition is None:
            return []
        return [
            encode_story_event(
                ConditionCleared(
                    actor_id=actor.id,
                    actor_name=actor.name,
                    condition=condition,
                ),
                ENGINE_ID,
                SCHEMA_VERSION,
            )
        ]

    @staticmethod
    def created(state: GameState, entity: Entity) -> StoryState:
        return created_state(state, entity)

    def apply(self, state: GameState, event: RuleEvent) -> StoryState:
        typed = decode_story_event(event, ENGINE_ID, SCHEMA_VERSION)
        match typed:
            case RiskRolled() | TakenOut() | Revived():
                return story_state(state)
            case GearAcquired(item_id=item_id, gear=gear):
                state.world.require_kind(item_id, ItemEntity)
                return story_state(state).with_item(item_id, StoryItemState(gear=gear))
            case StressChanged():
                actor, held = self._actor(state, typed.actor_id)
                if (held.stress, held.max_stress) != (typed.before, typed.maximum):
                    raise ValueError("stress event does not match current actor state")
                return self._with_actor(state, actor.id, updated(held, stress=typed.after))
            case ConditionApplied():
                actor, held = self._actor(state, typed.actor_id)
                changed = updated(held, conditions=(*held.conditions, typed.condition))
                return self._with_actor(state, actor.id, changed)
            case ConditionCleared():
                actor, held = self._actor(state, typed.actor_id)
                if typed.condition not in held.conditions:
                    raise ValueError("cleared condition is not active")
                changed = updated(
                    held,
                    conditions=tuple(
                        condition
                        for condition in held.conditions
                        if condition.id != typed.condition.id
                    ),
                )
                return self._with_actor(state, actor.id, changed)
            case _:
                return self._apply_player_event(state, typed)

    def _apply_player_event(self, state: GameState, typed: _PlayerRuleEvent) -> StoryState:
        player_state = story_state(state).actor(PLAYER_ID)
        match typed:
            case GrowthMarked():
                if player_state.growth_marks != typed.before or typed.after != typed.before + 1:
                    raise ValueError("growth event does not match current player growth")
                return self._with_actor(
                    state, PLAYER_ID, updated(player_state, growth_marks=typed.after)
                )
            case GrowthReset():
                if player_state.growth_marks != 3:
                    raise ValueError("growth can reset only from three")
                return self._with_actor(state, PLAYER_ID, updated(player_state, growth_marks=0))
            case ApproachRaised():
                before = player_state.approaches.score(typed.approach)
                if before != typed.before or typed.after != before + 1:
                    raise ValueError("approach event does not match current approach")
                approaches = updated(player_state.approaches, **{typed.approach: typed.after})
                return self._with_actor(
                    state, PLAYER_ID, updated(player_state, approaches=approaches)
                )
            case TagAdded():
                return self._with_actor(
                    state, PLAYER_ID, updated(player_state, tags=(*player_state.tags, typed.tag))
                )
            case TagRemoved():
                if typed.tag not in player_state.tags:
                    raise ValueError("removed Story tag is not active")
                return self._with_actor(
                    state,
                    PLAYER_ID,
                    updated(
                        player_state,
                        tags=tuple(tag for tag in player_state.tags if tag.id != typed.tag.id),
                    ),
                )
            case TagRewritten():
                if typed.before not in player_state.tags:
                    raise ValueError("rewritten Story tag is not active")
                return self._with_actor(
                    state,
                    PLAYER_ID,
                    updated(
                        player_state,
                        tags=tuple(
                            typed.after if tag.id == typed.before.id else tag
                            for tag in player_state.tags
                        ),
                    ),
                )
            case MaximumStressIncreased():
                if player_state.max_stress != typed.before or typed.after != typed.before + 1:
                    raise ValueError("maximum stress event does not match current maximum")
                return self._with_actor(
                    state, PLAYER_ID, updated(player_state, max_stress=typed.after)
                )

    def validate_state(self, state: GameState) -> None:
        story_state(state)

    @staticmethod
    def _with_actor(state: GameState, actor_id: EntityId, actor: StoryActorState) -> StoryState:
        return story_state(state).with_actor(actor_id, actor)

    def _actor_for_action(
        self,
        state: GameState,
        actor_id: EntityId | None,
    ) -> tuple[ActorEntity, StoryActorState]:
        return self._actor(state, PLAYER_ID if actor_id is None else actor_id)

    def _actor(
        self,
        state: GameState,
        actor_id: EntityId,
    ) -> tuple[ActorEntity, StoryActorState]:
        actor = state.world.require_kind(actor_id, ActorEntity)
        return actor, story_state(state).actor(actor_id)
