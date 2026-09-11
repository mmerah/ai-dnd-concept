from pathlib import Path
from random import Random

import pytest
from support.table import change, refused

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, Refusal, Slug, slug
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, Character, Game, Scenario, ScenarioMeta
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.rooms.engine import RoomEngine
from aidm.engines.rooms.tools import Move
from aidm.engines.rooms.world import Dweller, MapDraft, Place, Prop, RoomWorld, Visit, Way

SIXTH = EngineId("sixth")
GATE = "gate"
YARD = "yard"
CELLAR = "cellar"
WELL = "well"
WARDEN = "warden"


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
    dweller = Dweller
    world_type = SixthWorld

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


def _installed(tmp_path: Path) -> SixthEngine:
    class Installed(SixthEngine):
        directory = tmp_path

    (tmp_path / "rules.md").write_text("Roll high.", encoding=ENCODING)
    return Installed()


def _place(place_id: Slug, name: str, *, known: bool) -> Place:
    return Place(id=place_id, name=name, brief=f"The {name.lower()}", known=known, description=name)


def _scenario() -> SixthScenario:
    warden = Dweller(id=WARDEN, name="Warden", brief="Keeps the gate", known=True, place=GATE)
    return SixthScenario(
        meta=ScenarioMeta(
            title="The Keep", premise="A keep with one gate.", scope="One keep, one visit."
        ),
        engine=SIXTH,
        packs=(),
        payload=MapDraft[Dweller](
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
    ways_out = next(
        panel for panel in engine.player_view(state).panels if panel.title == "Ways out"
    )
    assert [row.label for row in ways_out.rows] == ["Yard"]
    engine.move(state, Move(to_id=YARD), Random(0))
    assert [visit.place for visit in state.payload.visits] == [GATE, YARD]


def test_unlocking_a_way_makes_it_known_and_tells_a_card(tmp_path: Path) -> None:
    engine = _installed(tmp_path)
    character = engine.create_character("Wren", "A quiet scout", {})
    state = engine.begin("the-keep", _scenario(), character)
    engine.move(state, Move(to_id=YARD), Random(0))
    draft = state.draft()
    before = next(panel for panel in engine.player_view(draft).panels if panel.title == "Ways out")
    assert [row.label for row in before.rows] == []

    facts = change(engine, draft, "unlock_way", to_id=WELL)

    way = draft.payload.way(YARD, WELL)
    assert way is not None
    assert way.known
    assert any(fact.told and fact.card == "Well unlocked" for fact in facts)
    after = next(panel for panel in engine.player_view(draft).panels if panel.title == "Ways out")
    assert [row.label for row in after.rows] == ["Well"]


def test_a_party_member_moves_with_the_player_and_is_named_in_the_trace(tmp_path: Path) -> None:
    engine = _installed(tmp_path)
    character = engine.create_character("Wren", "A quiet scout", {})
    state = engine.begin("the-keep", _scenario(), character)
    state.payload.party.append(WARDEN)

    facts = engine.move(state, Move(to_id=YARD), Random(0))

    assert state.payload.npcs[WARDEN].place == YARD
    assert any("Warden" in fact.trace and "along" in fact.trace for fact in facts)


def test_a_with_ids_entry_who_is_a_party_member_is_refused(tmp_path: Path) -> None:
    engine = _installed(tmp_path)
    character = engine.create_character("Wren", "A quiet scout", {})
    state = engine.begin("the-keep", _scenario(), character)
    state.payload.party.append(WARDEN)

    with pytest.raises(Refusal, match="without with_ids"):
        engine.move(state, Move(to_id=YARD, with_ids=(WARDEN,)), Random(0))


def test_the_familys_tools_are_offered_in_order(tmp_path: Path) -> None:
    engine = _installed(tmp_path)
    assert list(engine.tools) == [
        "reveal",
        "move_item",
        "kill",
        "join_party",
        "leave_party",
        "unlock_way",
        "move",
    ]
    character = engine.create_character("Wren", "A quiet scout", {})
    state = engine.begin("the-keep", _scenario(), character)
    draft = state.draft()

    _ = change(engine, draft, "join_party", entity_id=WARDEN)

    assert WARDEN in draft.payload.party

    _ = change(engine, draft, "leave_party", entity_id=WARDEN)

    assert draft.payload.party == []


def test_leave_party_on_a_non_member_is_refused(tmp_path: Path) -> None:
    engine = _installed(tmp_path)
    character = engine.create_character("Wren", "A quiet scout", {})
    state = engine.begin("the-keep", _scenario(), character)
    draft = state.draft()

    message = refused(engine, draft, "leave_party", entity_id=WARDEN)

    assert "does not travel with the player" in message


def test_a_party_member_is_absent_from_place_lines_while_their_items_stay(
    tmp_path: Path,
) -> None:
    engine = _installed(tmp_path)
    character = engine.create_character("Wren", "A quiet scout", {})
    state = engine.begin("the-keep", _scenario(), character)
    world = state.payload
    key = "warden-key"
    world.items[key] = Prop(id=key, name="Key", brief="A rusty key", known=True, on=WARDEN)
    world.party.append(WARDEN)

    lines = world.place_lines(known=True)

    assert "Warden[warden]" not in lines
    assert "Key[warden-key]" in lines

    panels = engine.player_view(state).panels
    party_rows = next(panel for panel in panels if panel.title == "Party").rows
    here_rows = next(panel for panel in panels if panel.title == "Also here").rows

    assert any(row.icon_id == WARDEN for row in party_rows)
    assert all(row.icon_id != WARDEN for row in here_rows)


def test_killing_a_party_member_drops_them_from_the_party(tmp_path: Path) -> None:
    engine = _installed(tmp_path)
    character = engine.create_character("Wren", "A quiet scout", {})
    state = engine.begin("the-keep", _scenario(), character)
    world = state.payload
    world.party.append(WARDEN)

    facts = world.kill(world.npcs[WARDEN])

    assert world.party == []
    assert not world.npcs[WARDEN].alive
    assert any(fact.card == "Warden is dead" for fact in facts)


def test_a_party_member_who_is_not_at_the_players_place_is_refused(tmp_path: Path) -> None:
    engine = _installed(tmp_path)
    character = engine.create_character("Wren", "A quiet scout", {})
    state = engine.begin("the-keep", _scenario(), character)
    world = state.payload

    with pytest.raises(ValueError, match="not at their place"):
        SixthWorld(
            places=world.places,
            ways=world.ways,
            npcs=world.npcs,
            items=world.items,
            player=world.player,
            visits=[Visit(place=YARD)],
            party=[WARDEN],
        )
