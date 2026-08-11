import json
from random import Random
from typing import get_args

from fivee_test_support import RAT, SWORD, armed, dnd5e_game, wizardly
from pydantic import JsonValue

from aidm.engines.dnd5e.actions import Action
from aidm.engines.loader import Engine
from aidm.state.base import PLAYER_ID, EntityId
from aidm.state.effects import AddTag, SpendCounter
from aidm.state.plan import OutcomeBranch, TurnPlanBase
from aidm.state.world import GameState, player_sheet, sheet_of

SUCCESS = "success"
FAILURE = "failure"
ACTS = tuple(action.model_fields["act"].default for action in get_args(Action.__value__))
WOUNDED = OutcomeBranch(outcome=SUCCESS, effects=(AddTag(entity_id=RAT, tag_id="wounded"),))
UNSCATHED = OutcomeBranch(outcome=FAILURE, effects=(AddTag(entity_id=RAT, tag_id="unscathed"),))


def _plan(
    engine: Engine, action: object | None, *, branches: tuple[OutcomeBranch, ...] = ()
) -> TurnPlanBase:
    return engine.plan_type.model_validate({"action": action, "branches": branches})


def _refusal(engine: Engine, state: GameState, plan: TurnPlanBase) -> str:
    refused = engine.check_plan(state, plan)
    assert refused is not None
    return refused


def _set_number(state: GameState, entity_id: EntityId, key: str, value: int) -> GameState:
    draft = state.draft()
    sheet_of(draft, entity_id).numbers[key] = value
    return draft.committed()


def _hp_ceiling(state: GameState, entity_id: EntityId, maximum: int) -> GameState:
    """Raises a target's hp ceiling so a damage window is never clipped by its own max."""
    draft = state.draft()
    counter = sheet_of(draft, entity_id).counters["hp"]
    counter.maximum = maximum
    counter.current = maximum
    return draft.committed()


def _number(value: JsonValue) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"expected a whole number fact value, got {value!r}")
    return value


def test_a_weapon_attack_that_hits_rolls_damage_and_applies_the_success_branch() -> None:
    engine, state = dnd5e_game()
    ready = _hp_ceiling(armed(state), RAT, 40)
    hit = _set_number(ready, RAT, "armor-class", 1)
    plan = _plan(
        engine,
        {"act": "attack", "actor_id": PLAYER_ID, "target_id": RAT, "weapon_item_id": SWORD},
        branches=(WOUNDED, UNSCATHED),
    )
    assert engine.check_plan(hit, plan) is None

    draft = hit.draft()
    facts = engine.resolve_action(draft, plan, Random(1))

    assert [fact.kind for fact in facts] == [
        "dice_rolled",
        "dice_rolled",
        "counter_changed",
        "tag_added",
    ]
    attack_roll, hp_change = facts[0], facts[2]
    assert _number(attack_roll.data["vs"]) == 1
    assert -11 <= _number(hp_change.data["delta"]) <= -4
    rat = sheet_of(draft, RAT)
    assert rat.tag("wounded") is not None
    assert rat.tag("unscathed") is None


def test_the_same_attack_missing_leaves_the_rat_untouched() -> None:
    engine, state = dnd5e_game()
    ready = armed(state)
    miss = _set_number(ready, RAT, "armor-class", 26)
    plan = _plan(
        engine,
        {"act": "attack", "actor_id": PLAYER_ID, "target_id": RAT, "weapon_item_id": SWORD},
        branches=(WOUNDED, UNSCATHED),
    )

    draft = miss.draft()
    facts = engine.resolve_action(draft, plan, Random(1))

    assert [fact.kind for fact in facts] == ["dice_rolled", "tag_added"]
    assert _number(facts[0].data["vs"]) == 26
    rat = sheet_of(draft, RAT)
    assert rat.counters["hp"].current == 7
    assert rat.tag("unscathed") is not None
    assert rat.tag("wounded") is None


def test_a_stat_block_attack_needs_exactly_one_source_for_its_numbers() -> None:
    engine, state = dnd5e_game()
    ready = armed(state)

    stat_block = {
        "act": "attack",
        "actor_id": RAT,
        "target_id": PLAYER_ID,
        "attack_bonus": 4,
        "damage": "1d4+2",
    }
    plan = _plan(engine, stat_block)
    assert engine.check_plan(ready, plan) is None
    facts = engine.resolve_action(ready.draft(), plan, Random(1))
    assert _number(facts[0].data["vs"]) == 12  # Kael's own armour class

    both = {
        "act": "attack",
        "actor_id": RAT,
        "target_id": PLAYER_ID,
        "weapon_item_id": SWORD,
        "attack_bonus": 4,
        "damage": "1d4+2",
    }
    assert "leave `attack_bonus` and `damage` null" in _refusal(engine, ready, _plan(engine, both))

    neither = {"act": "attack", "actor_id": RAT, "target_id": PLAYER_ID}
    assert "needs either a `weapon_item_id`" in _refusal(engine, ready, _plan(engine, neither))


def test_a_plan_that_also_writes_the_cost_the_engine_pays_is_refused() -> None:
    """gpt-oss-20b's dominant residual: the engine spends the cast's slot, and the plan writes a
    second spend on top, landing `slot-N` at −2 for one cast."""
    engine, state = dnd5e_game()
    ready = wizardly(armed(state))
    cast = {
        "act": "cast-spell",
        "actor_id": PLAYER_ID,
        "spell": "srd-2014/spells/magic-missile",
        "slot_level": 1,
        "target_id": RAT,
    }
    manual = SpendCounter(entity_id=PLAYER_ID, counter="slot-1", amount=1)

    doubled = _plan(engine, cast).model_copy(update={"effects": (manual,)})
    assert "already spends 'slot-1'" in _refusal(engine, ready, doubled)

    branched = _plan(
        engine,
        cast,
        branches=(OutcomeBranch(outcome=SUCCESS, effects=(manual,)),),
    )
    assert "already spends 'slot-1'" in _refusal(engine, ready, branched)

    second_wind = {
        "act": "use-feature",
        "actor_id": PLAYER_ID,
        "counter": "second-wind",
        "heal": "1d10 + 1",
    }
    drained = _plan(engine, second_wind).model_copy(
        update={"effects": (SpendCounter(entity_id=PLAYER_ID, counter="second-wind", amount=1),)}
    )
    assert "already spends 'second-wind'" in _refusal(engine, ready, drained)

    assert engine.check_plan(ready, _plan(engine, cast)) is None


def test_a_cast_spends_its_slot_before_anything_follows() -> None:
    """The protocol guarantee the structured-plan redesign exists for: the slot is gone before the
    spell's own success or failure is decided, and an emptied slot refuses the cast outright."""
    engine, state = dnd5e_game()
    ready = wizardly(armed(state))

    from_one = {
        "act": "cast-spell",
        "actor_id": PLAYER_ID,
        "spell": "srd-2014/spells/magic-missile",
        "slot_level": 1,
        "target_id": RAT,
    }
    plan_one = _plan(engine, from_one)
    assert engine.check_plan(ready, plan_one) is None
    draft_one = ready.draft()
    facts_one = engine.resolve_action(draft_one, plan_one, Random(1))
    sheet_one = sheet_of(draft_one, PLAYER_ID)
    assert sheet_one.counters["slot-1"].current == 1
    damage_one = next(fact for fact in facts_one if fact.kind == "dice_rolled")
    assert 6 <= _number(damage_one.data["total"]) <= 15

    from_two = {
        "act": "cast-spell",
        "actor_id": PLAYER_ID,
        "spell": "srd-2014/spells/magic-missile",
        "slot_level": 2,
        "target_id": RAT,
    }
    plan_two = _plan(engine, from_two)
    draft_two = ready.draft()
    facts_two = engine.resolve_action(draft_two, plan_two, Random(2))
    sheet_two = sheet_of(draft_two, PLAYER_ID)
    assert (sheet_two.counters["slot-2"].current, sheet_two.counters["slot-1"].current) == (1, 2)
    damage_two = next(fact for fact in facts_two if fact.kind == "dice_rolled")
    assert 8 <= _number(damage_two.data["total"]) <= 20

    drained = ready.draft()
    sheet_of(drained, PLAYER_ID).counters["slot-1"].current = 0
    empty = drained.committed()
    assert "cannot go below" in _refusal(engine, empty, plan_one)


def test_a_save_based_spell_rolls_a_fixed_dc_and_halves_on_a_saved_target() -> None:
    """Success and failure read from the caster's side: `success` means the target failed."""
    engine, state = dnd5e_game()
    ready = _hp_ceiling(wizardly(armed(state)), RAT, 100)
    plan = _plan(
        engine,
        {
            "act": "cast-spell",
            "actor_id": PLAYER_ID,
            "spell": "srd-2014/spells/burning-hands",
            "slot_level": 1,
            "target_id": RAT,
        },
    )

    failing = _set_number(ready, RAT, "dexterity", -100)
    draft = failing.draft()
    facts = engine.resolve_action(draft, plan, Random(1))
    save_roll = next(fact for fact in facts if "resists" in fact.trace)
    damage_roll = next(fact for fact in facts if "damage" in fact.trace)
    hp_change = next(fact for fact in facts if fact.data.get("counter") == "hp")
    assert _number(save_roll.data["vs"]) == 12
    assert _number(hp_change.data["delta"]) == -_number(damage_roll.data["total"])

    saving = _set_number(ready, RAT, "dexterity", 100)
    draft2 = saving.draft()
    facts2 = engine.resolve_action(draft2, plan, Random(2))
    save_roll2 = next(fact for fact in facts2 if "resists" in fact.trace)
    damage_roll2 = next(fact for fact in facts2 if "damage" in fact.trace)
    hp_change2 = next(fact for fact in facts2 if fact.data.get("counter") == "hp")
    assert _number(save_roll2.data["vs"]) == 12
    assert _number(hp_change2.data["delta"]) == -(_number(damage_roll2.data["total"]) // 2)


def test_the_bookkeeping_actions_spend_heal_and_recharge() -> None:
    engine, state = dnd5e_game()

    hurt = state.draft()
    player_sheet(hurt).counters["hp"].current = 0
    hurt = hurt.committed()
    feature_plan = _plan(
        engine,
        {"act": "use-feature", "actor_id": PLAYER_ID, "counter": "second-wind", "heal": "1d10 + 1"},
    )
    assert engine.check_plan(hurt, feature_plan) is None

    spent_draft = hurt.draft()
    feature_facts = engine.resolve_action(spent_draft, feature_plan, Random(1))
    spent_sheet = sheet_of(spent_draft, PLAYER_ID)
    assert spent_sheet.counters["second-wind"].current == 0
    heal_fact = next(fact for fact in feature_facts if fact.data.get("counter") == "hp")
    assert 2 <= _number(heal_fact.data["delta"]) <= 11

    rested = spent_draft.committed()
    rest_plan = _plan(engine, {"act": "rest", "actor_id": PLAYER_ID, "label": "short-rest"})
    rest_draft = rested.draft()
    rest_facts = engine.resolve_action(rest_draft, rest_plan, Random(1))
    assert [fact.kind for fact in rest_facts] == ["recharged"]
    assert sheet_of(rest_draft, PLAYER_ID).counters["second-wind"].current == 1

    uncontested = _plan(
        engine,
        {"act": "rest", "actor_id": PLAYER_ID, "label": "short-rest"},
        branches=(OutcomeBranch(outcome=SUCCESS, effects=()),),
    )
    assert "settles no outcome" in _refusal(engine, rested, uncontested)


def test_a_plan_with_json_stringified_nested_fields_validates_as_if_nested() -> None:
    """Some OpenAI-compatible backends deliver a tool call's nested arguments as JSON strings;
    a retry cannot repair that transport quirk, so the plan boundary decodes it."""
    engine, _ = dnd5e_game()
    action = {"act": "attack", "actor_id": "player", "target_id": RAT, "weapon_item_id": SWORD}
    hit = {"op": "add-tag", "entity_id": RAT, "tag_id": "wounded"}
    nested = {
        "action": action,
        "branches": [{"outcome": SUCCESS, "effects": [hit]}],
    }
    stringified = {
        **nested,
        "action": json.dumps(nested["action"]),
        "branches": json.dumps(nested["branches"]),
    }
    assert engine.plan_type.model_validate(stringified) == engine.plan_type.model_validate(nested)


def test_every_action_is_worked_through_in_the_directors_instructions() -> None:
    """An action without an example teaches the model nothing: coverage is asserted, not hoped."""
    engine, _ = dnd5e_game()
    for act in ACTS:
        assert engine.director_instructions.count(f'"act": "{act}"') >= 1


def test_a_cast_checks_its_target_and_a_roll_never_names_an_unrevealed_actor() -> None:
    """A heal states no attack and no save, so nothing else forces its target to be checked; and a
    roll's own fact carries names, which the reveal must precede."""
    engine, state = dnd5e_game()
    ready = wizardly(armed(state))  # the player is in the cloister, Mara is in the study

    away = _plan(
        engine,
        {
            "act": "cast-spell",
            "actor_id": PLAYER_ID,
            "spell": "srd-2014/spells/cure-wounds",
            "slot_level": 1,
            "target_id": EntityId("mara"),
        },
    )
    assert "not here with the player" in _refusal(engine, ready, away)

    draft = ready.draft()
    draft.world.record(RAT).entity.known = False
    attack = _plan(
        engine, {"act": "attack", "actor_id": PLAYER_ID, "target_id": RAT, "weapon_item_id": SWORD}
    )
    assert engine.resolve_action(draft, attack, Random(4))[0].kind == "entity_discovered"
