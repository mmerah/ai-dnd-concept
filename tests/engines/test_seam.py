import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import BaseModel
from support.fifth import FifthEngine, FifthGame, FifthState, engine_at, installed
from support.sixth import SixthEngine
from support.sixth import scenario as sixth_scenario
from support.table import ENGINE_IDS, TUNNELGOONS, TWENTYFOURXX, game
from support.tunnelgoons import MIRA
from support.tunnelgoons import small_world as tunnelgoons_small_world
from support.twentyfourxx import KESTREL
from support.twentyfourxx import small_world as twentyfourxx_small_world

from aidm.core.entities import EngineId, Refusal, Slug
from aidm.core.io import ENCODING
from aidm.core.model import AnyGame, Check, Generation
from aidm.core.play import DecisionOption
from aidm.engines.tools import HIRE

# A hire needs a member `game()`'s own scenario never names, so a fixture world stands in.
HIRE_GAMES: dict[EngineId, tuple[Callable[[], AnyGame], Slug]] = {
    TUNNELGOONS: (tunnelgoons_small_world, MIRA),
    TWENTYFOURXX: (twentyfourxx_small_world, KESTREL),
}


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
    assert (draft.world.turns_played, draft.world.meanwhile_due) == (
        FifthState.tempo - 1,
        False,
    )

    scene_engine.tick(draft, counted=True)

    assert (draft.world.turns_played, draft.world.meanwhile_due) == (0, True)


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
    assert scene_engine.packs.options() == (DecisionOption(id="srd", label="The SRD"),)
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


def test_begin_refuses_a_scenario_naming_an_uninstalled_pack(room_engine: SixthEngine) -> None:
    character = room_engine.create_character("Wren", "A quiet scout", "srd", {})
    stranded = sixth_scenario().model_copy(update={"pack_id": "gone"})

    with pytest.raises(Refusal, match="is not installed"):
        room_engine.begin("the-keep", stranded, character)


async def _stubbed[M: BaseModel](_prompt: str, _model: type[M], _check: Check[M]) -> M:
    raise Refusal("stubbed")


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
async def test_advance_matches_every_operation_the_engine_declares_unwritten(
    engine_id: EngineId,
) -> None:
    """`unwritten` and `advance`'s `match` stay in step: a drift here surfaces a `ValueError`."""
    engine, state = game(engine_id)

    for operation in engine.unwritten:
        if operation == HIRE:
            small_world, target = HIRE_GAMES[engine_id]
            draft = small_world().draft()
        else:
            draft, target = state.draft(), None
        request = Generation(
            operation=operation, detail="a request the stub never reads", target=target
        )

        with pytest.raises(Refusal, match="stubbed"):
            await engine.advance(draft, request, _stubbed)
