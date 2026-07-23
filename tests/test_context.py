"""The context policy is the experiment: each role must see only what its job needs."""

import pytest

from aidm.agents.context import TurnContext, prompt_for
from aidm.domain.models import ROLES, Direction, GameState, GrowthRequest

DIRECTION = Direction(guidance="secret plan: wisdom DC 12", tone="tense and hushed")


def context(state: GameState) -> TurnContext:
    return TurnContext(
        state=state,
        prompt="I search the study.",
        direction=DIRECTION,
        narration="You find nothing.",
        request=GrowthRequest(kind="npc", name="Elgin", brief="An apothecary."),
    )


def test_unrevealed_canon_never_reaches_the_narrator(state: GameState) -> None:
    """The Narrator alone writes what the player reads, so it is the one role kept in the dark."""
    for role in ROLES:
        shown = "An archivist." in prompt_for(role, context(state))
        assert shown == (role != "narrator"), f"{role}: wrong canon"


def test_narrator_reads_the_plan_before_the_outcome(state: GameState) -> None:
    """The plan gives the Narrator intent; the events must read last, because they overrule it."""
    narrator = prompt_for("narrator", context(state))
    assert DIRECTION.tone in narrator
    assert narrator.index(DIRECTION.guidance) < narrator.index("WHAT HAPPENED")


def test_actor_can_name_what_it_must_reveal(state: GameState) -> None:
    """The Actor must resolve `discover_entity` against entities it was actually shown."""
    actor = prompt_for("actor", context(state))
    assert "the vault map" in actor and "Elena" in actor


def test_a_speaker_may_be_named_by_id_or_by_name(state: GameState) -> None:
    for speaker_id in ("mara", "Mara"):
        direction = Direction(guidance="g", tone="t", speaker_id=speaker_id)
        context = TurnContext(state=state, prompt="hi", direction=direction)
        assert "Mara — A scribe." in prompt_for("narrator", context)


def test_a_hidden_speaker_fails_fast(state: GameState) -> None:
    hidden_speaker = TurnContext(
        state=state, prompt="hi", direction=Direction(guidance="g", tone="t", speaker_id="elena")
    )
    with pytest.raises(ValueError, match="unknown or hidden speaker"):
        prompt_for("narrator", hidden_speaker)
