from pathlib import Path

import pytest
from core_test_support import (
    CHARACTERS,
    ENGINES_BUILT,
    LONER3E,
    SCENARIOS,
    TWENTYFOURXX,
    begin_game,
    character,
    initialized,
    scenario,
    scenario_for,
    sheet_of,
    updated,
    with_entity,
)
from pydantic import ValidationError

from aidm.content.io import load_character, load_scenario
from aidm.content.model import Character, CharacterProfile
from aidm.engines.core import rules
from aidm.engines.loner3e.rules import RULES, Sheet
from aidm.state.entities import PLAYER_ID, Entity, EntityId
from aidm.state.model import Game

HELD = EntityId("frayed-rope")
MARA = EntityId("mara")
ELENA = EntityId("elena")
TOMAS = EntityId("tomas")


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


def test_a_doubled_id_in_a_world_file_is_refused(tmp_path: Path) -> None:
    world = (SCENARIOS / "whispering-vault" / "world.json").read_text(encoding="utf-8")
    doubled = world.replace('"study": {', '"study": {}, "study": {', 1)
    (tmp_path / "doubled").mkdir()
    _ = (tmp_path / "doubled" / "world.json").write_text(doubled, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate keys"):
        _ = load_scenario(tmp_path, "doubled")


def test_world_and_game_state_reject_inconsistent_topology() -> None:
    _, state = initialized()
    misfiled = state.world.require(PLAYER_ID).model_dump(round_trip=True)
    with pytest.raises(ValidationError, match="filed under"):
        type(state.world).model_validate({"entities": {"someone-else": misfiled}})

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

    engine = ENGINES_BUILT[LONER3E]
    with pytest.raises(ValidationError, match="gear"):
        _ = load_character(tmp_path, "broken", engine.id, engine.check_overlay)


def test_scenario_topology_is_validated() -> None:
    with pytest.raises(ValidationError, match="starting_location_id"):
        updated(scenario(), starting_location_id=EntityId("missing"))


def test_a_location_no_walk_reaches_is_refused() -> None:
    authored = scenario()
    undercroft = Entity(
        id=EntityId("undercroft"),
        kind="location",
        name="the undercroft",
        brief="A chamber no passage names.",
        known=False,
    )
    grown = updated(authored.world, entities={**authored.world.entities, "undercroft": undercroft})
    with pytest.raises(ValidationError, match=r"no walk.*undercroft"):
        updated(authored, world=grown)


def test_world_state_rejects_broken_exits_and_party() -> None:
    world = scenario().world
    study = world.require(EntityId("study"))
    exposed = updated(study, exits=(*study.exits, {"to": "bell-tower", "known": True}))
    with pytest.raises(ValidationError, match="has not met"):
        updated(world, entities={**world.entities, study.id: exposed})

    with pytest.raises(ValidationError, match="without being met"):
        updated(world, party=(ELENA,))

    mara = world.require(MARA)
    wandering = updated(mara, exits=({"to": "study"},))
    with pytest.raises(ValidationError, match="cannot have exits"):
        updated(world, entities={**world.entities, mara.id: wandering})


def test_a_committed_game_refuses_a_player_who_travels_with_themselves() -> None:
    """The played id is state, not world canon, so the party rule is checked at the commit."""
    _, state = initialized()
    draft = state.draft()
    draft.world.party.append(draft.player_id)
    with pytest.raises(ValueError, match="cannot travel with themselves"):
        _ = draft.committed()


def test_entity_ids_use_one_grammar() -> None:
    study = scenario().world.require(EntityId("study"))
    with pytest.raises(ValidationError, match="pattern"):
        _ = updated(study, id="bell_tower")
    with pytest.raises(ValidationError, match="pattern"):
        _ = updated(study, exits=({"to": "bell_tower"},))


def test_a_scenario_starts_the_party_it_authors() -> None:
    engine = ENGINES_BUILT[LONER3E]
    authored = scenario()
    started = updated(authored, world=updated(authored.world, party=[MARA]))

    begun = begin_game(engine, "whispering-vault", started, character())
    assert begun.world.party == [MARA]
    # Tomas is known and unique, so this is the stands-at-start check alone, not the party's own.
    with pytest.raises(ValidationError, match="who they set out with"):
        updated(authored, world=updated(authored.world, party=[TOMAS]))


def test_a_scenario_is_refused_by_an_engine_it_was_not_authored_for() -> None:
    with pytest.raises(ValueError, match="does not play"):
        _ = begin_game(ENGINES_BUILT[TWENTYFOURXX], "whispering-vault", scenario(), character())


def test_an_authored_actor_without_rules_is_refused() -> None:
    """Loner deviation 2 covers things, not actors: an actor nobody wrote has no sheet to roll."""
    authored = scenario()
    bare = updated(authored.world.require(MARA), rules={})
    stripped = updated(
        authored,
        world=updated(
            authored.world,
            entities={**authored.world.entities, MARA: bare},
        ),
    )

    with pytest.raises(ValueError, match="has no rules"):
        _ = begin_game(ENGINES_BUILT[LONER3E], "whispering-vault", stripped, character())


def test_twentyfourxx_opposition_needs_no_sheet() -> None:
    engine = ENGINES_BUILT[TWENTYFOURXX]
    scenario_id = scenario_for(TWENTYFOURXX)
    authored = load_scenario(SCENARIOS, scenario_id)
    hostile = next(entity for entity in authored.world.of_kind("actor") if entity.rules)
    stripped = updated(
        authored,
        world=updated(
            authored.world,
            entities={**authored.world.entities, hostile.id: updated(hostile, rules={})},
        ),
    )
    player = load_character(CHARACTERS, "kael", engine.id, engine.check_overlay)

    begun = begin_game(engine, scenario_id, stripped, player)

    assert engine.describe(begun, begun.world.require(hostile.id)) == ""


def test_scenario_packs_include_one_srd() -> None:
    with pytest.raises(ValidationError, match="must include 'srd'"):
        updated(scenario(), packs=("ap01-fantasy",))
    with pytest.raises(ValueError, match="duplicate scenario pack ids"):
        updated(scenario(), packs=("srd", "srd"))


def test_a_character_knows_the_gear_they_start_with() -> None:
    with pytest.raises(ValidationError, match="knows the gear they start with"):
        _character(holds=_rope(HELD, known=False))


def _luck(state: Game) -> int:
    return sheet_of(state, PLAYER_ID, Sheet).luck.current


def test_a_rules_mutation_lands_on_the_commit_and_nowhere_else() -> None:
    _, state = initialized()
    draft = state.draft()
    with rules(draft.world.require(PLAYER_ID), Sheet) as sheet:
        sheet.luck.current = 1

    committed = draft.committed()

    assert _luck(committed) == 1
    assert _luck(state) == RULES.luck_max
