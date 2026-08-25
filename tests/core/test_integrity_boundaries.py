import json
from pathlib import Path

import pytest
from core_test_support import (
    LONER3E,
    begin_game,
    build_engine,
    character,
    initialized,
    scenario,
    updated,
    with_entity,
)
from pydantic import ValidationError

from aidm.content.io import SavedGame, load_character
from aidm.content.model import Character, CharacterProfile, Scenario
from aidm.engines.loner3e.rules import RULES, Mechanics
from aidm.state.entities import PLAYER_ID, Entity, EntityId
from aidm.state.model import Game

HELD = EntityId("frayed-rope")
MARA = EntityId("mara")
ELENA = EntityId("elena")
TOMAS = EntityId("tomas")
_HALL = {"id": "hall", "kind": "location", "name": "the hall", "brief": "A hall.", "known": True}
_DOUBLED = json.dumps(
    {
        "meta": {"title": "Twice Over", "premise": "One id, authored twice."},
        "starting_location_id": "hall",
        "engines": ["loner3e"],
        "world": {"entities": [_HALL, {**_HALL, "name": "the hall again"}]},
    }
)


def _character(*, holds: Entity) -> Character:
    return Character(
        id="test-character",
        profile=CharacterProfile(
            name="Test Character",
            brief="A character built only for this test.",
            items=(holds,),
        ),
        rules={},
    )


def _rope(item_id: EntityId, *, known: bool = True) -> Entity:
    return Entity(
        id=item_id,
        kind="item",
        name="rope",
        brief="A length of rope.",
        known=known,
        parent_id=PLAYER_ID,
    )


def test_world_and_game_state_reject_inconsistent_topology() -> None:
    _, state = initialized()
    twice = state.world.require(PLAYER_ID).model_dump(round_trip=True)
    with pytest.raises(ValidationError, match="duplicate entity ids"):
        type(state.world).model_validate({"entities": [twice, twice]})

    with pytest.raises(ValueError, match="player entity must be known"):
        with_entity(state, updated(state.player, known=False))

    with pytest.raises(ValidationError, match="not in a valid location"):
        with_entity(state, updated(state.player, parent_id=EntityId("missing")))

    carried = state.world.children(PLAYER_ID, "item")[0]
    with pytest.raises(ValidationError, match="cannot be inside anything"):
        with_entity(state, updated(carried, kind="location"))


def test_an_engine_refuses_an_authored_payload_it_cannot_read(tmp_path: Path) -> None:
    folder = tmp_path / "broken"
    folder.mkdir()
    _ = (folder / "base.json").write_text('{"name": "Broken", "brief": "Built for this test."}')
    _ = (folder / f"{LONER3E}.json").write_text('{"character": {"gear": null}}')

    engine = build_engine(LONER3E)
    with pytest.raises(ValidationError, match="gear"):
        _ = load_character(tmp_path, "broken", engine.id, engine.check_overlay)


def test_scenario_topology_is_validated() -> None:
    with pytest.raises(ValidationError, match="starting_location_id"):
        updated(scenario(), starting_location_id=EntityId("missing"))
    with pytest.raises(ValidationError, match="duplicate entity ids"):
        # Keyed by id from a flat array, so the duplicate has to be caught before it collapses.
        Scenario.model_validate_json(_DOUBLED)


def test_a_location_no_walk_reaches_is_refused() -> None:
    authored = scenario()
    undercroft = Entity(
        id=EntityId("undercroft"),
        kind="location",
        name="the undercroft",
        brief="A chamber no passage names.",
        known=False,
    )
    grown = updated(authored.world, entities=(*authored.world.entities, undercroft))
    with pytest.raises(ValidationError, match=r"no walk.*undercroft"):
        updated(authored, world=grown)


def test_world_state_rejects_broken_exits_and_party() -> None:
    world = scenario().world
    study = world.require(EntityId("study"))
    exposed = updated(study, exits=(*study.exits, {"to": "bell-tower", "known": True}))
    with pytest.raises(ValidationError, match="has not met"):
        updated(world, entities=tuple(exposed if e.id == study.id else e for e in world.entities))

    with pytest.raises(ValidationError, match="without being met"):
        updated(world, party=(ELENA,))
    with pytest.raises(ValidationError, match="cannot travel with themselves"):
        updated(world, party=(PLAYER_ID,))

    mara = world.require(MARA)
    wandering = updated(mara, exits=({"to": "study"},))
    with pytest.raises(ValidationError, match="cannot have exits"):
        updated(world, entities=tuple(wandering if e.id == mara.id else e for e in world.entities))


def test_entity_ids_use_one_grammar() -> None:
    study = scenario().world.require(EntityId("study"))
    with pytest.raises(ValidationError, match="pattern"):
        _ = updated(study, id="bell_tower")
    with pytest.raises(ValidationError, match="pattern"):
        _ = updated(study, exits=({"to": "bell_tower"},))


def test_a_scenario_starts_the_party_it_authors() -> None:
    engine = build_engine(LONER3E)
    authored = scenario()
    started = updated(authored, world=updated(authored.world, party=[MARA]))

    begun = begin_game(engine, "whispering-vault", started, character())
    assert begun.world.party == [MARA]
    # Tomas is known and unique, so this is the stands-at-start check alone, not the party's own.
    with pytest.raises(ValidationError, match="who they set out with"):
        updated(authored, world=updated(authored.world, party=[TOMAS]))


def test_a_character_knows_the_gear_they_start_with() -> None:
    with pytest.raises(ValidationError, match="knows the gear they start with"):
        _character(holds=_rope(HELD, known=False))


def _luck(state: Game) -> int:
    return Mechanics.of_game(state).sheets[PLAYER_ID].luck.current


def test_a_mechanics_mutation_lands_on_the_commit_and_nowhere_else() -> None:
    _, state = initialized()
    draft = state.draft()
    Mechanics.of_game(draft).sheets[PLAYER_ID].luck.current = 1

    committed = draft.committed()

    assert _luck(committed) == 1
    assert SavedGame.from_game(committed).mechanics != SavedGame.from_game(state).mechanics
    assert _luck(state) == RULES.luck_max
