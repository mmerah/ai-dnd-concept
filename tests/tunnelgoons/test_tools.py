import asyncio
import re
from random import Random

import pytest
from pydantic import BaseModel
from support.table import change, refused
from support.tunnelgoons import (
    CRYPT,
    HALL,
    KEY,
    LANTERN,
    MANTIS,
    MIRA,
    ROPE,
    START,
    VAULT,
    small_world,
)

from aidm.core.entities import EntityId, Refusal
from aidm.core.model import Check, Generation
from aidm.engines.base import HIRE, PLAYER_ID, SIGNED_ON, Hire
from aidm.engines.rooms.tools import Move
from aidm.engines.rooms.world import Item, Visit
from aidm.engines.tunnelgoons.engine import TunnelGoonsEngine
from aidm.engines.tunnelgoons.tools import ActionRoll, LevelUp
from aidm.engines.tunnelgoons.world import Abilities

ENGINE = TunnelGoonsEngine()
TOTAL_RE = re.compile(r"(-?\d+) vs DS")


def _sheeted(*, brute: int = 0, skulker: int = 0, erudite: int = 0) -> Abilities:
    return Abilities(abilities={"brute": brute, "skulker": skulker, "erudite": erudite})


def _total(card: str) -> int:
    match = TOTAL_RE.search(card)
    assert match is not None
    return int(match.group(1))


def test_the_roll_adds_ability_and_items_and_penalizes_brute_and_skulker_over_inventory() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.player.sheet.abilities["skulker"] = 2
    world.player.sheet.inventory = 1  # carrying rope + torch (2) is 1 over
    facts = ENGINE.roll(
        draft,
        ActionRoll(what="Sneak past", ability="skulker", items=(ROPE,), difficulty=10),
        Random(1),
    )
    rolled = next(fact for fact in facts if fact.kind == "action_rolled")
    dice = rolled.dice[0].rolled
    assert _total(rolled.card) == sum(dice) + world.player.sheet.abilities["skulker"] + 1 - 1


def test_erudite_rolls_are_not_penalized_for_over_inventory() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.player.sheet.abilities["erudite"] = 2
    world.player.sheet.inventory = 1
    facts = ENGINE.roll(
        draft, ActionRoll(what="Read the runes", ability="erudite", difficulty=8), Random(2)
    )
    rolled = next(fact for fact in facts if fact.kind == "action_rolled")
    dice = rolled.dice[0].rolled
    assert _total(rolled.card) == sum(dice) + world.player.sheet.abilities["erudite"]


def test_a_roll_against_an_npc_that_hits_can_slay_it() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.npcs[MANTIS].place = START
    world.player.sheet.abilities["brute"] = 10  # min total 12 always beats DS 4
    facts = ENGINE.roll(
        draft,
        ActionRoll(what="Smash it", ability="brute", against=MANTIS, dangerous=True),
        Random(3),
    )
    mantis = world.npcs[MANTIS]
    assert mantis.hp.current == 0
    assert not mantis.alive
    assert any(fact.kind == "actor_killed" for fact in facts)


def test_an_npc_killed_by_a_roll_drops_what_it_carried_here() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.npcs[MANTIS].place = START
    world.items[KEY].on = MANTIS
    world.player.sheet.abilities["brute"] = 10  # min total 12 always beats DS 4
    facts = ENGINE.roll(
        draft,
        ActionRoll(what="Smash it", ability="brute", against=MANTIS, dangerous=True),
        Random(3),
    )
    assert world.items[KEY].on == START
    assert any(fact.kind == "items_dropped" for fact in facts)


def test_a_miss_against_an_npc_can_kill_the_player() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.npcs[MANTIS].place = START
    world.npcs[MANTIS].hp.maximum = 20
    world.npcs[MANTIS].hp.current = 20  # max total 12 never beats DS 20
    world.player.sheet.abilities["brute"] = 0
    world.player.hp.current = 1
    facts = ENGINE.roll(
        draft,
        ActionRoll(what="Smash it", ability="brute", against=MANTIS, dangerous=True),
        Random(4),
    )
    assert world.player.hp.current == 0
    assert not world.player.alive
    assert ENGINE.over(draft) == "You died."
    assert any(fact.kind == "actor_killed" for fact in facts)


def test_a_roll_against_an_npc_wounds_nobody_unless_it_is_dangerous() -> None:
    """SRD: only a dangerous action turns the margin into damage; talk against a DS does not."""
    draft = small_world().draft()
    world = draft.payload
    world.npcs[MANTIS].place = START
    facts = ENGINE.roll(
        draft, ActionRoll(what="Talk it down", ability="erudite", against=MANTIS), Random(3)
    )
    assert world.npcs[MANTIS].hp.current == world.npcs[MANTIS].hp.maximum
    assert world.player.hp.current == world.player.hp.maximum
    assert not any(fact.kind == "counter_changed" for fact in facts)


def test_dangerous_hurts_only_on_a_miss() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.player.sheet.abilities["erudite"] = 12  # min total 14 always beats DS 8
    before = world.player.hp.current
    facts = ENGINE.roll(
        draft,
        ActionRoll(what="Cross the gap", ability="erudite", difficulty=8, dangerous=True),
        Random(0),
    )
    assert world.player.hp.current == before
    assert not any(fact.kind == "counter_changed" for fact in facts)

    draft2 = small_world().draft()
    world2 = draft2.payload
    world2.player.sheet.inventory = 0
    world2.items.update(
        {
            EntityId(f"junk-{n}"): Item(
                id=EntityId(f"junk-{n}"),
                name=f"Junk {n}",
                brief="Clutter",
                known=True,
                on=PLAYER_ID,
            )
            for n in range(11)
        }
    )  # carried (13) - inventory (0) = 13 penalty, always below any legal DS
    facts2 = ENGINE.roll(
        draft2,
        ActionRoll(what="Cross the gap", ability="brute", difficulty=8, dangerous=True),
        Random(0),
    )
    assert world2.player.hp.current < world2.player.hp.maximum
    assert any(fact.kind == "counter_changed" for fact in facts2)


def test_neither_or_both_of_difficulty_and_against_is_refused() -> None:
    with pytest.raises(ValueError, match="not both/neither"):
        ActionRoll(what="Push", ability="brute")
    with pytest.raises(ValueError, match="not both/neither"):
        ActionRoll(what="Push", ability="brute", difficulty=8, against=MANTIS)


def test_an_item_not_in_the_players_hands_is_refused() -> None:
    draft = small_world().draft()
    with pytest.raises(Refusal, match="not in Kael's hands"):
        _ = ENGINE.roll(
            draft,
            ActionRoll(what="Pick lock", ability="skulker", items=(KEY,), difficulty=8),
            Random(0),
        )


def test_rest_heals_the_player() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.player.hp.current = 4
    facts = change(ENGINE, draft, "rest")
    assert world.player.hp.current == world.player.hp.maximum
    assert any(fact.kind == "rested" for fact in facts)


def test_level_up_with_no_args_opens_the_six_option_decision() -> None:
    draft = small_world().draft()
    facts = ENGINE.level_up(draft, LevelUp(), Random(0))
    assert facts == []
    assert draft.pending is not None
    assert len(draft.pending.options) == 6


def test_level_up_with_both_raises_the_ability_and_the_boost_and_the_level() -> None:
    draft = small_world().draft()
    world = draft.payload
    before = world.player.sheet.level
    facts = ENGINE.level_up(draft, LevelUp(ability="brute", boost="health"), Random(0))
    assert world.player.sheet.abilities["brute"] == 2
    assert world.player.sheet.level == before + 1
    assert any(fact.kind == "levelled_up" for fact in facts)


def test_level_up_with_one_argument_is_refused() -> None:
    draft = small_world().draft()
    with pytest.raises(Refusal, match="takes both"):
        _ = ENGINE.level_up(draft, LevelUp(ability="brute"), Random(0))


def test_move_refuses_a_locked_way() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.visits.append(Visit(place=HALL))
    with pytest.raises(Refusal, match="locked"):
        _ = ENGINE.move(draft, Move(to_id=VAULT), Random(0))


def test_move_refuses_when_there_is_no_way() -> None:
    draft = small_world().draft()
    with pytest.raises(Refusal, match="no way leads"):
        _ = ENGINE.move(draft, Move(to_id=CRYPT), Random(0))


def test_move_reveals_the_destination_and_adds_a_visit() -> None:
    draft = small_world().draft()
    world = draft.payload
    before = len(world.visits)
    facts = ENGINE.move(draft, Move(to_id=VAULT), Random(0))
    assert world.current.id == VAULT
    assert world.places[VAULT].known
    assert len(world.visits) == before + 1
    assert any(fact.kind == "arrived" for fact in facts)


def test_move_with_ids_brings_an_npc_here_and_refuses_one_standing_elsewhere() -> None:
    draft = small_world().draft()
    world = draft.payload
    facts = ENGINE.move(draft, Move(to_id=VAULT, with_ids=(MIRA,)), Random(0))
    assert world.npcs[MIRA].place == VAULT
    assert any("Mira" in fact.trace for fact in facts if fact.kind == "arrived")

    elsewhere = small_world().draft()
    with pytest.raises(Refusal, match="not here"):
        _ = ENGINE.move(elsewhere, Move(to_id=VAULT, with_ids=(MANTIS,)), Random(0))


def test_unlock_way_then_move_passes() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.visits.append(Visit(place=HALL))
    _ = change(ENGINE, draft, "unlock_way", to_id=VAULT)
    facts = ENGINE.move(draft, Move(to_id=VAULT), Random(0))
    assert world.current.id == VAULT
    assert any(fact.kind == "arrived" for fact in facts)


def test_move_item_to_the_player_to_an_npc_here_and_to_the_place() -> None:
    draft = small_world().draft()
    world = draft.payload

    _ = change(ENGINE, draft, "move_item", item_id=LANTERN, to=MIRA)
    assert world.items[LANTERN].on == MIRA

    _ = change(ENGINE, draft, "move_item", item_id=LANTERN, to=PLAYER_ID)
    assert world.items[LANTERN].on == PLAYER_ID

    _ = change(ENGINE, draft, "move_item", item_id=LANTERN, to=START)
    assert world.items[LANTERN].on == START


def test_move_item_refuses_a_holder_the_player_has_not_met() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.npcs[MANTIS].place = START
    with pytest.raises(Refusal, match="has not met"):
        _ = change(ENGINE, draft, "move_item", item_id=LANTERN, to=MANTIS)


def test_kill_drops_an_npcs_items_loose() -> None:
    draft = small_world().draft()
    world = draft.payload
    blade = EntityId("mira-blade")
    world.items[blade] = Item(id=blade, name="Blade", brief="Mira's blade", known=True, on=MIRA)

    _ = change(ENGINE, draft, "kill", entity_id=MIRA)

    assert not world.npcs[MIRA].alive
    assert world.items[blade].on == START


def test_reveal_only_what_is_here_and_unknown() -> None:
    draft = small_world().draft()
    world = draft.payload

    assert "not here" in refused(ENGINE, draft, "reveal", entity_id=KEY)
    assert "already" in refused(ENGINE, draft, "reveal", entity_id=LANTERN)

    world.npcs[MANTIS].place = START
    _ = change(ENGINE, draft, "reveal", entity_id=MANTIS)
    assert world.npcs[MANTIS].known


def test_action_roll_a_member_rolls_on_their_own_abilities_and_items() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.npcs[MIRA].sheet = _sheeted(skulker=2)
    world.party.append(MIRA)
    world.items[ROPE].on = MIRA
    facts = ENGINE.roll(
        draft,
        ActionRoll(
            what="Sneak past", ability="skulker", items=(ROPE,), difficulty=10, actor_id=MIRA
        ),
        Random(1),
    )
    rolled = next(fact for fact in facts if fact.kind == "action_rolled")
    dice = rolled.dice[0].rolled
    assert _total(rolled.card) == sum(dice) + 2 + 1
    assert "Mira" in rolled.card


def test_action_roll_refuses_rolling_against_oneself() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.npcs[MIRA].sheet = _sheeted()
    world.party.append(MIRA)
    with pytest.raises(Refusal, match="cannot roll against themselves"):
        _ = ENGINE.roll(
            draft,
            ActionRoll(what="Wrestle", ability="brute", against=MIRA, actor_id=MIRA),
            Random(0),
        )


def test_a_members_miss_damages_them_and_kills_them_at_zero() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.npcs[MIRA].sheet = _sheeted()
    world.npcs[MIRA].hp.current = 1
    world.party.append(MIRA)
    facts = ENGINE.roll(
        draft,
        ActionRoll(
            what="Leap the gap", ability="brute", difficulty=20, dangerous=True, actor_id=MIRA
        ),
        Random(0),
    )
    assert world.npcs[MIRA].hp.current == 0
    assert not world.npcs[MIRA].alive
    assert any(fact.kind == "actor_killed" for fact in facts)


def test_rest_heals_a_member() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.npcs[MIRA].sheet = _sheeted()
    world.npcs[MIRA].hp.current = 2
    world.party.append(MIRA)
    facts = change(ENGINE, draft, "rest")
    assert world.npcs[MIRA].hp.current == world.npcs[MIRA].hp.maximum
    assert any(fact.kind == "counter_changed" and "Mira" in fact.card for fact in facts)


def test_level_up_for_the_player_opens_the_members_decision() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.npcs[MIRA].sheet = _sheeted()
    world.party.append(MIRA)

    facts = ENGINE.level_up(draft, LevelUp(ability="brute", boost="health"), Random(0))
    assert any(fact.kind == "levelled_up" for fact in facts)
    assert draft.pending is not None
    assert draft.pending.options[0].args["actor_id"] == MIRA

    draft.pending = None
    facts2 = ENGINE.level_up(
        draft, LevelUp(ability="skulker", boost="health", actor_id=MIRA), Random(0)
    )
    assert any(fact.kind == "levelled_up" for fact in facts2)
    assert draft.pending is None


def test_require_actor_refuses_an_unsheeted_member() -> None:
    draft = small_world().draft()
    world = draft.payload
    world.party.append(MIRA)
    with pytest.raises(Refusal, match="is not the player or a hired party member"):
        _ = world.require_actor(MIRA)


def test_hire_sets_generation_and_ends_the_turn() -> None:
    draft = small_world().draft()
    facts = ENGINE.hire(draft, Hire(entity_id=MIRA, terms="Watch our backs"), Random(0))
    assert draft.generation == Generation(operation=HIRE, brief="Watch our backs", target=MIRA)
    assert any(fact.kind == "hire_asked" for fact in facts)


def test_hire_refuses_a_sheeted_npc() -> None:
    draft = small_world().draft()
    draft.payload.npcs[MIRA].sheet = _sheeted()
    with pytest.raises(Refusal, match="already carries a sheet"):
        _ = ENGINE.hire(draft, Hire(entity_id=MIRA, terms="terms"), Random(0))


def test_validate_refuses_a_stale_hire_target() -> None:
    draft = small_world().draft()
    draft.generation = Generation(operation=HIRE, brief="terms", target=MIRA)
    draft.payload.npcs[MIRA].sheet = _sheeted()
    with pytest.raises(Refusal, match="already carries a sheet"):
        ENGINE.validate(draft)


async def _stub_worldsmith[M: BaseModel](prompt: str, model: type[M], refusal: Check[M]) -> M:
    del prompt, refusal
    return model.model_validate({"abilities": {"brute": 2, "skulker": 1, "erudite": 0}})


def test_advance_on_a_hire_installs_the_sheet_and_joins_the_party() -> None:
    draft = small_world().draft()
    generation = Generation(operation=HIRE, brief="Watch our backs", target=MIRA)
    facts, told = asyncio.run(ENGINE.advance(draft, generation, _stub_worldsmith))
    member = draft.payload.npcs[MIRA]
    assert member.sheet is not None
    assert member.sheet.abilities == {"brute": 2, "skulker": 1, "erudite": 0}
    assert MIRA in draft.payload.party
    assert told == SIGNED_ON.format(name=member.name)
    assert any(fact.kind == "hired" for fact in facts)
