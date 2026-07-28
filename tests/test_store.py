"""Composing a scenario-independent character sheet with the scenario that places it, the two things
a save is refused for, and the files both live in."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from support import library, new_game

from aidm.content import PackStamp
from aidm.domain.models import (
    PLAYER_ID,
    SAVE_VERSION,
    Advancement,
    Attributes,
    CharacterSheet,
    Direction,
    GameState,
    Growth,
    Origin,
    Progression,
    ScenarioDef,
    Turn,
    updated,
)
from aidm.engine import campaign
from aidm.store import FileSaves, FileTraces

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


def test_a_save_survives_a_round_trip_and_an_unsaved_slug_is_not_an_error(tmp_path: Path) -> None:
    """`None` is how every first game starts, so a missing file is an answer rather than a fault."""
    saves = FileSaves(tmp_path)
    assert saves.load("nothing-here") is None
    state = new_game()
    saves.save("current", state)
    assert saves.load("current") == state
    saves.discard("current")
    assert saves.load("current") is None


def test_a_save_is_refused_when_the_schema_or_the_content_under_it_moved() -> None:
    """An actor's stats were snapshotted from a pack version, so a bump would silently change the
    game the save recorded. There are no migrations: fail loudly instead."""
    state = new_game()
    stamps = library().stamps
    assert campaign.resumable(state, stamps) == state
    with pytest.raises(ValueError, match=f"needs v{SAVE_VERSION}"):
        campaign.resumable(updated(state, version=SAVE_VERSION - 1), stamps)
    stale = updated(state, packs=[PackStamp(id="srd-2014", version="0.0.0")])
    with pytest.raises(ValueError, match="was played against"):
        campaign.resumable(stale, stamps)


def _turn(state: GameState, prompt: str) -> Turn:
    return Turn(
        prompt=prompt,
        direction=Direction(intent="i", tone="t"),
        narration="n",
        growth=Growth(),
        state=state,
    )


def test_the_trace_is_one_line_per_turn_and_only_ever_appended(tmp_path: Path) -> None:
    """The trace panel is the point of the app, so a turn already written must never be rewritten by
    a later one."""
    traces = FileTraces(tmp_path)
    state = new_game()
    for prompt in ("I listen.", "I knock."):
        traces.append("poc", _turn(state, prompt))
    lines = (tmp_path / "poc.trace.jsonl").read_text(encoding="utf-8").splitlines()
    assert [Turn.model_validate_json(line).prompt for line in lines] == ["I listen.", "I knock."]
    traces.discard("poc")
    assert not (tmp_path / "poc.trace.jsonl").exists()
