from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, EntityId, Slug, slug
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, Character, Game, Scenario, ScenarioMeta
from aidm.core.play import DecisionOption
from aidm.core.tools import MasterTool
from aidm.core.views import Sections
from aidm.engines.base import PLAYER_ID, Pack, Person
from aidm.engines.registry import begin_game
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.world import SceneCanon, SceneRun, SceneWorld

FIFTH = EngineId("fifth")
KEEPER = EntityId("keeper")
SITUATION = (
    "The taproom is half empty, the fire is down to embers, and the keeper is watching the door."
)


class FifthState(SceneWorld[Person, Person]):
    pass


class FifthGame(Game[FifthState]):
    pass


class FifthScenario(Scenario[SceneCanon[Person]]):
    pass


class FifthCharacter(Character[Person]):
    pass


class FifthEngine(SceneEngine[Person, Person, FifthGame, Pack]):
    """A fifth scene engine: its state model, its creation, its tools and its sections."""

    id = FIFTH
    title = "FIFTH"
    art_style = "Ink."
    game = FifthGame
    scenario = FifthScenario
    character = FifthCharacter
    cast = Person
    pack = Pack
    world_type = FifthState
    hub_phrase = "a taproom and its regulars"

    def master_tools(self) -> tuple[MasterTool[FifthGame], ...]:
        return ()

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        return (CreationStep(id="pack", prompt="Choose a table set", options=self.pack_options()),)

    def create_character(self, name: str, brief: str, picks: Picks) -> AnyCharacter:
        return FifthCharacter(
            id=slug(name, ()),
            engine=FIFTH,
            payload=Person(id=PLAYER_ID, name=name, brief=brief, known=True),
        )

    def guidance(self, picks: Sequence[Slug], *, campaign: bool) -> str:
        return "Write the taproom plainly."

    def master_sections(self, state: FifthGame) -> Sections:
        return (("SCENE", self.world(state).run.title),)


def _installed(tmp_path: Path) -> FifthEngine:
    (tmp_path / "rules.md").write_text("Roll high.", encoding=ENCODING)
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "srd.json").write_text('{"name": "The SRD"}', encoding=ENCODING)
    FifthEngine.directory = tmp_path
    return FifthEngine()


def _scenario() -> FifthScenario:
    keeper = Person(id=KEEPER, name="Keeper", brief="Keeps the taproom", known=True)
    return FifthScenario(
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


async def test_compose_builds_the_accepted_answer_once(tmp_path: Path) -> None:
    engine = _installed(tmp_path)
    builds: list[DecisionOption] = []

    def build(written: DecisionOption) -> FifthScenario:
        builds.append(written)
        return _scenario()

    async def worldsmith[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        written = model.model_validate({"id": "srd", "label": "The SRD"})
        assert refusal(written) is None
        return written

    await engine.compose(worldsmith, "write", DecisionOption, build, lambda _: None)
    assert len(builds) == 1
