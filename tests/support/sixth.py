from pathlib import Path

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, Slug, slug
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, Character, Game, Scenario, ScenarioMeta
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.rooms.engine import RoomEngine
from aidm.engines.rooms.world import Dweller, MapDraft, Place, Prop, RoomWorld, Way

SIXTH = EngineId("sixth")
GATE = "gate"
YARD = "yard"
CELLAR = "cellar"
WELL = "well"
WARDEN = "warden"
LANTERN = "lantern"


class SixthWorld(RoomWorld[Dweller, Person]):
    pass


class SixthGame(Game[SixthWorld]):
    pass


class SixthScenario(Scenario[MapDraft[Dweller]]):
    pass


class SixthCharacter(Character[Person]):
    pass


class SixthEngine(RoomEngine[Dweller, Person, SixthGame]):
    """A sixth engine, a room crawler: its state model and its creation; the tools are the
    family's."""

    id = SIXTH
    title = "SIXTH"
    art_style = "Ink."
    game = SixthGame
    scenario = SixthScenario
    character = SixthCharacter
    member = Dweller
    world = SixthWorld

    def creation_steps(self, _picks: Picks) -> tuple[CreationStep, ...]:
        return ()

    def create_character(self, name: str, brief: str, _picks: Picks) -> AnyCharacter:
        return SixthCharacter(
            id=slug(name, ()),
            engine=SIXTH,
            payload=Person(id=PLAYER_ID, name=name, brief=brief, known=True),
        )

    def guidance(self) -> str:
        return "Write the keep plainly."


def installed(tmp_path: Path) -> SixthEngine:
    class Installed(SixthEngine):
        directory = tmp_path

    (tmp_path / "rules.md").write_text("Roll high.", encoding=ENCODING)
    return Installed()


def place(place_id: Slug, name: str, *, known: bool) -> Place:
    return Place(id=place_id, name=name, brief=f"The {name.lower()}", known=known, description=name)


def scenario() -> SixthScenario:
    warden = Dweller(id=WARDEN, name="Warden", brief="Keeps the gate", known=True, place=GATE)
    return SixthScenario(
        meta=ScenarioMeta(
            title="The Keep", premise="A keep with one gate.", scope="One keep, one visit."
        ),
        engine=SIXTH,
        payload=MapDraft[Dweller](
            places={
                GATE: place(GATE, "Gate", known=True),
                YARD: place(YARD, "Yard", known=False),
                CELLAR: place(CELLAR, "Cellar", known=False),
                WELL: place(WELL, "Well", known=False),
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
