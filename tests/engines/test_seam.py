from collections.abc import Sequence
from pathlib import Path

import pytest
from support.table import ENGINE_IDS, game

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, Refusal, Slug, slug
from aidm.core.io import ENCODING, decode, read_prompt
from aidm.core.model import AnyCharacter, Character, Game, Scenario, ScenarioMeta
from aidm.core.play import DecisionOption, SpokenLine
from aidm.core.prompt import Pairs
from aidm.core.views import NarratorView
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.packs import ScenePack
from aidm.engines.scenes.tools import SceneDraft
from aidm.engines.scenes.world import SceneWorld

FIFTH = EngineId("fifth")
KEEPER = "keeper"
SITUATION = (
    "The taproom is half empty, the fire is down to embers, and the keeper is watching the door."
)


class FifthState(SceneWorld[Person]):
    pass


class FifthGame(Game[FifthState]):
    pass


class FifthScenario(Scenario[SceneDraft[Person]]):
    pass


class FifthCharacter(Character[Person]):
    pass


class FifthEngine(SceneEngine[Person, FifthGame, ScenePack]):
    """A fifth scene engine: its state model, its creation, its sections."""

    id = FIFTH
    title = "FIFTH"
    art_style = "Ink."
    game = FifthGame
    scenario = FifthScenario
    character = FifthCharacter
    cast = Person
    pack = ScenePack
    world_type = FifthState

    def creation_steps(self, _picks: Picks) -> tuple[CreationStep, ...]:
        return (CreationStep(id="pack", label="Choose a table set", options=self.pack_options()),)

    def create_character(self, name: str, brief: str, _picks: Picks) -> AnyCharacter:
        return FifthCharacter(
            id=slug(name, ()),
            engine=FIFTH,
            payload=Person(id=PLAYER_ID, name=name, brief=brief, known=True),
        )

    def guidance(self, _picks: Sequence[Slug]) -> str:
        return "Write the taproom plainly."

    def master_sections(self, state: FifthGame) -> Pairs:
        return (("SCENE", self.world(state).run.title),)


def _engine_at(tmp_path: Path) -> type[FifthEngine]:
    class Installed(FifthEngine):
        directory = tmp_path

    return Installed


def _installed(tmp_path: Path) -> FifthEngine:
    (tmp_path / "rules.md").write_text("Roll high.", encoding=ENCODING)
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "srd.json").write_text(
        '{"name": "The SRD", "source": "the test", "license": "CC0"}', encoding=ENCODING
    )
    return _engine_at(tmp_path)()


def test_srd_pack_refuses_when_no_srd_table_set_is_installed(tmp_path: Path) -> None:
    engine_type = type(_installed(tmp_path))
    (tmp_path / "packs" / "srd.json").rename(tmp_path / "packs" / "other.json")
    engine = engine_type()
    with pytest.raises(Refusal, match="the SRD table set is not installed"):
        _ = engine.srd_pack()


def test_a_pack_with_doubled_keys_is_refused(tmp_path: Path) -> None:
    (tmp_path / "rules.md").write_text("Roll high.", encoding=ENCODING)
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "srd.json").write_text(
        '{"name": "The SRD", "name": "Twice"}', encoding=ENCODING
    )
    with pytest.raises(Refusal, match="duplicate keys"):
        _engine_at(tmp_path)()


def _scenario() -> FifthScenario:
    keeper = Person(id=KEEPER, name="Keeper", brief="Keeps the taproom", known=True)
    return FifthScenario(
        meta=ScenarioMeta(
            title="The Taproom",
            premise="A quiet night that will not stay quiet.",
            scope="One evening at the taproom, start to close.",
        ),
        engine=FIFTH,
        packs=("srd",),
        payload=SceneDraft[Person](
            place="taproom",
            title="The Taproom",
            focus="Who is asking after Wren?",
            situation=SITUATION,
            present=("keeper",),
            cast={KEEPER: keeper},
        ),
    )


def test_a_fifth_scene_engine_begins_a_playable_game(tmp_path: Path) -> None:
    engine = _installed(tmp_path)
    character = engine.create_character("Wren", "A quiet scout", {})

    state = engine.begin("the-taproom", _scenario(), character)

    assert engine.pack_options() == (DecisionOption(id="srd", label="The SRD"),)
    assert engine.instructions.startswith("Roll high.")
    assert engine.instructions.endswith(read_prompt(engine.family_dir / "rules.md"))
    assert engine.narrator_view(state).title == "The Taproom"
    assert engine.master_sections(state) == (("SCENE", "The Taproom"),)
    assert [row.label for row in engine.player_view(state).panels[-2].rows] == ["Keeper"]


def test_a_game_with_no_chapter_open_is_refused(tmp_path: Path) -> None:
    engine = _installed(tmp_path)
    character = engine.create_character("Wren", "A quiet scout", {})
    state = engine.begin("the-taproom", _scenario(), character)
    state.log.clear()

    with pytest.raises(Refusal, match="no chapter open"):
        engine.validate(state)


def test_a_scene_engine_offers_the_familys_tools_without_naming_them(tmp_path: Path) -> None:
    assert list(_installed(tmp_path).tools) == [
        "reveal",
        "enter",
        "leave",
        "kill",
        "join_party",
        "leave_party",
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


def test_close_builds_no_narrator_view(tmp_path: Path) -> None:
    _ = _installed(tmp_path)  # writes rules.md and packs/srd.json onto tmp_path
    engine = _CountingFifthEngine(tmp_path)
    character = engine.create_character("Wren", "A quiet scout", {})
    state = engine.begin("the-taproom", _scenario(), character)
    before = engine.narrator_view_calls

    closed = engine.close(state.draft(), (SpokenLine(text="Nothing stirs."),), (), words="I wait.")

    assert engine.narrator_view_calls == before
    assert closed.exchanges()[-1].words == "I wait."


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_restored_round_trips(engine_id: EngineId) -> None:
    engine, state = game(engine_id)
    assert engine.restore(decode(state.model_dump_json())) == state
