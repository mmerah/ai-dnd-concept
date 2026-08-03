from collections.abc import Sequence
from random import Random
from typing import Literal

from aidm.actions import WorldActionRejected, is_world_action, resolve_world_action
from aidm.base import PLAYER_ID, Entity, EntityId
from aidm.content import Rules
from aidm.facts import Fact
from aidm.transition import Direction, Transition
from aidm.world import GameState

from .access import StoryWorld
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
    TakeStress,
    load_mechanics,
)
from .identity import ENGINE_ID
from .state import GROWTH_REQUIRED, StoryActorState, StoryApproach, StoryCondition, StoryItemState

StoryOutcome = Literal["strong", "mixed", "setback"]


class StoryProposalRejected(ValueError):
    """A proposed direction the rules cannot resolve; the Director turns this into a retry."""


def _risk_rolled(
    actor: Entity,
    dice: tuple[int, int],
    approach: StoryApproach,
    approach_modifier: int,
    helpful_modifier: int,
    hindering_modifier: int,
    difficulty: int,
    total: int,
    outcome: StoryOutcome,
) -> Fact:
    modifiers = approach_modifier + helpful_modifier + hindering_modifier - difficulty
    trace = f"{actor.name} risk: {dice[0]}+{dice[1]} {modifiers:+d} = {total}: {outcome}"
    return Fact(
        source=ENGINE_ID,
        kind="risk_rolled",
        trace=trace,
        narrator=f"{actor.name}'s attempt ends in a {outcome}",
        data={
            "actor_id": actor.id,
            "actor_name": actor.name,
            "dice": list(dice),
            "approach": approach,
            "approach_modifier": approach_modifier,
            "helpful_modifier": helpful_modifier,
            "hindering_modifier": hindering_modifier,
            "difficulty": difficulty,
            "total": total,
            "outcome": outcome,
        },
    )


def _stress_changed(actor: Entity, before: int, after: int, maximum: int) -> Fact:
    narrator = (
        f"{actor.name} recovers some composure"
        if after < before
        else f"{actor.name} comes under more pressure"
    )
    return Fact(
        source=ENGINE_ID,
        kind="stress_changed",
        trace=f"{actor.name} stress {before}->{after}/{maximum}",
        narrator=narrator,
        data={
            "actor_id": actor.id,
            "actor_name": actor.name,
            "before": before,
            "after": after,
            "maximum": maximum,
        },
    )


def _taken_out(actor: Entity) -> Fact:
    trace = f"{actor.name} is taken out"
    return Fact(
        source=ENGINE_ID,
        kind="taken_out",
        trace=trace,
        narrator=trace,
        data={"actor_id": actor.id, "actor_name": actor.name},
    )


def revived(actor: Entity) -> Fact:
    trace = f"{actor.name} is no longer taken out"
    return Fact(
        source=ENGINE_ID,
        kind="revived",
        trace=trace,
        narrator=trace,
        data={"actor_id": actor.id, "actor_name": actor.name},
    )


def _condition_applied(actor: Entity, condition: StoryCondition) -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="condition_applied",
        trace=f"{actor.name} gains condition {condition.name}[id={condition.id}]",
        narrator=f"{actor.name} is now {condition.name}",
        data={
            "actor_id": actor.id,
            "actor_name": actor.name,
            "condition_id": condition.id,
            "condition_name": condition.name,
        },
    )


def _condition_cleared(actor: Entity, condition: StoryCondition) -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="condition_cleared",
        trace=f"{actor.name} loses condition {condition.name}[id={condition.id}]",
        narrator=f"{actor.name} is no longer {condition.name}",
        data={
            "actor_id": actor.id,
            "actor_name": actor.name,
            "condition_id": condition.id,
            "condition_name": condition.name,
        },
    )


def _growth_marked(before: int, after: int) -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="growth_marked",
        trace=f"growth {before}->{after}/{GROWTH_REQUIRED}",
        narrator=None,
        data={"before": before, "after": after, "required": GROWTH_REQUIRED},
    )


class StoryRules:
    def resolve(self, direction: Direction, state: GameState, rng: Random) -> Transition:
        mechanics = load_mechanics(direction)
        world = StoryWorld(state.draft())
        facts = self._fold(world, mechanics, rng)
        return Transition(state=world.commit(), facts=tuple(facts))

    def _fold(
        self,
        world: StoryWorld,
        mechanics: Sequence[StoryConsequence],
        rng: Random,
    ) -> list[Fact]:
        emitted: list[Fact] = []
        for consequence in mechanics:
            emitted.extend(self._resolve_one(world, consequence, rng))
        return emitted

    def _resolve_one(
        self,
        world: StoryWorld,
        consequence: StoryConsequence,
        rng: Random,
    ) -> list[Fact]:
        if is_world_action(consequence):
            try:
                return list(resolve_world_action(consequence, world.state, _improvised_item_rules))
            except WorldActionRejected as error:
                raise StoryProposalRejected(str(error)) from error
        match consequence:
            case Risk():
                return self._risk(world, consequence, rng)
            case TakeStress():
                return self._take_stress(world, consequence)
            case RecoverStress():
                return self._recover_stress(world, consequence)
            case ApplyCondition():
                return self._apply_condition(world, consequence)
            case ClearCondition():
                return self._clear_condition(world, consequence)
            case _:
                raise TypeError(f"unsupported Story consequence {type(consequence).__name__}")

    def _risk(self, world: StoryWorld, risk: Risk, rng: Random) -> list[Fact]:
        actor_id = PLAYER_ID if risk.actor_id is None else risk.actor_id
        actor, sheet = world.actor(actor_id)
        if sheet.taken_out:
            raise StoryProposalRejected(
                f"actor {actor.id!r} is taken out and cannot attempt a risk;"
                " recover_stress must bring them back below max_stress first"
            )
        helpful = self._helpful_modifier(world, actor_id, sheet, risk)
        hindering = self._hindering_modifier(sheet, risk)
        dice = (rng.randint(1, 6), rng.randint(1, 6))
        approach = sheet.approaches.score(risk.approach)
        total = sum(dice) + approach + helpful + hindering - risk.difficulty
        outcome: StoryOutcome = "strong" if total >= 10 else "mixed" if total >= 7 else "setback"
        emitted: list[Fact] = [
            _risk_rolled(
                actor,
                dice,
                risk.approach,
                approach,
                helpful,
                hindering,
                risk.difficulty,
                total,
                outcome,
            )
        ]
        if outcome == "setback" and actor.id == PLAYER_ID and sheet.growth_marks < GROWTH_REQUIRED:
            before = sheet.growth_marks
            sheet.growth_marks = before + 1
            emitted.append(_growth_marked(before, sheet.growth_marks))
        branch = (
            risk.on_strong
            if outcome == "strong"
            else risk.on_mixed
            if outcome == "mixed"
            else risk.on_setback
        )
        return [*emitted, *self._fold(world, branch, rng)]

    def _helpful_modifier(
        self,
        world: StoryWorld,
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
                item, profile = world.item(item_id)
                if item.parent_id != actor_id:
                    raise StoryProposalRejected(
                        f"gear item {item_id!r} is not carried by {actor_id!r}"
                    )
                if profile.gear is None:
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

    def _take_stress(self, world: StoryWorld, action: TakeStress) -> list[Fact]:
        actor, sheet = self._actor_for_action(world, action.actor_id)
        if sheet.stress == sheet.max_stress:
            return []
        before = sheet.stress
        sheet.stress = min(sheet.max_stress, before + action.amount)
        emitted: list[Fact] = [_stress_changed(actor, before, sheet.stress, sheet.max_stress)]
        if sheet.taken_out:
            emitted.append(_taken_out(actor))
        return emitted

    def _recover_stress(self, world: StoryWorld, action: RecoverStress) -> list[Fact]:
        actor, sheet = self._actor_for_action(world, action.actor_id)
        if sheet.stress == 0:
            return []
        before = sheet.stress
        sheet.stress = max(0, before - action.amount)
        emitted: list[Fact] = [_stress_changed(actor, before, sheet.stress, sheet.max_stress)]
        if before == sheet.max_stress and not sheet.taken_out:
            emitted.append(revived(actor))
        return emitted

    def _apply_condition(self, world: StoryWorld, action: ApplyCondition) -> list[Fact]:
        actor, sheet = self._actor_for_action(world, action.actor_id)
        if any(condition.id == action.condition.id for condition in sheet.conditions):
            return []
        sheet.conditions = (*sheet.conditions, action.condition)
        return [_condition_applied(actor, action.condition)]

    def _clear_condition(self, world: StoryWorld, action: ClearCondition) -> list[Fact]:
        actor, sheet = self._actor_for_action(world, action.actor_id)
        condition = next(
            (condition for condition in sheet.conditions if condition.id == action.condition_id),
            None,
        )
        if condition is None:
            return []
        sheet.conditions = tuple(item for item in sheet.conditions if item.id != condition.id)
        return [_condition_cleared(actor, condition)]

    @staticmethod
    def _actor_for_action(
        world: StoryWorld,
        actor_id: EntityId | None,
    ) -> tuple[Entity, StoryActorState]:
        return world.actor(PLAYER_ID if actor_id is None else actor_id)


def _improvised_item_rules() -> Rules:
    return StoryItemState().model_dump(mode="json")
