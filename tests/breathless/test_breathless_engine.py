from random import Random

import pytest
from breathless_test_support import item_sheet, sheet
from core_test_support import game

from aidm.engines.breathless.rules import (
    RULES,
    Breathe,
    BreathlessState,
    ChangeStress,
    Check,
    ItemSheet,
    LootCheck,
    Sheet,
    apply_catch_breath,
    apply_change_stress,
    apply_use_med_kit,
    breathers,
    loot_die,
    med_kit_holders,
    outcome_for,
    resolve_check,
    resolve_loot,
)
from aidm.engines.core import play_action, rules
from aidm.state.entities import PLAYER_ID, EngineId, Entity, EntityId
from aidm.state.model import Game
from aidm.state.tools import apply_to_draft
from aidm.world import actions
from aidm.world.topology import player_location

BREATHLESS = EngineId("breathless")
LANTERN = EntityId("lantern")


def _check(**changes: object) -> Check:
    base: dict[str, object] = {
        "actor_id": PLAYER_ID,
        "goal": "slip past the crawlers",
        "risk": "they hear you",
        "dangerous": True,
        "skill": "Sneak",
    }
    return Check.model_validate(base | changes)


def _sheet(state: Game) -> Sheet:
    return sheet(state, PLAYER_ID)


def test_outcome_bands_and_loot_ratings() -> None:
    assert [outcome_for(n) for n in (1, 2, 3, 4, 5, 12)] == [
        "fail",
        "fail",
        "mixed",
        "mixed",
        "success",
        "success",
    ]
    assert [loot_die(n) for n in (5, 6, 7, 8, 9, 10, 11, 12)] == [6, 6, 8, 8, 10, 10, 12, 12]


def test_a_check_wears_the_skill_down_to_the_floor_and_breath_resets_it() -> None:
    engine, state = game(BREATHLESS)
    draft = state.draft()
    facts = resolve_check(draft, _check(), Random(1))
    assert any(fact.kind == "check_resolved" and fact.card for fact in facts)
    for _ in range(3):
        _ = resolve_check(draft, _check(), Random(1))
    assert _sheet(draft).worn["Sneak"] == RULES.floor
    assert _sheet(draft).skills["Sneak"] == 10
    engine.validate(draft)

    landed = draft.committed()
    assert [label for label, _ in breathers(landed)] == ["Catch your breath"]
    after, facts = play_action(engine, landed, "catch_breath", {"actor_id": PLAYER_ID}, Random(0))
    assert _sheet(after).worn["Sneak"] == 10
    assert "complication" in after.world.pending_notes[-1]
    assert breathers(after) == ()


def test_an_item_rolls_in_place_of_a_skill_and_fades_at_d4() -> None:
    engine, state = game(BREATHLESS)
    draft = state.draft()
    assert item_sheet(draft, LANTERN).die == RULES.starting_item
    for _ in range(3):
        _ = resolve_check(draft, _check(skill="", item_id=LANTERN), Random(1))
    assert item_sheet(draft, LANTERN).die == RULES.floor
    # Broken, lost, or faded: it lies where Kael stands and no longer fills a slot.
    assert draft.world.require(LANTERN).parent_id == player_location(draft)
    draft.world.require(LANTERN).parent_id = PLAYER_ID
    with pytest.raises(ValueError, match="rolls no more"):
        _ = resolve_check(draft, _check(skill="", item_id=LANTERN), Random(1))
    engine.validate(draft)


def test_a_stunt_is_a_d12_once_until_breath() -> None:
    _, state = game(BREATHLESS)
    draft = state.draft()
    facts = resolve_check(draft, _check(skill="", stunt=True), Random(1))
    rolled = next(fact for fact in facts if fact.kind == "check_resolved")
    assert rolled.dice[0].faces == (12,)
    with pytest.raises(ValueError, match="catch their breath"):
        _ = resolve_check(draft, _check(skill="", stunt=True), Random(1))
    _ = apply_catch_breath(draft, Breathe(actor_id=PLAYER_ID))
    assert not _sheet(draft).stunted


def test_a_vulnerable_actor_failing_a_dangerous_check_is_flagged() -> None:
    _, state = game(BREATHLESS)
    draft = state.draft()
    facts = apply_change_stress(draft, ChangeStress(actor_id=PLAYER_ID, amount=4, why="the horde"))
    assert [fact.kind for fact in facts] == ["counter_changed", "vulnerable"]
    # Seed 3 fails a d4 Bash roll.
    failed = resolve_check(draft, _check(skill="Bash"), Random(3))
    rolled = next(fact for fact in failed if fact.kind == "check_resolved")
    assert rolled.card.startswith("Check — fail")
    assert "taken out, or dead" in rolled.trace


def test_loot_finds_trouble_or_an_item_or_a_med_kit_and_wears_the_loot_die() -> None:
    engine, state = game(BREATHLESS)
    draft = state.draft()
    notes = len(draft.world.pending_notes)
    # Seed 0 on a d12 rolls high: an item; the die then stands at d10.
    scavenge = LootCheck(actor_id=PLAYER_ID, seeking="a crowbar")
    # Through the draft gate, so the find is refused or committed exactly as it is in play.
    facts = apply_to_draft(
        engine.validate, draft, lambda d, rng: resolve_loot(d, scavenge, rng), Random(0)
    )
    crowbar = draft.world.require(EntityId("a-crowbar"))
    assert crowbar.parent_id == PLAYER_ID
    found = next(f for f in facts if f.kind == "loot_found")
    kept = int(found.dice[0].result)
    assert item_sheet(draft, crowbar.id).die == loot_die(kept)
    assert _sheet(draft).loot == 10

    # Seed 5 rolls a 10 on the d10: the player chooses between the item and a med kit.
    _ = resolve_loot(draft, LootCheck(actor_id=PLAYER_ID, seeking="bandages"), Random(5))
    assert draft.pending is not None and draft.pending.kind == "loot"
    med_kit = next(one for one in draft.pending.options if one.id == "med-kit")
    found = engine.tool(med_kit.call.name)
    assert found is not None
    _ = found.call(draft, med_kit.call.args, Random(0))
    draft.pending = None
    assert _sheet(draft).med_kit
    assert draft.world.find(EntityId("bandages")) is None

    # Seed 6 rolls a 2 on the d8: trouble is here.
    trouble = resolve_loot(draft, LootCheck(actor_id=PLAYER_ID, seeking="a rifle"), Random(6))
    assert draft.world.find(EntityId("a-rifle")) is None
    assert len(draft.world.pending_notes) == notes + 1
    assert any(fact.kind == "loot_found" for fact in trouble)
    engine.validate(draft)


def test_a_full_backpack_leaves_the_find_on_the_ground_and_refuses_a_fourth_in_hand() -> None:
    engine, state = game(BREATHLESS)
    draft = state.draft()
    for name in ("a bat", "a pipe"):
        item = Entity(
            id=EntityId(name.replace(" ", "-")),
            kind="item",
            name=name,
            brief=name,
            known=True,
            parent_id=PLAYER_ID,
        )
        _ = draft.add(item)
        with rules(draft.world, BreathlessState) as blob:
            blob.items[item.id] = ItemSheet(die=6)
    engine.validate(draft)
    scavenge = LootCheck(actor_id=PLAYER_ID, seeking="a saw")
    # Seed 0 finds an item; the backpack is full, so it lies at the player's location.
    _ = apply_to_draft(
        engine.validate, draft, lambda d, rng: resolve_loot(d, scavenge, rng), Random(0)
    )
    assert draft.world.require(EntityId("a-saw")).parent_id == player_location(draft)
    with pytest.raises(ValueError, match="backpack holds 3"):
        _ = actions.move(draft, EntityId("a-saw"), PLAYER_ID) and engine.validate(draft)
    # An item is its die: one the blob rates none is not a Breathless item.
    draft = state.draft()
    _ = draft.add(
        Entity(
            id=EntityId("a-brick"),
            kind="item",
            name="a brick",
            brief="a brick",
            parent_id=player_location(draft),
        )
    )
    with pytest.raises(ValueError, match="die"):
        engine.validate(draft)


def test_a_helper_rolls_too_and_shares_the_danger() -> None:
    _, state = game(BREATHLESS)
    draft = state.draft()
    wren = EntityId("wren-halloway")
    draft.world.require(wren).parent_id = player_location(draft)
    draft.world.require(wren).known = True
    with rules(draft.world, BreathlessState) as blob:
        blob.sheets[wren].stress.current = 4
    helped = _check(skill="Bash", helper_id=wren, helper_skill="Think")
    # Seed 2 fails the d4+d10 pool.
    facts = resolve_check(draft, helped, Random(2))
    rolled = next(fact for fact in facts if fact.kind == "check_resolved")
    assert len(rolled.dice[0].faces) == 2
    assert sheet(draft, wren).worn["Think"] == 8
    assert rolled.card.startswith("Check — fail")
    assert "Wren Halloway is vulnerable" in rolled.trace


def test_a_med_kit_clears_two_stress_and_is_offered_only_when_useful() -> None:
    engine, state = game(BREATHLESS)
    draft = state.draft()
    _ = apply_change_stress(draft, ChangeStress(actor_id=PLAYER_ID, amount=3, why="a bite"))
    assert med_kit_holders(draft) == ()
    with rules(draft.world, BreathlessState) as blob:
        blob.sheets[PLAYER_ID].med_kit = True
    landed = draft.committed()
    assert [label for label, _ in med_kit_holders(landed)] == ["Use the med kit"]
    after, _ = play_action(engine, landed, "use_med_kit", {"actor_id": PLAYER_ID}, Random(0))
    assert _sheet(after).stress.current == 1
    assert not _sheet(after).med_kit
    with pytest.raises(ValueError, match="no med kit"):
        _ = apply_use_med_kit(after.draft(), Breathe(actor_id=PLAYER_ID))


def test_creation_rates_three_skills_and_packs_a_d10_item() -> None:
    engine, _ = game(BREATHLESS)
    picks = {
        "pack": "srd",
        "d10": "shoot",
        "d8": "think",
        "d6": "dash",
        "job": "Nurse",
        "pronouns": "she/her",
        "item": "a fire axe",
    }
    created = engine.creation.create("Ines", "A nurse who kept her axe.", picks)
    made = BreathlessState.model_validate(created.mechanics)
    assert made.sheets[PLAYER_ID].skills == {
        "Bash": 4,
        "Dash": 6,
        "Sneak": 4,
        "Shoot": 10,
        "Think": 8,
        "Sway": 4,
    }
    assert made.items[created.items[0].id] == ItemSheet(die=10)
    with pytest.raises(ValueError, match="offers no"):
        _ = engine.creation.create("Ines", "", picks | {"d8": "shoot"})
