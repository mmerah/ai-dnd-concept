import json
from pathlib import Path

import pytest
from support.fifth import FifthEngine, FifthGame, FifthState, engine_at, installed
from support.sixth import SixthEngine
from support.table import ENGINE_IDS, game, updated

from aidm.core.entities import EngineId, Refusal
from aidm.core.io import ENCODING


def test_the_tempo_floor_refuses_a_tempo_below_two(tmp_path: Path) -> None:
    class Impatient(FifthState):
        tempo = 1

    class TooFast(type(installed(tmp_path))):
        world = Impatient

    with pytest.raises(ValueError, match="ticks every"):
        TooFast(tmp_path / "written")


def test_the_clock_arms_on_reaching_the_tempo_and_starts_over(
    scene_engine: FifthEngine, begun_scene: FifthGame
) -> None:
    draft = begun_scene.draft()

    for _ in range(FifthState.tempo - 1):
        scene_engine.tick(draft, counted=True)
    assert (draft.payload.turns_played, draft.payload.meanwhile_due) == (
        FifthState.tempo - 1,
        False,
    )

    scene_engine.tick(draft, counted=True)

    assert (draft.payload.turns_played, draft.payload.meanwhile_due) == (0, True)


def test_construction_refuses_when_no_srd_table_set_is_installed(tmp_path: Path) -> None:
    engine_type = type(installed(tmp_path))
    (tmp_path / "packs" / "srd.json").rename(tmp_path / "packs" / "other.json")
    with pytest.raises(ValueError, match="ships no 'srd' pack"):
        engine_type(tmp_path / "written")


def test_a_pack_with_doubled_keys_is_refused(tmp_path: Path) -> None:
    (tmp_path / "rules.md").write_text("Roll high.", encoding=ENCODING)
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "srd.json").write_text(
        '{"name": "The SRD", "name": "Twice"}', encoding=ENCODING
    )
    with pytest.raises(Refusal, match="duplicate keys"):
        engine_at(tmp_path)(tmp_path / "written")


def test_a_fifth_scene_engine_begins_a_playable_game(
    scene_engine: FifthEngine, begun_scene: FifthGame
) -> None:
    assert scene_engine.supplement_options() == ()
    assert scene_engine.narrator_view(begun_scene).title == "The Taproom"
    assert scene_engine.master_sections(begun_scene) == (("SCENE", "The Taproom"),)
    assert [row.label for row in scene_engine.player_view(begun_scene).panels[-2].rows] == [
        "Keeper"
    ]


def test_a_game_with_no_chapter_open_is_refused(
    scene_engine: FifthEngine, begun_scene: FifthGame
) -> None:
    begun_scene.log.clear()

    with pytest.raises(Refusal, match="no chapter open"):
        scene_engine.validate(begun_scene)


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_validate_refuses_a_game_that_does_not_play_the_srd(engine_id: EngineId) -> None:
    engine, state = game(engine_id)

    with pytest.raises(Refusal, match="plays the 'srd' tables"):
        engine.validate(updated(state, packs=()))


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_restored_round_trips(engine_id: EngineId) -> None:
    engine, state = game(engine_id)
    assert engine.restore(state.model_dump_json()) == state


def test_restore_refuses_a_save_smuggling_a_pending_generation() -> None:
    engine, state = game(ENGINE_IDS[0])
    raw = json.loads(state.model_dump_json())
    raw["generation"] = {"operation": "departure", "detail": "smuggled in by hand"}

    with pytest.raises(Refusal, match="generation"):
        engine.restore(json.dumps(raw))


def test_restore_accepts_a_save_with_a_null_generation() -> None:
    engine, state = game(ENGINE_IDS[0])
    raw = json.loads(state.model_dump_json())
    raw["generation"] = None

    assert engine.restore(json.dumps(raw)) == state


def test_admit_refuses_a_pack_the_engine_has_not_installed(room_engine: SixthEngine) -> None:
    character = room_engine.create_character("Wren", "A quiet scout", ("srd",), {})

    with pytest.raises(Refusal, match="packs not installed"):
        room_engine.admit(("srd", "gone"), character)
