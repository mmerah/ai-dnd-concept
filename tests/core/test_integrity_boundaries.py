import json
from pathlib import Path

import pytest
from core_test_support import (
    ENGINES_BUILT,
    LONER3E,
    SCENARIO_MODELS,
    SCENARIOS,
    begin_game,
    character,
    initialized,
    loner_sheet,
    scenario,
    updated,
)
from pydantic import ValidationError

from aidm.core.entities import EngineId, EntityId, Refusal
from aidm.core.io import read_character, read_scenario
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.world import LUCK_MAX, Loner3eGame, Loner3eWorld

MARA = EntityId("mara")
OTHER = EngineId("ruleless")


def test_a_doubled_id_in_a_world_file_is_refused(tmp_path: Path) -> None:
    world = (SCENARIOS / "whispering-vault" / "world.json").read_text(encoding="utf-8")
    doubled = world.replace('"mara": {', '"mara": {}, "mara": {', 1)
    (tmp_path / "doubled").mkdir()
    _ = (tmp_path / "doubled" / "world.json").write_text(doubled, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate keys"):
        _ = read_scenario(tmp_path, "doubled", SCENARIO_MODELS)


def test_a_doubled_key_in_a_save_is_refused() -> None:
    engine, state = initialized()
    doubled = state.model_dump_json().replace('{"scenario_id"', '{"turn": 0, "scenario_id"', 1)
    with pytest.raises(ValueError, match="duplicate keys"):
        _ = engine.restore(doubled)


def test_a_doubled_key_in_a_character_file_is_refused(tmp_path: Path) -> None:
    written = character()
    folder = tmp_path / written.id
    folder.mkdir()
    doubled = written.model_dump_json().replace('{"id"', '{"name": "Other", "id"', 1)
    _ = (folder / f"{written.engine}.json").write_text(doubled, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate keys"):
        _ = read_character(tmp_path, written.id, written.engine, ENGINES_BUILT[LONER3E].character)


def test_the_scene_world_rejects_state_it_cannot_stand_on() -> None:
    _, state = initialized()
    world = state.payload

    with pytest.raises(ValidationError, match="filed under"):
        _ = updated(world, cast={"someone-else": world.player.model_dump(round_trip=True)})

    with pytest.raises(ValidationError, match="unknown to themselves"):
        _ = updated(world, player=world.player.model_copy(update={"known": False}))

    with pytest.raises(ValidationError, match="scene names"):
        _ = _with_run(world, here=["ghost"])


def _with_run(world: Loner3eWorld, **changes: object) -> Loner3eWorld:
    return updated(world, runs=[world.run.model_dump(round_trip=True) | changes])


def test_the_party_rules_refuse_the_dead_and_the_doubled() -> None:
    _, state = initialized()
    dead = state.draft()
    dead.payload.require(MARA).alive = False
    dead.payload.party.append(MARA)
    with pytest.raises(ValueError, match="cannot travel with the player"):
        _ = dead.commit()

    twice = state.draft()
    twice.payload.party.extend((MARA, MARA))
    with pytest.raises(ValueError, match="duplicate party"):
        _ = twice.commit()


def test_a_committed_game_refuses_a_player_who_travels_with_themselves() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.payload.party.append(draft.payload.player.id)
    with pytest.raises(ValueError, match="cannot travel with themselves"):
        _ = draft.commit()


def test_entity_and_scene_ids_use_one_grammar() -> None:
    _, state = initialized()
    with pytest.raises(ValidationError, match="pattern"):
        _ = updated(state.payload.require(MARA), id="bell_tower")
    with pytest.raises(ValidationError, match="pattern"):
        _ = updated(state.payload.run, here=["study_1"])


def test_a_game_is_refused_a_scenario_or_a_character_from_another_engine() -> None:
    engine = ENGINES_BUILT[LONER3E]
    with pytest.raises(ValueError, match="authored for the 'ruleless' rules"):
        _ = begin_game(engine, "whispering-vault", updated(scenario(), engine=OTHER), character())
    with pytest.raises(ValueError, match="written for the 'ruleless' rules"):
        _ = begin_game(engine, "whispering-vault", scenario(), updated(character(), engine=OTHER))


def test_a_character_file_belongs_to_its_folder_and_its_engine(tmp_path: Path) -> None:
    written = character().model_dump_json()
    foreign = json.dumps(json.loads(written) | {"engine": OTHER})
    (tmp_path / "kael").mkdir()
    _ = (tmp_path / "kael" / f"{LONER3E}.json").write_text(foreign, encoding="utf-8")
    (tmp_path / "mira").mkdir()
    _ = (tmp_path / "mira" / f"{LONER3E}.json").write_text(written, encoding="utf-8")

    with pytest.raises(ValueError, match="plays 'ruleless', not 'loner3e'"):
        _ = read_character(
            tmp_path, "kael", ENGINES_BUILT[LONER3E].id, ENGINES_BUILT[LONER3E].character
        )
    with pytest.raises(ValueError, match="'kael' is filed under 'mira'"):
        _ = read_character(
            tmp_path, "mira", ENGINES_BUILT[LONER3E].id, ENGINES_BUILT[LONER3E].character
        )


def _luck(state: Loner3eGame) -> int:
    return loner_sheet(state, PLAYER_ID).luck.current


def test_a_rules_mutation_lands_on_the_commit_and_nowhere_else() -> None:
    _, state = initialized()
    draft = state.draft()
    loner_sheet(draft, PLAYER_ID).luck.current = 1

    committed = draft.commit()

    assert _luck(committed) == 1
    assert _luck(state) == LUCK_MAX


def test_a_save_whose_payload_the_engine_rejects_is_refused() -> None:
    engine, state = initialized()
    raw = state.model_dump(mode="json")
    raw["payload"]["cast"]["ghost"] = {"name": "Ghost"}
    with pytest.raises(Refusal):
        _ = engine.restore(json.dumps(raw))


def test_a_save_from_other_rules_is_refused_before_it_is_read() -> None:
    engine, state = initialized()
    foreign = json.dumps(state.model_dump(mode="json") | {"engine": OTHER})
    with pytest.raises(ValueError, match="the save plays 'ruleless', not 'loner3e'"):
        _ = engine.restore(foreign)
