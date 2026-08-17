from random import Random

import pytest
from core_test_support import CAIRN2E, game, with_entity

from aidm.engines.cairn2e.actions import (
    Attack,
    Fate,
    PassTime,
    Reaction,
    reaction_for,
    resolve_attack,
    resolve_fate,
    resolve_pass_time,
    resolve_reaction,
)
from aidm.engines.cairn2e.mechanics import (
    DEPRIVED,
    STOWED,
    ItemRules,
    Mechanics,
    Sheet,
    apply,
    armor_of,
    saved,
)
from aidm.engines.counters import CounterChange
from aidm.state.base import PLAYER_ID, Counter, Entity, EntityId, Trait
from aidm.state.creation import Picks
from aidm.state.effects import TraitChange

MARA = EntityId("mara")
BRIGAND = EntityId("brigand")
SWORD = EntityId("sword")
DAGGER = EntityId("dagger")
SHIELD = EntityId("shield")


@pytest.mark.parametrize(
    ("rolled", "score", "expected"),
    [
        (1, 1, True),
        (1, 20, True),
        (20, 20, False),
        (12, 12, True),
        (13, 12, False),
    ],
)
def test_the_save_ladder_passes_a_natural_1_and_fails_a_natural_20(
    rolled: int, score: int, expected: bool
) -> None:
    assert saved(rolled, score) is expected


def test_ten_filled_slots_empty_the_hp_and_an_eleventh_is_refused() -> None:
    _, state = game(CAIRN2E)
    fill = CounterChange(
        mode="adjust",
        entity_id=PLAYER_ID,
        counter="fatigue",
        amount=9,
        why="worn thin by the vault",
    )
    draft = state.draft()
    apply(draft, fill)
    assert draft.mechanics_as(Mechanics).sheets[PLAYER_ID].hp.current == 0

    overloaded = fill.model_copy(update={"amount": 10})
    with pytest.raises(ValueError, match="limit of 10"):
        apply(state.draft(), overloaded)


def test_deprivation_refuses_recovery_until_the_trait_lifts() -> None:
    _, state = game(CAIRN2E)
    draft = state.draft()
    mechanics = draft.mechanics_as(Mechanics)
    mechanics.sheets[PLAYER_ID].hp.current = 2
    hurt = draft.committed()

    draft = hurt.draft()
    draft.world.require(PLAYER_ID).traits.append(Trait(id=DEPRIVED, name="Deprived", text=""))
    weakened = draft.committed()

    heal = CounterChange(
        mode="adjust", entity_id=PLAYER_ID, counter="hp", amount=1, why="a healing draught"
    )
    with pytest.raises(ValueError, match="deprived"):
        apply(weakened.draft(), heal)

    draft = hurt.draft()
    apply(draft, heal)
    assert draft.mechanics_as(Mechanics).sheets[PLAYER_ID].hp.current == 3


def test_an_attack_takes_armor_off_the_damage_then_hp() -> None:
    _, state = game(CAIRN2E)
    draft = state.draft()
    mechanics = draft.mechanics_as(Mechanics)
    mechanics.sheets[MARA].hp = Counter(current=10, maximum=10)
    mechanics.sheets[MARA].armor = 1
    ready = draft.committed()

    draft = ready.draft()
    attack = Attack(attacker_id=PLAYER_ID, target_ids=(MARA,), weapon_ids=())
    resolution = resolve_attack(draft, attack, Random(1))

    # A d4 less one armor can never reach ten HP.
    assert resolution.outcome == "hit"
    (dice_fact,) = [fact for fact in resolution.facts if fact.kind == "dice_rolled"]
    kept = dice_fact.data["kept"]
    assert isinstance(kept, int)
    assert draft.mechanics_as(Mechanics).sheets[MARA].hp.current == 10 - max(kept - 1, 0)


def test_damage_past_the_hp_becomes_critical_damage() -> None:
    _, state = game(CAIRN2E)
    draft = state.draft()
    mechanics = draft.mechanics_as(Mechanics)
    mechanics.sheets[MARA].hp = Counter(current=0, maximum=4)
    mechanics.sheets[MARA].strength = Counter(current=1, maximum=10)
    ready = draft.committed()

    draft = ready.draft()
    attack = Attack(attacker_id=PLAYER_ID, target_ids=(MARA,), weapon_ids=())
    # Any unarmed die empties Mara's 1 strength, and strength at 0 is death outright.
    resolution = resolve_attack(draft, attack, Random(0))

    assert draft.mechanics_as(Mechanics).sheets[MARA].strength.current == 0
    assert draft.world.require(MARA).trait("dead") is not None
    assert resolution.outcome == "down"
    # An NPC going down is a consequence, not an interruption.
    assert resolution.followup == "continue"


def test_a_blow_that_lands_on_exactly_0_hp_takes_a_scar() -> None:
    _, state = game(CAIRN2E)
    before = len(state.world.pending_notes)
    draft = state.draft()
    attack = Attack(attacker_id=MARA, target_ids=(PLAYER_ID,), weapon_ids=())
    # Seed 0's attack die rolls a natural 4, landing Kael's 4 HP on exactly 0 with no overflow.
    resolution = resolve_attack(draft, attack, Random(0))

    assert resolution.outcome == "hit"
    (scar_fact,) = [fact for fact in resolution.facts if fact.kind == "scar_taken"]
    assert draft.world.require(PLAYER_ID).trait(str(scar_fact.data["scar"])) is not None
    assert len(draft.world.pending_notes) > before
    assert resolution.followup == "settle"


def test_pass_time_ticks_a_fatigue_per_deprived_day() -> None:
    _, state = game(CAIRN2E)
    draft = state.draft()
    draft.world.require(PLAYER_ID).traits.append(Trait(id=DEPRIVED, name="Deprived", text=""))
    ready = draft.committed()

    draft = ready.draft()
    resolution = resolve_pass_time(
        draft, PassTime(days=2, why="a two-day trek to the coast"), Random(0)
    )

    mechanics = draft.mechanics_as(Mechanics)
    assert mechanics.sheets[PLAYER_ID].fatigue.current == 2
    assert mechanics.sheets[MARA].fatigue.current == 0
    assert mechanics.day == 2
    (time_fact,) = [fact for fact in resolution.facts if fact.kind == "time_passed"]
    assert time_fact.data == {"days": 2, "day": 2}


def test_a_deferred_scar_waits_and_pays_out_when_mended() -> None:
    _, state = game(CAIRN2E)
    draft = state.draft()
    attack = Attack(attacker_id=MARA, target_ids=(PLAYER_ID,), weapon_ids=())
    # Seed 0 lands Kael's 4 HP on exactly 0 (hp_lost=4 -> broken-limb, a deferred row).
    resolve_attack(draft, attack, Random(0))
    mechanics = draft.mechanics_as(Mechanics)
    assert draft.world.require(PLAYER_ID).trait("broken-limb") is not None
    assert mechanics.sheets[PLAYER_ID].hp.maximum == 4
    assert mechanics.sheets[PLAYER_ID].mending == ["broken-limb"]
    hurt = draft.committed()

    draft = hurt.draft()
    mend = PassTime(days=7, mended_ids=(PLAYER_ID,), why="a week under a healer's care")
    resolution = resolve_pass_time(draft, mend, Random(0))

    mechanics = draft.mechanics_as(Mechanics)
    assert draft.world.require(PLAYER_ID).trait("broken-limb") is None
    assert mechanics.sheets[PLAYER_ID].mending == []
    assert any(fact.kind == "scar_mended" for fact in resolution.facts)
    # Seed 0's 2d6 recovery rolls 4, 4 -> 8, higher than the untouched maximum of 4.
    assert mechanics.sheets[PLAYER_ID].hp.maximum == 8


def test_an_immediate_scar_still_pays_at_once() -> None:
    _, state = game(CAIRN2E)
    draft = state.draft()
    mechanics = draft.mechanics_as(Mechanics)
    mechanics.sheets[PLAYER_ID].hp.current = 1
    # Full armor takes seed 0's natural-4 blow down to exactly 1 damage (hp_lost=1 -> lasting-scar).
    mechanics.sheets[PLAYER_ID].armor = 3
    ready = draft.committed()

    draft = ready.draft()
    attack = Attack(attacker_id=MARA, target_ids=(PLAYER_ID,), weapon_ids=())
    resolution = resolve_attack(draft, attack, Random(0))

    assert any(
        fact.kind == "dice_rolled" and str(fact.data["reason"]).endswith("recovery")
        for fact in resolution.facts
    )
    assert draft.mechanics_as(Mechanics).sheets[PLAYER_ID].mending == []


def test_trait_change_cannot_lift_a_scar_that_waits_on_mending() -> None:
    _, state = game(CAIRN2E)
    draft = state.draft()
    draft.world.require(PLAYER_ID).traits.append(
        Trait(id="broken-limb", name="Broken Limb", text="")
    )
    draft.mechanics_as(Mechanics).sheets[PLAYER_ID].mending.append("broken-limb")
    ready = draft.committed()

    lift = TraitChange(mode="remove", entity_id=PLAYER_ID, trait_id="broken-limb")
    with pytest.raises(ValueError, match="mended_ids"):
        apply(ready.draft(), lift)


def test_pass_time_refuses_the_dead_and_the_unscarred() -> None:
    _, state = game(CAIRN2E)
    draft = state.draft()
    draft.world.require(MARA).traits.append(Trait(id="dead", name="Dead", text="(condition) Dead."))
    dead = draft.committed()

    with pytest.raises(ValueError, match="past mending"):
        resolve_pass_time(
            dead.draft(), PassTime(days=0, mended_ids=(MARA,), why="a week passes"), Random(0)
        )

    with pytest.raises(ValueError, match="no scar waiting"):
        resolve_pass_time(
            state.draft(), PassTime(days=0, mended_ids=(MARA,), why="a week passes"), Random(0)
        )


def test_dual_wield_rolls_both_weapon_dice_and_keeps_the_highest() -> None:
    _, state = game(CAIRN2E)
    sword = Entity(
        id=SWORD,
        kind="item",
        name="Sword",
        brief="A well-oiled blade.",
        known=True,
        parent_id=PLAYER_ID,
    )
    dagger = Entity(
        id=DAGGER,
        kind="item",
        name="Dagger",
        brief="A wicked little blade.",
        known=True,
        parent_id=PLAYER_ID,
    )
    state = with_entity(with_entity(state, sword), dagger)
    draft = state.draft()
    mechanics = draft.mechanics_as(Mechanics)
    mechanics.items[SWORD] = ItemRules(damage=8)
    mechanics.items[DAGGER] = ItemRules(damage=6)
    mechanics.sheets[MARA].hp = Counter(current=20, maximum=20)
    ready = draft.committed()

    draft = ready.draft()
    attack = Attack(attacker_id=PLAYER_ID, target_ids=(MARA,), weapon_ids=(SWORD, DAGGER))
    resolution = resolve_attack(draft, attack, Random(1))

    (dice_fact,) = [fact for fact in resolution.facts if fact.kind == "dice_rolled"]
    assert dice_fact.data["faces"] == [8, 6]


def test_stowed_armor_does_not_count() -> None:
    _, state = game(CAIRN2E)
    shield = Entity(
        id=SHIELD,
        kind="item",
        name="Shield",
        brief="A round oak shield.",
        known=True,
        parent_id=PLAYER_ID,
    )
    state = with_entity(state, shield)
    draft = state.draft()
    mechanics = draft.mechanics_as(Mechanics)
    mechanics.items[SHIELD] = ItemRules(armor=1)
    player = draft.world.require(PLAYER_ID)
    assert armor_of(draft, mechanics, player) == 1

    player.traits.append(Trait(id=STOWED, name="Stowed", text="(condition) Packed away."))
    assert armor_of(draft, mechanics, player) == 1
    draft.world.require(SHIELD).traits.append(
        Trait(id=STOWED, name="Stowed", text="(condition) Packed away.")
    )
    assert armor_of(draft, mechanics, player) == 0


def test_a_blast_rolls_each_target_and_reports_the_players_own_outcome() -> None:
    _, state = game(CAIRN2E)
    brigand = Entity(
        id=BRIGAND,
        kind="actor",
        name="A Brigand",
        brief="One more blade crowding the abbot's study.",
        known=True,
        parent_id=state.player_location,
    )
    state = with_entity(state, brigand)
    draft = state.draft()
    mechanics = draft.mechanics_as(Mechanics)
    mechanics.sheets[BRIGAND] = Sheet(
        hp=Counter(current=1, maximum=1), strength=Counter(current=1, maximum=10)
    )
    mechanics.sheets[PLAYER_ID].hp = Counter(current=20, maximum=20)
    ready = draft.committed()

    draft = ready.draft()
    attack = Attack(attacker_id=MARA, target_ids=(BRIGAND, PLAYER_ID), weapon_ids=())
    # Seed 0's two unarmed d4 rolls are 4 and 4: the brigand's lone strength empties outright
    # (down, no save owed), the player just takes the blow (hit) — the player's own outcome wins.
    resolution = resolve_attack(draft, attack, Random(0))

    dice_facts = [fact for fact in resolution.facts if fact.kind == "dice_rolled"]
    assert len(dice_facts) == 2
    assert draft.world.require(BRIGAND).trait("dead") is not None
    assert resolution.outcome == "hit"


@pytest.mark.parametrize(
    ("total", "expected"),
    [(2, "hostile"), (5, "wary"), (6, "curious"), (11, "kind"), (12, "helpful")],
)
def test_reaction_for_maps_the_srd_table(total: int, expected: str) -> None:
    assert reaction_for(total) == expected


def test_resolve_fate_and_resolve_reaction() -> None:
    _, state = game(CAIRN2E)
    before = len(state.world.pending_notes)
    draft = state.draft()
    # Seed 1 rolls a 2 on the fate d6 and 2+5=7 on the reaction 2d6.
    resolution = resolve_fate(draft, Fate(question="does the rope hold"), Random(1))
    assert resolution.outcome == "unfavorable"
    assert len(draft.world.pending_notes) == before + 1

    draft = state.draft()
    resolution = resolve_reaction(draft, Reaction(actor_id=MARA), Random(1))
    assert resolution.outcome == "curious"
    assert any(fact.kind == "reaction_rolled" for fact in resolution.facts)
    assert len(draft.world.pending_notes) == before + 1

    with pytest.raises(ValueError):
        resolve_reaction(state.draft(), Reaction(actor_id=PLAYER_ID), Random(1))


def test_creation_builds_a_character_the_engine_can_read() -> None:
    engine, _ = game(CAIRN2E)
    assert engine.creation is not None
    picks: Picks = {}
    while pending := next(
        (step for step in engine.creation.steps(picks) if step.id not in picks), None
    ):
        chosen = tuple(option.id for option in pending.options[: pending.choose])
        picks = {**picks, pending.id: chosen}
    created = engine.creation.create("Vex", "A quiet drifter.", picks)

    Sheet.model_validate(created.overlay.character)
    for payload in created.overlay.entities.values():
        ItemRules.model_validate(payload)
    assert {item.id for item in created.profile.items} == set(created.overlay.entities)
