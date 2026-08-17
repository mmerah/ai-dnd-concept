import json
import re
from pathlib import Path
from typing import get_args

import pytest
from core_test_support import (
    LONER3E,
    begin_game,
    character,
    initialized,
    scenario,
    updated,
    with_entity,
)
from pydantic import ValidationError

import aidm.state.apply
import aidm.state.world
from aidm.content.authored import (
    Character,
    CharacterOverlay,
    CharacterProfile,
    ScenarioWorld,
    check_hooks,
)
from aidm.engines.loner3e.mechanics import LUCK_MAX, Mechanics
from aidm.state.base import PLAYER_ID, Entity, EntityId
from aidm.state.world import CONNECTED, GameState, Hook, HookFactKind, HookMatch, Relation

HELD = EntityId("frayed_rope")
UNHELD = EntityId("silk_rope")
MARA = EntityId("mara")
ELENA = EntityId("elena")
_HALL = {"id": "hall", "kind": "location", "name": "the hall", "brief": "A hall.", "known": True}
_DOUBLED = json.dumps(
    {
        "meta": {"title": "Twice Over", "premise": "One id, authored twice."},
        "starting_location_id": "hall",
        "entities": [_HALL, {**_HALL, "name": "the hall again"}],
    }
)


def _character(*, holds: Entity, gear_for: EntityId) -> Character:
    return Character(
        id="test-character",
        engine=LONER3E,
        profile=CharacterProfile(
            name="Test Character",
            brief="A character built only for this test.",
            items=(holds,),
        ),
        overlay=CharacterOverlay(character={}, entities={gear_for: {}}),
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
    player = state.world.require(PLAYER_ID)
    with pytest.raises(ValidationError, match="keys disagree"):
        type(state.world).model_validate(
            {"entities": {"wrong-key": player.model_dump(round_trip=True)}}
        )

    with pytest.raises(ValidationError, match="player entity must be known"):
        with_entity(state, updated(state.player, known=False))

    with pytest.raises(ValidationError, match="not in a valid location"):
        with_entity(state, updated(state.player, parent_id=EntityId("missing")))

    carried = state.world.children(PLAYER_ID, "item")[0]
    with pytest.raises(ValidationError, match="cannot be inside anything"):
        with_entity(state, updated(carried, kind="location"))


def test_an_engine_refuses_an_authored_payload_it_cannot_read() -> None:
    """Only actors carry engine mechanics now, so the overlay's forbid-extra guard fires on one of
    them — and it has to fire at launch, not on the turn that first reads the entity."""
    engine, _ = initialized()
    authored = scenario()
    entities = authored.world.world.entities.values()
    actor = next(entity for entity in entities if entity.kind == "actor")
    poisoned = updated(authored, overlay={"entities": {actor.id: {"gear": None}}})

    with pytest.raises(ValueError, match="gear"):
        begin_game(engine, poisoned, character())


def test_scenario_topology_is_validated() -> None:
    with pytest.raises(ValidationError, match="starting_location_id"):
        updated(scenario().world, starting_location_id=EntityId("missing"))
    with pytest.raises(ValidationError, match="duplicate entity ids"):
        # Keyed by id from a flat array, so the duplicate has to be caught before it collapses.
        ScenarioWorld.model_validate_json(_DOUBLED)


def test_a_location_no_walk_reaches_is_refused() -> None:
    world = scenario().world
    undercroft = Entity(
        id=EntityId("undercroft"),
        kind="location",
        name="the undercroft",
        brief="A chamber no passage names.",
        known=False,
    )
    with pytest.raises(ValidationError, match=r"no walk.*undercroft"):
        updated(world, entities=(*world.entities, undercroft))


def test_a_known_location_no_known_way_reaches_is_refused() -> None:
    """Reachable through an unknown way, so only the stricter known-way rule can catch it."""
    world = scenario().world
    chapel = Entity(
        id=EntityId("chapel"),
        kind="location",
        name="the chapel",
        brief="A chapel the premise names.",
        known=True,
    )
    way = Relation(
        kind=CONNECTED, source=world.starting_location_id, target=chapel.id, directed=False
    )
    with pytest.raises(ValidationError, match=r"knows of but no known way.*chapel"):
        updated(world, entities=(*world.entities, chapel), relations=(*world.relations, way))


def test_a_hook_waiting_on_an_unauthored_id_is_refused() -> None:
    world = scenario().world
    ghost = Hook(
        id="ghost-sighted", match=HookMatch(kind="entity_discovered", data={"entity_id": "ghost"})
    )
    with pytest.raises(ValidationError, match=r"never fire.*ghost"):
        updated(world, hooks=(*world.hooks, ghost))


def test_a_hook_effect_naming_an_unauthored_id_is_refused() -> None:
    engine, _ = initialized()
    world = scenario().world
    haunted = Hook(
        id="vault-haunted",
        match=HookMatch(kind="entity_discovered", data={"entity_id": "vault"}),
        effects=({"name": "reveal", "args": {"entity_id": "ghost"}},),
    )
    with pytest.raises(ValueError, match=r"vault-haunted.*reveal.*entity_id='ghost'"):
        check_hooks(updated(world, hooks=(*world.hooks, haunted)), engine.binding())


def test_a_hook_waiting_on_a_kind_core_never_emits_is_refused() -> None:
    with pytest.raises(ValidationError, match="entity_discoverd"):
        _ = HookMatch.model_validate({"kind": "entity_discoverd"})


_FACT_KIND_PATTERNS = (
    # Fact(source=CORE, kind="...") and the second argument of *_fact(entity, "...") helpers.
    re.compile(r'Fact\([^)]*?kind="([a-z_]+)"'),
    re.compile(r'_fact\(\s*[\w.]+,\s*"([a-z_]+)"'),
)
_UNMATCHABLE = {"hook_fired", "hook_failed", "hooks_capped"}


def test_the_hookable_set_tracks_the_kinds_core_actually_emits() -> None:
    """A kind added to core's world ops goes into `HookFactKind`, or is unmatchable here."""
    sources = (Path(aidm.state.world.__file__), Path(aidm.state.apply.__file__))
    emitted = {
        kind
        for source in sources
        for pattern in _FACT_KIND_PATTERNS
        for kind in pattern.findall(source.read_text())
    }
    assert emitted == set(get_args(HookFactKind.__value__)) | _UNMATCHABLE


def test_a_scenario_starts_the_party_it_authors() -> None:
    """A scenario holds no player, so the tie to one is named as an id and made at composition."""
    engine, _ = initialized()
    authored = scenario()
    started = updated(authored, world=updated(authored.world, starting_party=(MARA,)))

    assert begin_game(engine, started, character()).world.party() == (MARA,)
    with pytest.raises(ValidationError, match="who they set out with"):
        updated(authored.world, starting_party=(ELENA,))


def test_an_overlay_may_not_name_an_entity_the_author_never_wrote() -> None:
    """An overlay keys off authored ids, so a typo must fail at load, not go silently unread."""
    with pytest.raises(ValidationError, match="unauthored ids"):
        _character(holds=_rope(HELD), gear_for=UNHELD)


def test_a_character_knows_the_gear_they_start_with() -> None:
    """Unknown carried gear would be hidden canon inside the inventory the Narrator is shown."""
    with pytest.raises(ValidationError, match="knows the gear they start with"):
        _character(holds=_rope(HELD, known=False), gear_for=HELD)


def _luck(state: GameState) -> int:
    return state.mechanics_as(Mechanics).sheets[PLAYER_ID].luck.current


def test_two_reads_in_one_draft_share_one_live_mechanics() -> None:
    _, state = initialized()
    draft = state.draft()

    assert draft.mechanics_as(Mechanics) is draft.mechanics_as(Mechanics)


def test_a_mutation_with_no_write_back_survives_the_commit() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.mechanics_as(Mechanics).sheets[PLAYER_ID].luck.current = 1

    committed = draft.committed()

    assert _luck(committed) == 1
    assert Mechanics.model_validate(committed.mechanics).sheets[PLAYER_ID].luck.current == 1


def test_a_mutation_against_a_committed_state_reaches_no_save_or_draft() -> None:
    _, state = initialized()
    state.mechanics_as(Mechanics).sheets[PLAYER_ID].luck.current = 1

    saved = Mechanics.model_validate(state.model_dump()["mechanics"])

    assert saved.sheets[PLAYER_ID].luck.current == LUCK_MAX
    assert _luck(state.draft()) == LUCK_MAX
