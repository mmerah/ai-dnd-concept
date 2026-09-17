import pytest
from support.tunnelgoons import HALL, MIRA, START, small_world

from aidm.core.entities import Refusal
from aidm.engines.base import PLAYER_ID
from aidm.engines.rooms.world import MapDraft, Prop, Way
from aidm.engines.tunnelgoons.world import Goon, GoonSheet, Npc, TunnelGoonsGame, TunnelGoonsWorld

GHOST = "ghost"


def test_begin_refuses_a_draft_whose_npc_stands_in_no_place(world: TunnelGoonsWorld) -> None:
    map_draft = MapDraft[Npc](
        places=world.places, ways=world.ways, npcs=world.npcs, items=world.items, start=START
    )
    map_draft.npcs[MIRA].place = GHOST
    with pytest.raises(Refusal, match="in no place"):
        _ = TunnelGoonsWorld.opening(map_draft, world.player, ())


def test_an_item_on_nothing_is_refused(draft: TunnelGoonsGame) -> None:
    draft.payload.items["stray"] = Prop(
        id="stray", name="Stray", brief="Nobody's", known=True, on=GHOST
    )
    with pytest.raises(Refusal, match="on nothing"):
        _ = draft.commit()


def test_an_npc_in_no_place_is_refused(draft: TunnelGoonsGame) -> None:
    draft.payload.npcs[MIRA].place = GHOST
    with pytest.raises(Refusal, match="no place"):
        _ = draft.commit()


def test_a_way_to_a_non_place_is_refused(draft: TunnelGoonsGame) -> None:
    draft.payload.ways[START].append(Way(to=GHOST))
    with pytest.raises(Refusal, match="not a place"):
        _ = draft.commit()


def test_the_player_stands_at_the_last_visit(draft: TunnelGoonsGame) -> None:
    draft.payload.visits.append(HALL)
    assert draft.commit().payload.current.id == HALL


def test_killing_a_party_member_drops_them_from_the_party(world: TunnelGoonsWorld) -> None:
    world.party.append(MIRA)

    facts = world.kill(MIRA)

    assert world.party == []
    assert not world.npcs[MIRA].alive
    assert any(fact.card == "Mira is dead" for fact in facts)


def test_a_party_member_who_is_not_at_the_players_place_is_refused() -> None:
    world = small_world().payload
    with pytest.raises(ValueError, match="not at their place"):
        TunnelGoonsWorld(
            places=world.places,
            ways=world.ways,
            npcs=world.npcs,
            items=world.items,
            player=world.player,
            visits=[HALL],
            party=[MIRA],
        )


def test_walk_reaches_every_place_along_the_ways(world: TunnelGoonsWorld) -> None:
    assert world.reachable(START) == set(world.places)


def test_frontier_counts_every_unknown_place_reachable_from_here(world: TunnelGoonsWorld) -> None:
    assert world.frontier() == 2


def test_a_goons_rows_put_health_before_the_sheets_rows(world: TunnelGoonsWorld) -> None:
    labels = [label for label, _ in world.player.rows()]

    assert labels == ["Health", "Brute", "Skulker", "Erudite", "Inventory", "Level"]


def test_the_inventory_row_counts_what_the_player_carries(world: TunnelGoonsWorld) -> None:
    held = len(list(world.carried(PLAYER_ID)))
    total = world.player.require_sheet().inventory

    assert dict(world.sheet_rows())["Inventory"] == f"{held}/{total}"
    assert dict(world.player.rows())["Inventory"] == str(total)


def test_the_player_levels_up_their_ability_and_health_with_no_name_prefix() -> None:
    world = small_world().payload
    player = world.player
    sheet = player.require_sheet()
    before_ability = sheet.abilities["brute"]
    before_hp = player.hp.maximum

    facts = player.level("brute", "health")

    assert sheet.abilities["brute"] == before_ability + 1
    assert player.hp.maximum == before_hp + 1
    assert player.hp.current == before_hp + 1
    assert sheet.level == 2
    assert len(facts) == 1
    assert facts[0].card == "Level 2: Brute +1, Health +1"
    assert facts[0].trace == facts[0].card


def test_a_hired_npc_levels_up_their_ability_and_inventory_with_a_name_prefix() -> None:
    world = small_world().payload
    mira = world.npcs[MIRA]
    mira.sheet = GoonSheet(abilities={"brute": 0, "skulker": 0, "erudite": 0})
    before_inventory = mira.require_sheet().inventory

    facts = mira.level("skulker", "inventory")

    assert mira.require_sheet().abilities["skulker"] == 1
    assert mira.require_sheet().inventory == before_inventory + 1
    assert mira.require_sheet().level == 2
    assert len(facts) == 1
    assert facts[0].card == "Mira: Level 2: Skulker +1, Inventory +1"


def test_unpack_kit_seeds_the_player_id_so_an_item_named_player_does_not_collide() -> None:
    goon = Goon(
        id=PLAYER_ID,
        name="Kael",
        brief="A wiry scavenger",
        known=True,
        sheet=GoonSheet(abilities={"brute": 1, "skulker": 1, "erudite": 1}),
        kit=("Player", "Rope", "Torch"),
    )

    items = goon.unpack_kit(())

    ids = [item.id for item in items]
    assert PLAYER_ID not in ids
    assert len(set(ids)) == 3


def test_the_map_so_far_names_who_stands_where_and_every_id_in_use() -> None:
    world = small_world().payload
    shown = world.map_so_far()

    assert "  here: Mira[mira] (met), Lantern[lantern] (met)" in shown
    assert "Robo Mantis" not in shown
    assert shown.endswith(
        "ids in use: crypt, hall, key, lantern, mantis, mira, rope, start, torch, vault"
    )
