import json
from pathlib import Path

import pytest
from support.engine_dir import install_engine_dir
from support.table import (
    ENGINE_IDS,
    ENGINES_BUILT,
    LIBRARY,
    LONER3E,
    SCENARIO_MODELS,
    game,
    scenario_for,
)

from aidm.core.entities import EngineId, Refusal
from aidm.core.io import ENCODING
from aidm.core.model import Character
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.loner3e.world import Loner3eWorld
from aidm.engines.tunnelgoons.engine import TunnelGoonsEngine
from aidm.engines.tunnelgoons.world import TunnelGoonsWorld


def _engine_at(tmp_path: Path) -> type[TunnelGoonsEngine]:
    """A shipped engine read out of a directory a test writes, so construction is the subject."""

    class Installed(TunnelGoonsEngine):
        directory = tmp_path

    return Installed


def test_the_tempo_floor_refuses_a_tempo_below_two(tmp_path: Path) -> None:
    class Impatient(TunnelGoonsWorld):
        tempo = 1

    class TooFast(_engine_at(tmp_path)):
        world = Impatient

    install_engine_dir(tmp_path)

    with pytest.raises(ValueError, match="ticks every"):
        TooFast(tmp_path / "written")


def test_the_clock_arms_on_reaching_the_tempo_and_starts_over() -> None:
    engine, state = game(LONER3E)
    draft = state.draft()

    for _ in range(Loner3eWorld.tempo - 1):
        engine.tick(draft, counted=True)
    assert (draft.world.turns_played, draft.world.meanwhile_due) == (
        Loner3eWorld.tempo - 1,
        False,
    )

    engine.tick(draft, counted=True)

    assert (draft.world.turns_played, draft.world.meanwhile_due) == (0, True)


def test_construction_refuses_when_no_srd_table_set_is_installed(tmp_path: Path) -> None:
    install_engine_dir(tmp_path)
    (tmp_path / "packs" / "srd.json").rename(tmp_path / "packs" / "other.json")
    with pytest.raises(ValueError, match="ships no 'srd' pack"):
        _engine_at(tmp_path)(tmp_path / "written")


def test_a_pack_with_doubled_keys_is_refused(tmp_path: Path) -> None:
    install_engine_dir(tmp_path)
    (tmp_path / "packs" / "srd.json").write_text(
        '{"name": "The SRD", "name": "Twice"}', encoding=ENCODING
    )
    with pytest.raises(Refusal, match="duplicate keys"):
        _engine_at(tmp_path)(tmp_path / "written")


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_player_of_refuses_a_sheet_the_engine_does_not_write(engine_id: EngineId) -> None:
    engine = ENGINES_BUILT[engine_id]
    stranger = Character[Person](
        id="wren",
        engine=engine.id,
        sheet=Person(id=PLAYER_ID, name="Wren", brief="", known=True),
    )

    with pytest.raises(Refusal, match="is not a"):
        engine.player_of(stranger)


def test_a_game_with_no_chapter_open_is_refused() -> None:
    engine, state = game(LONER3E)
    state.log.clear()

    with pytest.raises(Refusal, match="no chapter open"):
        engine.validate(state)


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_restore_refuses_a_save_naming_an_uninstalled_pack(engine_id: EngineId) -> None:
    engine, state = game(engine_id)

    with pytest.raises(Refusal, match="is not installed"):
        engine.restore(state.model_copy(update={"pack_id": "gone"}).model_dump_json())


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_one_panel_alone_carries_the_portrait(engine_id: EngineId) -> None:
    engine, state = game(engine_id)

    assert [panel.title for panel in engine.player_view(state).panels if panel.portrait] == [
        "Character"
    ]


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_restored_round_trips(engine_id: EngineId) -> None:
    engine, state = game(engine_id)
    assert engine.restore(state.model_dump_json()) == state


def test_restore_refuses_a_save_smuggling_a_pending_commission() -> None:
    engine, state = game(ENGINE_IDS[0])
    raw = json.loads(state.model_dump_json())
    raw["commission"] = {"operation": "departure", "detail": "smuggled in by hand"}

    with pytest.raises(Refusal, match="commission"):
        engine.restore(json.dumps(raw))


def test_restore_accepts_a_save_with_a_null_commission() -> None:
    engine, state = game(ENGINE_IDS[0])
    raw = json.loads(state.model_dump_json())
    raw["commission"] = None

    assert engine.restore(json.dumps(raw)) == state


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_begin_refuses_a_scenario_naming_an_uninstalled_pack(engine_id: EngineId) -> None:
    engine = ENGINES_BUILT[engine_id]
    scenario_id = scenario_for(engine_id)
    stranded = LIBRARY.read_scenario(scenario_id, SCENARIO_MODELS).model_copy(
        update={"pack_id": "gone"}
    )
    character = LIBRARY.read_character("kael", engine.id, engine.character)

    with pytest.raises(Refusal, match="is not installed"):
        engine.begin(scenario_id, stranded, character)
