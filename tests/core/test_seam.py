from collections.abc import Sequence
from pathlib import Path

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, EntityId, Slug, slug
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, Character, Game, Scenario, ScenarioMeta
from aidm.core.play import DecisionOption
from aidm.core.tools import MasterTool
from aidm.core.views import Rows
from aidm.engines.core import PLAYER_ID, Pack, Person
from aidm.engines.registry import begin_game
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.world import SceneCanon, SceneRun, SceneWorld, new_world

FIFTH = EngineId("fifth")
KEEPER = EntityId("keeper")
SITUATION = (
    "The taproom is half empty, the fire is down to embers, and the keeper is watching the door."
)


class FifthState(SceneWorld[Person, Person]):
    pass


class FifthGame(Game[FifthState]):
    pass


class FifthScenarioFile(Scenario[SceneCanon[Person]]):
    pass


class FifthCharacterFile(Character[Person]):
    pass


class FifthEngine(SceneEngine[Person, Person, FifthGame, Pack]):
    """A fifth scene engine: its state model, its creation, its tools and its sections."""

    id = FIFTH
    title = "FIFTH"
    art_style = "Ink."
    game = FifthGame
    scenario = FifthScenarioFile
    character = FifthCharacterFile
    cast = Person
    pack = Pack
    hub_phrase = "a taproom and its regulars"

    def master_tools(self) -> tuple[MasterTool[FifthGame], ...]:
        return ()

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        return (CreationStep(id="pack", prompt="Choose a table set", options=self.pack_options()),)

    def create_character(self, name: str, brief: str, picks: Picks) -> AnyCharacter:
        return FifthCharacterFile(
            id=slug(name, ()),
            engine=FIFTH,
            name=name,
            brief=brief,
            payload=Person(id=PLAYER_ID, name=name, brief=brief, known=True),
        )

    def preview_character(self, character: AnyCharacter) -> Rows:
        return (("Name", character.name),)

    def guidance(self, picks: Sequence[Slug], *, campaign: bool) -> str:
        return "Write the taproom plainly."

    def new_state(self, canon: SceneCanon[Person], character: AnyCharacter) -> FifthState:
        player = Person(id=PLAYER_ID, name=character.name, brief=character.brief, known=True)
        return new_world(FifthState, canon, player)

    def master_sections(self, state: FifthGame) -> Rows:
        return (("SCENE", self.world(state).run.title),)


def _installed(tmp_path: Path) -> FifthEngine:
    (tmp_path / "rules.md").write_text("Roll high.", encoding=ENCODING)
    (tmp_path / "worldsmith.md").write_text("You write the world.", encoding=ENCODING)
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "srd.json").write_text('{"name": "The SRD"}', encoding=ENCODING)
    FifthEngine.directory = tmp_path
    return FifthEngine(tmp_path / "user-packs")


def _scenario() -> FifthScenarioFile:
    keeper = Person(id=KEEPER, name="Keeper", brief="Keeps the taproom", known=True)
    return FifthScenarioFile(
        meta=ScenarioMeta(title="The Taproom", premise="A quiet night that will not stay quiet."),
        engine=FIFTH,
        packs=("srd",),
        payload=SceneCanon(
            cast={KEEPER: keeper},
            opening=SceneRun(
                place="taproom",
                title="The Taproom",
                question="Who is asking after Wren?",
                situation=SITUATION,
                here=[KEEPER],
            ),
        ),
    )


def test_a_fifth_scene_engine_begins_a_playable_game(tmp_path: Path) -> None:
    engine = _installed(tmp_path)
    character = engine.create_character("Wren", "A quiet scout", {})

    state = begin_game(engine, "the-taproom", _scenario(), character)
    if not isinstance(state, FifthGame):
        raise AssertionError("the fifth engine began another game type")

    assert engine.pack_options() == (DecisionOption(id="srd", label="The SRD"),)
    assert engine.instructions == "Roll high."
    assert engine.narrator_view(state).title == "The Taproom"
    assert engine.master_sections(state) == (("SCENE", "The Taproom"),)
    assert [row.label for row in engine.player_view(state).panels[-2].rows] == [
        "Wren (you)",
        "Keeper",
    ]
