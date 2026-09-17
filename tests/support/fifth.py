from pathlib import Path

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, slug
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, Character, Game, PackSelection, Scenario, ScenarioMeta
from aidm.core.prompt import Sections
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.packs import Pack
from aidm.engines.scenes.engine import SceneEngine
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


class FifthEngine(SceneEngine[Person, FifthGame, Pack]):
    """A fifth scene engine: its state model, its creation, its sections."""

    id = FIFTH
    title = "FIFTH"
    authoring = "Write the taproom plainly."
    art_style = "Ink."
    game = FifthGame
    scenario = FifthScenario
    character = FifthCharacter
    member = Person
    pack = Pack
    world = FifthState

    def creation_steps(self, _picks: Picks) -> tuple[CreationStep, ...]:
        return self.supplement_steps()

    def build_character(self, name: str, brief: str, _picks: Picks) -> AnyCharacter:
        return FifthCharacter(
            id=slug(name, ()),
            engine=FIFTH,
            packs=PackSelection(ids=("srd",)),
            payload=Person(id=PLAYER_ID, name=name, brief=brief, known=True),
        )

    def master_sections(self, state: FifthGame) -> Sections:
        return (("SCENE", self.world_of(state).run.title),)


def engine_at(tmp_path: Path) -> type[FifthEngine]:
    class Installed(FifthEngine):
        directory = tmp_path

    return Installed


def installed(tmp_path: Path) -> FifthEngine:
    (tmp_path / "rules.md").write_text("Roll high.", encoding=ENCODING)
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "srd.json").write_text(
        '{"name": "The SRD", "source": "the test", "license": "CC0"}', encoding=ENCODING
    )
    (tmp_path / "look.json").write_text(
        '{"palette": {}, "dice": {"body": "#000", "ink": "#fff", "glow": "#fff"}}',
        encoding=ENCODING,
    )
    return engine_at(tmp_path)(tmp_path / "written")


def scenario() -> FifthScenario:
    keeper = Person(id=KEEPER, name="Keeper", brief="Keeps the taproom", known=True)
    return FifthScenario(
        meta=ScenarioMeta(
            title="The Taproom",
            premise="A quiet night that will not stay quiet.",
            scope="One evening at the taproom, start to close.",
        ),
        engine=FIFTH,
        packs=PackSelection(ids=("srd",)),
        payload=SceneDraft[Person](
            place="taproom",
            title="The Taproom",
            focus="Who is asking after Wren?",
            situation=SITUATION,
            present=("keeper",),
            cast={KEEPER: keeper},
        ),
    )
