from collections.abc import Sequence
from random import Random

from fivee_test_support import ruleset, sheet

import aidm_5e.engine.progression as progression
from aidm_5e.content.records.base import ContentRef
from aidm_5e.content.records.character import ProgressionChoice
from aidm_5e.domain.models.progression import Decisions, Origin
from aidm_5e.domain.models.state import GameState
from aidm_5e.domain.reducer import apply
from aidm_5e.utils.models import updated

RULES = ruleset()
SHEET = sheet()
SECOND_WIND = "srd-2014/features/second-wind"
ACTION_SURGE = "srd-2014/features/action-surge-1-use"


def ref(collection: str, index: str) -> ContentRef:
    return ContentRef.model_validate({"pack": "srd-2014", "collection": collection, "index": index})


def answers(choices: Sequence[ProgressionChoice]) -> Decisions:
    return {
        choice.id: tuple(option.key for option in choice.options[: choice.choose])
        if choice.distinct
        else (choice.options[0].key,) * choice.choose
        for choice in choices
    }


def next_of(state: GameState) -> Decisions:
    return answers(progression.preview(state.player, RULES).choices)


def levelled(state: GameState, to: int) -> GameState:
    current = state.player.progression
    assert current is not None
    for _ in range(current.level + 1, to + 1):
        state = apply(
            state,
            progression.advance(state.player, next_of(state), RULES, Random(1)),
        )
    return state


def started(klass: str, state: GameState) -> GameState:
    origin = Origin(class_ref=ref("classes", klass))
    prepared = updated(SHEET, origin=origin, decisions={})
    decisions = answers(progression.pending(origin, 1, RULES))
    start = progression.first_level(updated(prepared, decisions=decisions), RULES)
    player = updated(
        state.player,
        progression=start.progression,
        stats=updated(state.player.stats, attributes=start.attributes),
    )
    return updated(state, world=state.world.replacing(player))
