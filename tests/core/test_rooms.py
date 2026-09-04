from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, EntityId, slug
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, Character, Game, Scenario, ScenarioMeta
from aidm.core.tools import MasterTool
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.rooms.engine import RoomEngine
from aidm.engines.rooms.tools import Move
from aidm.engines.rooms.world import Dweller, Place, RoomCanon, RoomWorld, Way

SIXTH = EngineId("sixth")
GATE = EntityId("gate")
YARD = EntityId("yard")
CELLAR = EntityId("cellar")
WELL = EntityId("well")
WARDEN = EntityId("warden")


class SixthWorld(RoomWorld[Dweller, Person]):
    pass


class SixthGame(Game[SixthWorld]):
    pass


class SixthScenario(Scenario[RoomCanon[Dweller]]):
    pass


class SixthCharacter(Character[Person]):
    pass


class SixthEngine(RoomEngine[Dweller, Person, SixthGame]):
    """A sixth engine, a room crawler: its state model, its creation and no tools of its own."""

    id = SIXTH
    title = "SIXTH"
    art_style = "Ink."
    game = SixthGame
    scenario = SixthScenario
    character = SixthCharacter
    dweller = Dweller
    world_type = SixthWorld

    def master_tools(self) -> tuple[MasterTool[SixthGame], ...]:
        return ()

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        return ()

    def create_character(self, name: str, brief: str, picks: Picks) -> AnyCharacter:
        return SixthCharacter(
            id=slug(name, ()),
            engine=SIXTH,
            payload=Person(id=PLAYER_ID, name=name, brief=brief, known=True),
        )

    def guidance(self) -> str:
        return "Write the keep plainly."


def _engine_at(tmp_path: Path) -> type[SixthEngine]:
    class Installed(SixthEngine):
        directory = tmp_path

    return Installed


def _installed(tmp_path: Path) -> SixthEngine:
    (tmp_path / "rules.md").write_text("Roll high.", encoding=ENCODING)
    return _engine_at(tmp_path)()


def _place(place_id: EntityId, name: str, *, known: bool) -> Place:
    return Place(id=place_id, name=name, brief=f"The {name.lower()}", known=known, description=name)


def _scenario() -> SixthScenario:
    warden = Dweller(id=WARDEN, name="Warden", brief="Keeps the gate", known=True, place=GATE)
    return SixthScenario(
        meta=ScenarioMeta(title="The Keep", premise="A keep with one gate."),
        engine=SIXTH,
        packs=(),
        payload=RoomCanon[Dweller](
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
            start=GATE,
        ),
    )


def test_a_sixth_room_engine_begins_a_playable_game(tmp_path: Path) -> None:
    engine = _installed(tmp_path)
    character = engine.create_character("Wren", "A quiet scout", {})

    state = engine.begin("the-keep", _scenario(), character)

    assert engine.master_sections(state)[0] == ("CURRENT PLACE", "Gate[gate]\nGate")
    assert "commission" in engine.tools
    ways_out = next(
        panel for panel in engine.player_view(state).panels if panel.title == "Ways out"
    )
    assert [row.label for row in ways_out.rows] == ["Yard"]
    engine.move(state, Move(to_id=YARD), Random(0))
    assert [visit.place for visit in state.payload.visits] == [GATE, YARD]
