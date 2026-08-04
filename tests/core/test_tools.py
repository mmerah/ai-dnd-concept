from collections.abc import Callable

import pytest
from core_test_support import initialized, tool_context, turn_context, updated, with_entity
from pydantic_ai import ModelRetry, RunContext

from aidm.base import PLAYER_ID, EntityId
from aidm.facts import Fact
from aidm.tools import (
    DirectorNotes,
    TurnContext,
    director_notes,
    discover,
    drop_item,
    gain_improvised_item,
    give_item,
    move,
    take_item,
)
from aidm.world import GameState

BELL_TOWER = EntityId("bell_tower")
ELENA = EntityId("elena")
LANTERN = EntityId("lantern")
MARA = EntityId("mara")
STUDY = EntityId("study")
VAULT = EntityId("vault")
VAULT_MAP = EntityId("vault_map")


class Turn:
    """One turn's draft and the tools acting on it, as the Director's loop would."""

    def __init__(self, state: GameState | None = None) -> None:
        engine, opened = initialized()
        self.context: TurnContext = turn_context(engine, opened if state is None else state)
        self.run: RunContext[TurnContext] = tool_context(self.context)

    def call(self, tool: Callable[..., str], **arguments: object) -> list[Fact]:
        """Only the facts this call appended, so a test reads one action at a time."""
        before = len(self.context.facts)
        _ = tool(self.run, **arguments)
        return self.context.facts[before:]


def opened() -> GameState:
    return initialized()[1]


def relocated(entity_id: EntityId, location_id: EntityId) -> GameState:
    state = opened()
    return with_entity(state, updated(state.world.require(entity_id), parent_id=location_id))


def test_inventory_tools_gate_on_position_and_carrying() -> None:
    turn = Turn()
    took = turn.call(take_item, item_id=VAULT_MAP)[1]
    assert (took.data["entity_id"], took.data["to_id"]) == (VAULT_MAP, PLAYER_ID)
    (dropped,) = turn.call(drop_item, item_id=LANTERN)
    assert (dropped.data["entity_id"], dropped.data["to_kind"]) == (LANTERN, "location")
    (given,) = turn.call(give_item, item_id=VAULT_MAP, actor_id=MARA)
    assert (given.data["entity_id"], given.data["to_id"]) == (VAULT_MAP, MARA)

    with pytest.raises(ModelRetry, match="not loose at the player's location"):
        _ = turn.call(take_item, item_id=VAULT_MAP)  # given away, not lying here
    with pytest.raises(ModelRetry, match="does not carry"):
        _ = turn.call(drop_item, item_id=VAULT_MAP)
    with pytest.raises(ModelRetry, match="already holds the item"):
        _ = turn.call(give_item, item_id=LANTERN, actor_id=PLAYER_ID)

    away = Turn(relocated(MARA, VAULT))
    with pytest.raises(ModelRetry, match="not here with the player"):
        _ = away.call(give_item, item_id=LANTERN, actor_id=MARA)


def test_move_reveals_only_what_the_player_witnesses() -> None:
    entered = Turn().call(move, location_id=VAULT)
    assert [fact.kind for fact in entered] == ["entity_discovered", "entity_moved"]

    left = Turn().call(move, location_id=VAULT, actor_id=MARA)
    assert [fact.kind for fact in left] == ["entity_moved"]
    arrived = Turn().call(move, location_id=STUDY, actor_id=ELENA)
    assert [fact.kind for fact in arrived] == ["entity_discovered", "entity_moved"]

    elsewhere = Turn()
    with pytest.raises(ModelRetry, match="would not be witnessed"):
        _ = elsewhere.call(move, location_id=VAULT, actor_id=ELENA)


def test_discovery_is_idempotent_and_an_improvised_item_is_promoted_to_canon() -> None:
    turn = Turn()
    assert turn.call(discover, entity_id=MARA) == []
    assert [f.kind for f in turn.call(discover, entity_id=VAULT_MAP)] == ["entity_discovered"]

    created, took = turn.call(gain_improvised_item, item_name="a rusty key")
    assert created.data["name"] == "a rusty key"
    assert took.data["entity_id"] == created.data["entity_id"]


def test_a_bad_reference_asks_the_model_to_retry() -> None:
    turn = Turn()
    with pytest.raises(ModelRetry, match="unknown entity id"):
        _ = turn.call(take_item, item_id=EntityId("ghost"))
    with pytest.raises(ModelRetry, match="is a actor, not a location"):
        _ = turn.call(move, location_id=MARA)
    assert turn.context.draft == opened()


def test_the_narrator_is_only_given_a_speaker_it_may_voice() -> None:
    """`speaker_id` reaches the Narrator, so the player, an unrevealed actor and an absent one
    must all be refused here."""
    turn = Turn()
    notes = DirectorNotes(intent="Mara answers.", tone="hushed", speaker_id=MARA)
    assert director_notes(turn.run, notes) == notes

    for refused in (PLAYER_ID, ELENA, BELL_TOWER, EntityId("ghost")):
        with pytest.raises(ModelRetry):
            _ = director_notes(turn.run, updated(notes, speaker_id=refused))
