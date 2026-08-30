import json
from pathlib import Path
from random import Random

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
    loner_sheet,
    scenario,
    scenario_for,
    updated,
    with_entity,
    with_world,
)
from pydantic import ValidationError

from aidm.content.io import load_character, load_scenario
from aidm.engines.core import rules
from aidm.engines.loner3e.rules import LUCK_MAX, Loner3eState
from aidm.engines.twentyfourxx.rules import TwentyfourxxState
from aidm.state.entities import PLAYER_ID, Entity, EntityId
from aidm.state.facts import Fact
from aidm.state.model import Character, CharacterPayload, Game
from aidm.state.tools import apply_to_draft
from aidm.world.topology import children, validate_rooms

HERE = "HERE WITH THE PLAYER"
HELD = EntityId("frayed-rope")
MARA = EntityId("mara")
ELENA = EntityId("elena")
TOMAS = EntityId("tomas")


def _character(*, holds: Entity) -> Character:
    return Character(
        id="test-character",
        engine=LONER3E,
        name="Test Character",
        brief="A character built only for this test.",
        payload=CharacterPayload(items=(holds,)),
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
        _ = load_scenario(tmp_path, "doubled", ENGINES_BUILT[LONER3E])


def test_world_and_game_state_reject_inconsistent_topology() -> None:
    _, state = initialized()
    misfiled = state.world.require(PLAYER_ID).model_dump(round_trip=True)
    with pytest.raises(ValidationError, match="filed under"):
        type(state.world).model_validate({"entities": {"someone-else": misfiled}})

    with pytest.raises(ValueError, match="player entity must be known"):
        with_entity(state, updated(state.player, known=False))

    with pytest.raises(ValidationError, match="unknown entity id"):
        with_entity(state, updated(state.player, parent_id=EntityId("missing")))

    carried = children(state.world, PLAYER_ID, "item")[0]
    with pytest.raises(ValidationError, match="inside itself"):
        with_entity(state, updated(state.player, parent_id=carried.id))

    with pytest.raises(ValueError, match="cannot be inside anything"):
        validate_rooms(with_entity(state, updated(carried, kind="location")).world)


def test_an_engine_refuses_an_authored_payload_it_cannot_read() -> None:
    engine, state = initialized()
    draft = state.draft()
    draft.world.mechanics = {"sheets": {PLAYER_ID: {"gear": None}}}

    with pytest.raises(ValueError, match=r"^mechanics\.sheets\.player\.gear: "):
        engine.validate(draft)


def test_the_rooms_rules_reject_broken_exits_and_party() -> None:
    world = scenario().world
    study = world.require(EntityId("study"))
    exposed = updated(study, exits=(*study.exits, {"to": "bell-tower", "known": True}))
    with pytest.raises(ValueError, match="has not met"):
        validate_rooms(updated(world, entities={**world.entities, study.id: exposed}))

    with pytest.raises(ValueError, match="without being met"):
        validate_rooms(updated(world, party=(ELENA,)))

    mara = world.require(MARA)
    wandering = updated(mara, exits=({"to": "study"},))
    with pytest.raises(ValueError, match="cannot have exits"):
        validate_rooms(updated(world, entities={**world.entities, mara.id: wandering}))


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
    started = with_world(authored, updated(authored.world, party=[MARA]))

    begun = begin_game(engine, "whispering-vault", started, character())
    assert begun.world.party == [MARA]
    # Tomas is known and unique, so this is the stands-at-start check alone, not the party's own.
    apart = with_world(authored, updated(authored.world, party=[TOMAS]))
    unmet = engine.authoring_brief(apart.packs, None, False).unmet(apart)
    assert unmet == ["every starting party member in 'study', unlike ['tomas']"]


def test_a_game_is_refused_a_scenario_or_a_character_from_another_engine() -> None:
    twentyfourxx = ENGINES_BUILT[TWENTYFOURXX]
    with pytest.raises(ValueError, match="does not play"):
        _ = begin_game(twentyfourxx, "whispering-vault", scenario(), character())

    theirs = scenario_for(TWENTYFOURXX)
    with pytest.raises(ValueError, match="is written for the 'loner3e' rules"):
        _ = begin_game(
            twentyfourxx, theirs, load_scenario(SCENARIOS, theirs, twentyfourxx), character()
        )


def test_a_character_file_belongs_to_its_folder_and_its_engine(tmp_path: Path) -> None:
    written = character().model_dump_json()
    (tmp_path / "kael").mkdir()
    _ = (tmp_path / "kael" / f"{TWENTYFOURXX}.json").write_text(written, encoding="utf-8")
    (tmp_path / "mira").mkdir()
    _ = (tmp_path / "mira" / f"{LONER3E}.json").write_text(written, encoding="utf-8")

    with pytest.raises(ValueError, match="plays 'loner3e', not 'twentyfourxx'"):
        _ = load_character(tmp_path, "kael", ENGINES_BUILT[TWENTYFOURXX])
    with pytest.raises(ValueError, match="'kael' is filed under 'mira'"):
        _ = load_character(tmp_path, "mira", ENGINES_BUILT[LONER3E])


def test_an_authored_actor_without_rules_is_refused() -> None:
    """Loner deviation 2 covers things, not actors: an actor nobody wrote has no sheet to roll."""
    engine, authored = ENGINES_BUILT[LONER3E], scenario()
    stripped = with_world(
        authored,
        updated(
            authored.world,
            mechanics=engine.mechanics_patch(authored.world.mechanics, {}, (MARA,)),
        ),
    )

    with pytest.raises(ValueError, match="has no sheet"):
        _ = begin_game(engine, "whispering-vault", stripped, character())


def test_twentyfourxx_opposition_needs_no_sheet() -> None:
    engine = ENGINES_BUILT[TWENTYFOURXX]
    scenario_id = scenario_for(TWENTYFOURXX)
    authored = load_scenario(SCENARIOS, scenario_id, engine)
    hostile_id = next(iter(TwentyfourxxState.model_validate(authored.world.mechanics).sheets))
    stripped = with_world(
        authored,
        updated(
            authored.world,
            mechanics=engine.mechanics_patch(authored.world.mechanics, {}, (hostile_id,)),
        ),
    )
    player = load_character(CHARACTERS, "kael", engine)

    begun = begin_game(engine, scenario_id, stripped, player)

    here = dict(engine.scene(begun).director_sections)[HERE]
    # One entity's block: its headline and the lines indented under it, mechanics included.
    block = next(one for one in here.split("\n- ") if f"[{hostile_id}]" in one)
    assert "state:" not in block


def test_a_character_knows_the_gear_they_start_with() -> None:
    with pytest.raises(ValidationError, match="knows the gear they start with"):
        _character(holds=_rope(HELD, known=False))


def _luck(state: Game) -> int:
    return loner_sheet(state, PLAYER_ID).luck.current


def test_a_rules_mutation_lands_on_the_commit_and_nowhere_else() -> None:
    _, state = initialized()
    draft = state.draft()
    with rules(draft.world, Loner3eState) as game:
        game.sheets[PLAYER_ID].luck.current = 1

    committed = draft.committed()

    assert _luck(committed) == 1
    assert _luck(state) == LUCK_MAX


def test_a_told_fact_about_an_unmet_or_unknown_entity_is_refused() -> None:
    engine, state = initialized()
    leak = Fact(kind="entity_moved", trace="Elena moved", told=True, entity_id=ELENA)

    with pytest.raises(ValueError, match="has not met"):
        _ = apply_to_draft(engine.validate, state.draft(), lambda _draft, _rng: (leak,), Random(0))

    nobody = Fact(
        kind="entity_moved", trace="a ghost moved", told=True, entity_id=EntityId("ghost")
    )

    with pytest.raises(ValueError, match="does not hold"):
        _ = apply_to_draft(
            engine.validate, state.draft(), lambda _draft, _rng: (nobody,), Random(0)
        )


def test_a_raw_dict_payload_is_refused_before_it_can_vanish() -> None:
    """`SerializeAsAny[BaseModel]` would swallow a dict whole; the guard is the only defence."""
    state = initialized()[1]
    with pytest.raises(ValidationError, match="parses the payload"):
        _ = Game.model_validate(state.model_dump(mode="json"))
    with pytest.raises(ValidationError, match="parses the payload"):
        _ = Character.model_validate(character().model_dump(mode="json"))


def test_a_save_whose_payload_the_engine_rejects_is_refused() -> None:
    engine, state = initialized()
    raw = state.model_dump(mode="json")
    raw["payload"]["world"]["entities"]["ghost"] = {"kind": "actor"}
    with pytest.raises(ValidationError):
        _ = engine.restored(json.dumps(raw))
