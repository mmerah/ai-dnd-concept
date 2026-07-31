from collections.abc import Sequence
from random import Random

from core_test_support import updated
from fivee_test_support import content_ref as ref
from fivee_test_support import player_of as player_of
from fivee_test_support import ruleset, sheet

import aidm_5e.engine.progression as progression
from aidm.domain.base import PLAYER_ID
from aidm.domain.state import GameState
from aidm_5e.content.records.character import ProgressionChoice
from aidm_5e.domain.models.progression import Decisions, Origin
from aidm_5e.state import dnd5e_state

RULES = ruleset()
SHEET = sheet()


def answers(choices: Sequence[ProgressionChoice]) -> Decisions:
    return {
        choice.id: tuple(option.key for option in choice.options[: choice.choose])
        if choice.distinct
        else (choice.options[0].key,) * choice.choose
        for choice in choices
    }


def next_of(state: GameState) -> Decisions:
    return answers(progression.preview(player_of(state), RULES).choices)


def levelled(state: GameState, to: int) -> GameState:
    """Draft first: `advance` mutates, and callers compare against the state they passed in."""
    working = state.draft()
    current = player_of(working).progression
    assert current is not None
    for _ in range(current.level + 1, to + 1):
        _ = progression.advance(player_of(working), next_of(working), RULES, Random(1))
    return working.committed()


def started(klass: str, state: GameState) -> GameState:
    origin = Origin(class_ref=ref("classes", klass))
    prepared = updated(SHEET, origin=origin, decisions={})
    decisions = answers(progression.pending(origin, 1, RULES))
    start = progression.first_level(updated(prepared, decisions=decisions), RULES)
    engine = dnd5e_state(state)
    held = engine.actor(PLAYER_ID)
    player = updated(
        held,
        progression=start.progression,
        stats=updated(held.stats, attributes=start.attributes),
    )
    return updated(state, engine=updated(engine, actors={**engine.actors, PLAYER_ID: player}))
