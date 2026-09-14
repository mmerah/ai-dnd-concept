from pathlib import Path

import pytest
from support.fifth import FifthEngine, FifthGame, engine_at, scenario
from support.table import ENGINE_IDS, game

from aidm.core.entities import EngineId, Refusal
from aidm.core.io import ENCODING, read_cached_text
from aidm.core.play import SpokenLine
from aidm.core.views import NarratorView


def test_the_tempo_floor_refuses_a_tempo_below_two(scene_engine: FifthEngine) -> None:
    class TooFast(type(scene_engine)):
        meanwhile_turns = 1

    with pytest.raises(ValueError, match="ticks every"):
        TooFast()


def test_the_clock_arms_on_reaching_the_tempo_and_starts_over(
    scene_engine: FifthEngine, begun_scene: FifthGame
) -> None:
    draft = begun_scene.draft()

    for _ in range(scene_engine.meanwhile_turns - 1):
        scene_engine.tick(draft, counted=True)
    assert (draft.payload.turns_played, draft.payload.meanwhile_due) == (
        scene_engine.meanwhile_turns - 1,
        False,
    )

    scene_engine.tick(draft, counted=True)

    assert (draft.payload.turns_played, draft.payload.meanwhile_due) == (0, True)


def test_construction_refuses_when_no_srd_table_set_is_installed(
    scene_engine: FifthEngine, tmp_path: Path
) -> None:
    engine_type = type(scene_engine)
    (tmp_path / "packs" / "srd.json").rename(tmp_path / "packs" / "other.json")
    with pytest.raises(ValueError, match="ships no 'srd' pack"):
        engine_type()


def test_construction_refuses_when_the_packs_dir_has_no_srd(tmp_path: Path) -> None:
    (tmp_path / "rules.md").write_text("Roll high.", encoding=ENCODING)
    (tmp_path / "packs").mkdir()
    with pytest.raises(ValueError, match="ships no 'srd' pack"):
        engine_at(tmp_path)()


def test_a_pack_with_doubled_keys_is_refused(tmp_path: Path) -> None:
    (tmp_path / "rules.md").write_text("Roll high.", encoding=ENCODING)
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "srd.json").write_text(
        '{"name": "The SRD", "name": "Twice"}', encoding=ENCODING
    )
    with pytest.raises(Refusal, match="duplicate keys"):
        engine_at(tmp_path)()


def test_a_fifth_scene_engine_begins_a_playable_game(
    scene_engine: FifthEngine, begun_scene: FifthGame
) -> None:
    assert scene_engine.supplement_options() == ()
    assert scene_engine.instructions.startswith("Roll high.")
    assert scene_engine.instructions.endswith(
        read_cached_text(scene_engine.family_dir / "rules.md")
    )
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


def test_a_scene_engine_offers_the_familys_tools_without_naming_them(
    scene_engine: FifthEngine,
) -> None:
    assert list(scene_engine.tools) == [
        "reveal",
        "kill",
        "join_party",
        "leave_party",
        "enter",
        "leave",
        "next_scene",
    ]


class _CountingFifthEngine(FifthEngine):
    narrator_view_calls = 0

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        super().__init__()

    def narrator_view(self, state: FifthGame) -> NarratorView:
        self.narrator_view_calls += 1
        return super().narrator_view(state)


@pytest.mark.usefixtures("scene_engine")
def test_close_builds_no_narrator_view(tmp_path: Path) -> None:
    engine = _CountingFifthEngine(tmp_path)
    character = engine.create_character("Wren", "A quiet scout", {})
    state = engine.begin("the-taproom", scenario(), character)
    before = engine.narrator_view_calls

    closed = engine.close(state.draft(), (SpokenLine(text="Nothing stirs."),), (), words="I wait.")

    assert engine.narrator_view_calls == before
    assert closed.exchanges()[-1].words == "I wait."


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_restored_round_trips(engine_id: EngineId) -> None:
    engine, state = game(engine_id)
    assert engine.restore(state.model_dump_json()) == state
