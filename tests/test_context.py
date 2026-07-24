"""The context policy is the experiment: each role must see only what its job needs."""

import pytest

from aidm.agents.context import TurnContext
from aidm.agents.policy import prompt_for
from aidm.domain.models import ROLES, Direction, EntityId, GameState, GrowthRequest

DIRECTION = Direction(intent="Kael searches the study for anything hidden.", tone="hushed")
REQUEST = GrowthRequest(kind="npc", name="Elgin", brief="An apothecary.")


def context(state: GameState) -> TurnContext:
    return TurnContext(state=state, prompt="I search the study.", narration="You find nothing.")


def test_unrevealed_canon_never_reaches_the_narrator(state: GameState) -> None:
    """The Narrator alone writes what the player reads, so it is the one role kept in the dark."""
    for role in ROLES:
        shown = "An archivist." in prompt_for(
            role, context(state), direction=DIRECTION, request=REQUEST
        )
        assert shown == (role != "narrator"), f"{role}: wrong canon"


def test_known_entities_carry_their_ids_for_the_director(state: GameState) -> None:
    """The bug: the Director could not name a known entity because its id was hidden from it."""
    director = prompt_for("director", context(state), direction=DIRECTION)
    assert "the vault map[id=vault_map]" in director
    assert "Mara[id=mara]" in director


def test_narrator_reads_the_plan_before_the_outcome(state: GameState) -> None:
    """The intent gives the Narrator context; the events read last, because they overrule it."""
    narrator = prompt_for("narrator", context(state), direction=DIRECTION)
    assert DIRECTION.tone in narrator
    assert narrator.index(DIRECTION.intent) < narrator.index("WHAT HAPPENED")


def test_a_known_speaker_is_rendered_by_id(state: GameState) -> None:
    direction = Direction(intent="i", tone="t", speaker_id=EntityId("mara"))
    narrator = prompt_for("narrator", context(state), direction=direction)
    assert "Mara[id=mara] — A scribe." in narrator


def test_a_hidden_speaker_fails_fast(state: GameState) -> None:
    direction = Direction(intent="i", tone="t", speaker_id=EntityId("elena"))
    with pytest.raises(ValueError, match="unknown or hidden speaker"):
        prompt_for("narrator", context(state), direction=direction)


def test_a_direction_block_without_a_direction_fails_fast(state: GameState) -> None:
    with pytest.raises(ValueError, match="without a direction"):
        prompt_for("narrator", context(state))
