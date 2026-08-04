from collections.abc import Sequence
from random import Random

from core_test_support import updated
from fivee_test_support import content_ref as ref
from fivee_test_support import player_of as player_of
from fivee_test_support import ruleset, sheet, with_actor

import aidm.engines.dnd5e.progression as progression
from aidm.engines.dnd5e.access import Dnd5eWorld
from aidm.engines.dnd5e.content.records.character import ProgressionChoice
from aidm.engines.dnd5e.state import Decisions, Dnd5eState, Origin

RULES = ruleset()
SHEET = sheet()


def answers(choices: Sequence[ProgressionChoice]) -> Decisions:
    return {
        choice.id: tuple(option.key for option in choice.options[: choice.choose])
        if choice.distinct
        else (choice.options[0].key,) * choice.choose
        for choice in choices
    }


def next_of(state: Dnd5eState) -> Decisions:
    return answers(progression.preview(player_of(state), RULES).choices)


def levelled(state: Dnd5eState, to: int) -> Dnd5eState:
    """Draft first: `advance` mutates, and callers compare against the state they passed in.
    Commit after every level so the next iteration's `next_of` reads the level it just reached —
    hydration is a fresh copy now, not the record's own object."""
    working = state.draft()
    current = player_of(working).progression
    assert current is not None
    for _ in range(current.level + 1, to + 1):
        world = Dnd5eWorld(state=working, rng=Random(1), ruleset=RULES)
        _ = progression.advance(world.player(), next_of(working), RULES, Random(1))
        working = world.commit()
    return working


def started(klass: str, state: Dnd5eState) -> Dnd5eState:
    origin = Origin(class_ref=ref("classes", klass))
    prepared = updated(SHEET, origin=origin, decisions={})
    decisions = answers(progression.pending(origin, 1, RULES))
    start = progression.first_level(updated(prepared, decisions=decisions), RULES)
    held = player_of(state)
    player = updated(
        held.state,
        progression=start.progression,
        stats=updated(held.stats, attributes=start.attributes),
    )
    return with_actor(state, held.entity, player)
