from collections.abc import Mapping
from random import Random
from types import MappingProxyType

from aidm.core.base import PLAYER_ID, Entity, Slug
from aidm.core.dice import roll
from aidm.core.effects import AdjustCounter, apply_effect, require_actor_here
from aidm.core.enginepack import EngineParts
from aidm.core.facts import Fact
from aidm.core.plan import TurnPlanBase, apply_branch, check_plan_base
from aidm.core.sheet import Sheet, sheet_of
from aidm.core.world import GameState

from .actions import OUTCOMES, Difficulty, Risk, StoryPlan

DICE = "2d6"
PENALTY: Mapping[Difficulty, int] = MappingProxyType({"risky": 0, "demanding": 1, "extreme": 2})
TARGET = 7
STRONG_FROM = 10
GROWTH_MARK = AdjustCounter(
    entity_id=PLAYER_ID, counter="growth", delta=1, reason="a setback earns growth"
)


def _story_plan(plan: TurnPlanBase) -> StoryPlan:
    if not isinstance(plan, StoryPlan):
        raise ValueError(f"the story engine cannot resolve a {type(plan).__name__}")
    return plan


def _helps(state: GameState[Sheet], actor: Entity, sheet: Sheet, tag_id: Slug) -> bool:
    if sheet.tag(tag_id) is not None:
        return True
    carried = state.world.children(actor.id, "item")
    return any(sheet_of(state, item.id).tag(tag_id) is not None for item in carried)


def _refused(state: GameState[Sheet], action: Risk) -> str | None:
    try:
        actor = require_actor_here(state, action.actor_id)
    except ValueError as unreadable:
        return str(unreadable)
    sheet = sheet_of(state, actor.id)
    stress = sheet.counters["stress"]
    if stress.current == stress.maximum:
        return (
            f"{actor.name} is TAKEN OUT: their stress is at its maximum, so they can risk nothing. "
            "Write what their collapse means into `intent` instead."
        )
    hindering = action.hindering_tag_id
    if hindering is not None and sheet.tag(hindering) is None:
        return f"{actor.name} carries no tag {hindering!r}, so nothing hinders them here"
    helping = action.helping_tag_id
    if helping is not None and not _helps(state, actor, sheet, helping):
        return (
            f"{actor.name} carries no tag {helping!r}, on their own sheet or on an item they hold, "
            "so nothing helps them here"
        )
    return None


def check_plan(parts: EngineParts, state: GameState[Sheet], plan: TurnPlanBase) -> str | None:
    story = _story_plan(plan)
    action = story.action
    if action is None:
        return check_plan_base(state, story, frozenset[Slug](), parts.default_rules)
    return _refused(state, action) or check_plan_base(state, story, OUTCOMES, parts.default_rules)


def resolve_action(
    parts: EngineParts, draft: GameState[Sheet], plan: TurnPlanBase, rng: Random
) -> list[Fact]:
    action = _story_plan(plan).action
    if action is None:
        return []
    actor = require_actor_here(draft, action.actor_id)
    sheet = sheet_of(draft, actor.id)
    bonus = (
        sheet.numbers[action.approach]
        + (1 if action.helping_tag_id is not None else 0)
        - (1 if action.hindering_tag_id is not None else 0)
        - PENALTY[action.difficulty]
    )
    rolled, fact = roll(DICE, action.stakes, rng, vs=TARGET, bonus=bonus)
    outcome = _outcome(rolled.total)
    facts = [*draft.reveal(actor), fact]
    if outcome == "setback" and actor.id == PLAYER_ID:
        facts.extend(apply_effect(draft, GROWTH_MARK, parts.default_rules))
    facts.extend(apply_branch(draft, plan, outcome, parts.default_rules))
    return facts


def _outcome(total: int) -> Slug:
    if total >= STRONG_FROM:
        return "strong"
    return "mixed" if total >= TARGET else "setback"
