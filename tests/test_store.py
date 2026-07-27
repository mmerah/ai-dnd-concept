"""Composing a scenario-independent character sheet with the scenario that places it."""

import pytest
from pydantic import ValidationError

from aidm.domain.models import PLAYER_ID, CharacterSheet, GameState, ScenarioDef

SHEET = {
    "name": "Kael",
    "brief": "A relic-hunter.",
    "starting_items": [{"name": "a lantern", "brief": "A tin lantern."}],
}
STUDY = {"id": "study", "kind": "location", "name": "the study", "brief": "A room.", "known": True}
MARA = {"id": "mara", "kind": "actor", "name": "Mara", "brief": "A scribe.", "location_id": "study"}
META = {"title": "T", "premise": "P"}


def test_a_sheet_cannot_carry_a_location() -> None:
    """The starting position is the scenario's to give: a sheet knows no scenario's entity ids."""
    with pytest.raises(ValidationError):
        CharacterSheet.model_validate(SHEET | {"location_id": "study"})


def test_a_starting_location_must_be_one_of_the_scenario_s_own_locations() -> None:
    for start in ("nowhere", "mara"):  # absent, then present but not a location
        with pytest.raises(ValidationError):
            ScenarioDef.model_validate(
                {"meta": META, "starting_location_id": start, "entities": [STUDY, MARA]}
            )


def test_a_valid_starting_location_resolves() -> None:
    definition = ScenarioDef.model_validate(
        {"meta": META, "starting_location_id": "study", "entities": [STUDY, MARA]}
    )
    assert definition.starting_location_id == "study"


def test_a_scenario_may_not_ship_the_player() -> None:
    """The player is an actor entity now, which makes shipping one look reasonable. A scenario must
    place whatever character arrives, so the sheet alone mints the reserved id."""
    with pytest.raises(ValidationError, match="reserved player id"):
        ScenarioDef.model_validate(
            {
                "meta": META,
                "starting_location_id": "study",
                "entities": [STUDY, MARA | {"id": PLAYER_ID}],
            }
        )


def test_a_sheet_becomes_the_player_entity() -> None:
    """Composition puts the player in `world.entities` under the reserved id, holding real item
    ids — so `_consistent_world` validates them like anyone else's."""
    definition = ScenarioDef.model_validate(
        {"meta": META, "starting_location_id": "study", "entities": [STUDY, MARA]}
    )
    state = GameState.from_scenario(definition, CharacterSheet.model_validate(SHEET))
    assert state.player.id == PLAYER_ID
    assert state.player.known and state.player.location_id == "study"
    assert [state.world.entities[i].name for i in state.player.inventory] == ["a lantern"]
