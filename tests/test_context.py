"""The context policy is the experiment: each role must see only what its job needs."""

import pytest

from aidm.agents import views
from aidm.agents.context import TurnContext
from aidm.agents.policy import prompt_for
from aidm.domain.models import ROLES, Direction, EntityId, GameState, GrowthRequest, updated

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


def test_a_carried_item_keeps_its_id_and_brief(state: GameState) -> None:
    """Regression: an item in an inventory must stay in context, not drop to a bare name — the
    Director needs its id to drop or give it, and its brief to reason about it."""
    assert "- a lantern[id=lantern] — A tin lantern." in views.character(state)


def test_an_item_in_an_npc_inventory_is_shown_with_its_holder(state: GameState) -> None:
    mara = updated(state.world.entities[EntityId("mara")], inventory=[EntityId("lantern")])
    handed = updated(
        state,
        character=updated(state.character, inventory=[]),
        world=updated(state.world, entities={**state.world.entities, EntityId("mara"): mara}),
    )
    assert "a lantern[id=lantern] — item — held by Mara" in views.here(handed)


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
