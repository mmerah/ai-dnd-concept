from pathlib import Path

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, Slug, slug
from aidm.core.model import AnyCharacter, Character, Game, Scenario, ScenarioMeta
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.packs import Pack
from aidm.engines.rooms.engine import RoomEngine
from aidm.engines.rooms.world import Dweller, MapProposal, Place, Prop, RoomWorld, Way
from support.engine_dir import install_engine_dir

SIXTH = EngineId("sixth")
GATE = "gate"
YARD = "yard"
CELLAR = "cellar"
WELL = "well"
WARDEN = "warden"
LANTERN = "lantern"


class SixthWorld(RoomWorld[Person, Dweller]):
    tempo = 6


SixthGame = Game[SixthWorld]


class SixthScenario(Scenario[MapProposal[Dweller]]):
    pass


class SixthCharacter(Character[Person]):
    pass


class SixthEngine(RoomEngine[Person, Dweller, SixthWorld, Pack]):
    """A sixth engine, a room crawler; the tools are the family's."""

    id = SIXTH
    title = "SIXTH"
    authoring = "Write the keep plainly."
    art_style = "Ink."
    game = SixthGame
    scenario = SixthScenario
    character = SixthCharacter
    member = Dweller
    pack = Pack
    world = SixthWorld

    def creation_steps(self, _packs: tuple[Slug, ...], _picks: Picks) -> tuple[CreationStep, ...]:
        return ()

    def build_character(
        self, name: str, brief: str, packs: tuple[Slug, ...], _picks: Picks
    ) -> AnyCharacter:
        return SixthCharacter(
            id=slug(name, ()),
            engine=SIXTH,
            packs=packs,
            payload=Person(id=PLAYER_ID, name=name, brief=brief, known=True),
        )


def installed(tmp_path: Path) -> SixthEngine:
    class Installed(SixthEngine):
        directory = tmp_path

    install_engine_dir(tmp_path)
    return Installed(tmp_path / "written")


def _place(place_id: Slug, name: str, *, known: bool) -> Place:
    return Place(id=place_id, name=name, brief=f"The {name.lower()}", known=known, description=name)


def scenario() -> SixthScenario:
    warden = Dweller(id=WARDEN, name="Warden", brief="Keeps the gate", known=True, place=GATE)
    return SixthScenario(
        meta=ScenarioMeta(
            title="The Keep", premise="A keep with one gate.", scope="One keep, one visit."
        ),
        engine=SIXTH,
        packs=("srd",),
        payload=MapProposal[Dweller](
            places={
                GATE: _place(GATE, "Gate", known=True),
                YARD: _place(YARD, "Yard", known=False),
                CELLAR: _place(CELLAR, "Cellar", known=False),
                WELL: _place(WELL, "Well", known=False),
            },
            ways={
                GATE: [Way(to=YARD, known=True)],
                YARD: [Way(to=CELLAR), Way(to=WELL, locked=True)],
                CELLAR: [Way(to=WELL)],
            },
            npcs={WARDEN: warden},
            items={
                LANTERN: Prop(
                    id=LANTERN, name="Lantern", brief="A dim lantern", known=False, on=YARD
                )
            },
            start=GATE,
        ),
    )
