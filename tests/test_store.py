"""Composing a scenario-independent character sheet with the scenario that places it, and the two
things a save is refused for."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from aidm import store
from aidm.config import settings
from aidm.content import PackStamp
from aidm.domain.models import (
    PLAYER_ID,
    Advancement,
    Attributes,
    CharacterSheet,
    GameState,
    Origin,
    Progression,
    ScenarioDef,
    updated,
)

CLASS_REF = {"pack": "srd-2014", "collection": "classes", "index": "fighter"}
SHEET = {
    "name": "Kael",
    "brief": "A relic-hunter.",
    "origin": {"class_ref": CLASS_REF},
    "starting_items": [{"name": "a lantern", "brief": "A tin lantern."}],
}
# Level 1 is engine work; `from_scenario` only places what it is handed, which is what keeps
# `domain/` free of pack reads.
START = Advancement(
    progression=Progression(
        origin=Origin.model_validate({"class_ref": CLASS_REF}),
        level=1,
        prof_bonus=2,
        saving_throws=("strength", "constitution"),
        proficiencies=(),
        spell_slots={},
        decisions={},
    ),
    attributes=Attributes(),
    hp_gain=10,
)
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
    ids — so `_consistent_world` validates them like anyone else's. Hit points come from the
    handed-in level, never from the sheet: only a class knows a hit die."""
    definition = ScenarioDef.model_validate(
        {"meta": META, "starting_location_id": "study", "entities": [STUDY, MARA]}
    )
    state = GameState.from_scenario(definition, CharacterSheet.model_validate(SHEET), [], START)
    assert state.player.id == PLAYER_ID
    assert state.player.known and state.player.location_id == "study"
    assert [e.name for e in state.world.carried_by(PLAYER_ID)] == ["a lantern"]
    assert state.player.stats.max_hp == 10 and state.player.progression == START.progression


def test_a_save_played_against_other_content_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An actor's stats were snapshotted from a pack version, so a bump would silently change the
    game the save recorded. There are no migrations: fail loudly instead."""
    monkeypatch.setattr(settings(), "saves_dir", tmp_path)
    state = store.new_game("whispering_vault")
    store.save("current", state)
    assert store.load("current") == state

    store.save("stale", updated(state, packs=[PackStamp(id="srd-2014", version="0.0.0")]))
    with pytest.raises(ValueError, match="was played against"):
        store.load("stale")
