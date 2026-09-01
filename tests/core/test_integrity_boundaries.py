import json
from pathlib import Path
from random import Random

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

from aidm.core.entities import EngineId, EntityId
from aidm.core.facts import Fact
from aidm.core.io import load_character, read_scenario
from aidm.core.tools import apply_to_draft
from aidm.engines.core import PLAYER_ID
from aidm.engines.loner3e.world import LUCK_MAX, Loner3eGame, LonerWorld

MARA = EntityId("mara")
ELENA = EntityId("elena")
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
        _ = engine.restored(doubled)


def test_a_doubled_key_in_a_character_file_is_refused(tmp_path: Path) -> None:
    written = character()
    folder = tmp_path / written.id
    folder.mkdir()
    doubled = written.model_dump_json().replace('{"id"', '{"name": "Other", "id"', 1)
    _ = (folder / f"{written.engine}.json").write_text(doubled, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate keys"):
        _ = load_character(tmp_path, written.id, written.engine, ENGINES_BUILT[LONER3E].character)


def test_the_scene_world_rejects_state_it_cannot_stand_on() -> None:
    _, state = initialized()
    world = state.payload.world

    with pytest.raises(ValidationError, match="filed under"):
        _ = updated(world, cast={"someone-else": world.player.model_dump(round_trip=True)})

    with pytest.raises(ValidationError, match="the player is not in the cast"):
        _ = updated(world, player_id="nobody")

    with pytest.raises(ValidationError, match="scene names"):
        _ = _with_run(world, present=["ghost"])

    with pytest.raises(ValidationError, match="already met"):
        _ = _with_run(world, present=[PLAYER_ID], hidden=[MARA])


def _with_run(world: LonerWorld, **changes: object) -> LonerWorld:
    return updated(world, runs=[world.run.model_dump(round_trip=True) | changes])


def test_the_party_rules_refuse_the_dead_and_the_doubled() -> None:
    _, state = initialized()
    dead = state.draft()
    dead.payload.world.require(MARA).alive = False
    dead.payload.world.companions.append(MARA)
    with pytest.raises(ValueError, match="cannot travel with the player"):
        _ = dead.committed()

    twice = state.draft()
    twice.payload.world.companions.extend((MARA, MARA))
    with pytest.raises(ValueError, match="duplicate companions"):
        _ = twice.committed()


def test_a_committed_game_refuses_a_player_who_travels_with_themselves() -> None:
    """The played id is state, not world canon, so the party rule is checked at the commit."""
    _, state = initialized()
    draft = state.draft()
    draft.payload.world.companions.append(draft.payload.world.player_id)
    with pytest.raises(ValueError, match="cannot travel with themselves"):
        _ = draft.committed()


def test_entity_and_scene_ids_use_one_grammar() -> None:
    _, state = initialized()
    with pytest.raises(ValidationError, match="pattern"):
        _ = updated(state.payload.world.require(MARA), id="bell_tower")
    with pytest.raises(ValidationError, match="pattern"):
        _ = updated(state.payload.world.run, present=["study_1"])


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
        _ = load_character(
            tmp_path, "kael", ENGINES_BUILT[LONER3E].id, ENGINES_BUILT[LONER3E].character
        )
    with pytest.raises(ValueError, match="'kael' is filed under 'mira'"):
        _ = load_character(
            tmp_path, "mira", ENGINES_BUILT[LONER3E].id, ENGINES_BUILT[LONER3E].character
        )


def _luck(state: Loner3eGame) -> int:
    return loner_sheet(state, PLAYER_ID).luck.current


def test_a_rules_mutation_lands_on_the_commit_and_nowhere_else() -> None:
    _, state = initialized()
    draft = state.draft()
    loner_sheet(draft, PLAYER_ID).luck.current = 1

    committed = draft.committed()

    assert _luck(committed) == 1
    assert _luck(state) == LUCK_MAX


def test_a_told_fact_about_an_unmet_or_unknown_entity_is_refused() -> None:
    engine, state = initialized()
    leak = Fact(kind="entity_moved", trace="Elena moved", told=True, entity_id=ELENA)

    with pytest.raises(ValueError, match="has not met"):
        _ = apply_to_draft(
            engine.validate,
            engine.known,
            state.draft(),
            lambda _draft, _rng: (leak,),
            Random(0),
        )

    nobody = Fact(
        kind="entity_moved", trace="a ghost moved", told=True, entity_id=EntityId("ghost")
    )

    with pytest.raises(ValueError, match="does not hold"):
        _ = apply_to_draft(
            engine.validate,
            engine.known,
            state.draft(),
            lambda _draft, _rng: (nobody,),
            Random(0),
        )


def test_a_save_whose_payload_the_engine_rejects_is_refused() -> None:
    engine, state = initialized()
    raw = state.model_dump(mode="json")
    raw["payload"]["world"]["cast"]["ghost"] = {"name": "Ghost"}
    with pytest.raises(ValidationError):
        _ = engine.restored(json.dumps(raw))


def test_a_save_from_other_rules_is_refused_before_it_is_read() -> None:
    engine, state = initialized()
    foreign = json.dumps(state.model_dump(mode="json") | {"engine": OTHER})
    with pytest.raises(ValueError, match="the save plays 'ruleless', not 'loner3e'"):
        _ = engine.restored(foreign)
