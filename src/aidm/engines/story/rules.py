from collections.abc import Sequence
from random import Random

from aidm.actions import WorldActionRejected, is_world_action, resolve_world_action
from aidm.base import PLAYER_ID, ActorEntity, Entity, EntityId, ItemEntity
from aidm.transition import Transition
from aidm.world import EntityRules, GameState

from .access import actor_of, item_of
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
from .facts import (
    ConditionApplied,
    ConditionCleared,
    Emitted,
    GrowthMarked,
    Revived,
    RiskRolled,
    StoryOutcome,
    StressChanged,
    TakenOut,
)
from .state import GROWTH_REQUIRED, StoryActorState, StoryItemState


class StoryProposalRejected(ValueError):
    """A proposed direction the rules cannot resolve; the Director turns this into a retry."""


class StoryRules:
    def resolve(self, direction: StoryDirection, state: GameState, rng: Random) -> Transition:
        draft = state.draft()
        facts = self._fold(draft, direction.mechanics, rng)
        return Transition(state=draft.committed(), facts=tuple(facts))

    def _fold(
        self,
        draft: GameState,
        mechanics: Sequence[StoryConsequence],
        rng: Random,
    ) -> list[Emitted]:
        emitted: list[Emitted] = []
        for consequence in mechanics:
            emitted.extend(self._resolve_one(draft, consequence, rng))
        return emitted

    def _resolve_one(
        self,
        draft: GameState,
        consequence: StoryConsequence,
        rng: Random,
    ) -> list[Emitted]:
        if is_world_action(consequence):
            try:
                return list(resolve_world_action(consequence, draft, _default_rules))
            except WorldActionRejected as error:
                raise StoryProposalRejected(str(error)) from error
        match consequence:
            case Risk():
                return self._risk(draft, consequence, rng)
            case TakeStress():
                return self._take_stress(draft, consequence)
            case RecoverStress():
                return self._recover_stress(draft, consequence)
            case ApplyCondition():
                return self._apply_condition(draft, consequence)
            case ClearCondition():
                return self._clear_condition(draft, consequence)
            case _:
                raise TypeError(f"unsupported Story consequence {type(consequence).__name__}")

    def _risk(self, draft: GameState, risk: Risk, rng: Random) -> list[Emitted]:
        actor_id = PLAYER_ID if risk.actor_id is None else risk.actor_id
        actor, held = actor_of(draft, actor_id)
        if held.taken_out:
            raise StoryProposalRejected(
                f"actor {actor.id!r} is taken out and cannot attempt a risk;"
                " recover_stress must bring them back below max_stress first"
            )
        helpful = self._helpful_modifier(draft, actor_id, held, risk)
        hindering = self._hindering_modifier(held, risk)
        dice = (rng.randint(1, 6), rng.randint(1, 6))
        approach = held.approaches.score(risk.approach)
        total = sum(dice) + approach + helpful + hindering - risk.difficulty
        outcome: StoryOutcome = "strong" if total >= 10 else "mixed" if total >= 7 else "setback"
        emitted: list[Emitted] = [
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
            )
        ]
        if outcome == "setback" and actor.id == PLAYER_ID and held.growth_marks < GROWTH_REQUIRED:
            before = held.growth_marks
            held.growth_marks = before + 1
            emitted.append(GrowthMarked(before=before, after=held.growth_marks))
        branch = (
            risk.on_strong
            if outcome == "strong"
            else risk.on_mixed
            if outcome == "mixed"
            else risk.on_setback
        )
        return [*emitted, *self._fold(draft, branch, rng)]

    def _helpful_modifier(
        self,
        draft: GameState,
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
                item, held = item_of(draft, item_id)
                if item.container_id != actor_id:
                    raise StoryProposalRejected(
                        f"gear item {item_id!r} is not carried by {actor_id!r}"
                    )
                if held.gear is None:
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

    def _take_stress(self, draft: GameState, action: TakeStress) -> list[Emitted]:
        actor, held = self._actor_for_action(draft, action.actor_id)
        if held.stress == held.max_stress:
            return []
        before = held.stress
        held.stress = min(held.max_stress, before + action.amount)
        emitted: list[Emitted] = [
            StressChanged(
                actor_id=actor.id,
                actor_name=actor.name,
                before=before,
                after=held.stress,
                maximum=held.max_stress,
            )
        ]
        if held.taken_out:
            emitted.append(TakenOut(actor_id=actor.id, actor_name=actor.name))
        return emitted

    def _recover_stress(self, draft: GameState, action: RecoverStress) -> list[Emitted]:
        actor, held = self._actor_for_action(draft, action.actor_id)
        if held.stress == 0:
            return []
        before = held.stress
        held.stress = max(0, before - action.amount)
        emitted: list[Emitted] = [
            StressChanged(
                actor_id=actor.id,
                actor_name=actor.name,
                before=before,
                after=held.stress,
                maximum=held.max_stress,
            )
        ]
        if before == held.max_stress and not held.taken_out:
            emitted.append(Revived(actor_id=actor.id, actor_name=actor.name))
        return emitted

    def _apply_condition(self, draft: GameState, action: ApplyCondition) -> list[Emitted]:
        actor, held = self._actor_for_action(draft, action.actor_id)
        if any(condition.id == action.condition.id for condition in held.conditions):
            return []
        held.conditions = (*held.conditions, action.condition)
        return [
            ConditionApplied(
                actor_id=actor.id,
                actor_name=actor.name,
                condition=action.condition,
            )
        ]

    def _clear_condition(self, draft: GameState, action: ClearCondition) -> list[Emitted]:
        actor, held = self._actor_for_action(draft, action.actor_id)
        condition = next(
            (condition for condition in held.conditions if condition.id == action.condition_id),
            None,
        )
        if condition is None:
            return []
        held.conditions = tuple(item for item in held.conditions if item.id != condition.id)
        return [
            ConditionCleared(
                actor_id=actor.id,
                actor_name=actor.name,
                condition=condition,
            )
        ]

    @staticmethod
    def _actor_for_action(
        draft: GameState,
        actor_id: EntityId | None,
    ) -> tuple[ActorEntity, StoryActorState]:
        return actor_of(draft, PLAYER_ID if actor_id is None else actor_id)


def _default_rules(entity: Entity) -> EntityRules | None:
    return StoryItemState() if isinstance(entity, ItemEntity) else None
