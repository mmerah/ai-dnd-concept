from random import Random

import pytest
from core_test_support import CAIRN2E, game

from aidm.engines.cairn2e.actions import Attack, resolve_attack
from aidm.engines.cairn2e.mechanics import DEPRIVED, ItemRules, Mechanics, Sheet, apply, saved
from aidm.engines.counters import CounterChange
from aidm.state.base import PLAYER_ID, Counter, EntityId, Trait
from aidm.state.creation import Picks

MARA = EntityId("mara")


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
    attack = Attack(attacker_id=PLAYER_ID, target_id=MARA, weapon_id=None)
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
    attack = Attack(attacker_id=PLAYER_ID, target_id=MARA, weapon_id=None)
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
    attack = Attack(attacker_id=MARA, target_id=PLAYER_ID, weapon_id=None)
    # Seed 0's attack die rolls a natural 4, landing Kael's 4 HP on exactly 0 with no overflow.
    resolution = resolve_attack(draft, attack, Random(0))

    assert resolution.outcome == "hit"
    (scar_fact,) = [fact for fact in resolution.facts if fact.kind == "scar_taken"]
    assert draft.world.require(PLAYER_ID).trait(str(scar_fact.data["scar"])) is not None
    assert len(draft.world.pending_notes) > before
    assert resolution.followup == "settle"


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
