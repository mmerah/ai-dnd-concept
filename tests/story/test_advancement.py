from random import Random

from story_test_support import initial_story_game, setback_direction

from aidm.advancement import AdvancementChoice, AdvancementOption, SelectField
from aidm.base import PLAYER_ID, EntityId
from aidm.engines.story.access import player_state
from aidm.engines.story.advancement import IncreaseMaximumStress, dump_decision
from aidm.engines.story.direction import dump_direction


def _values(option: AdvancementOption) -> dict[str, tuple[str, ...]]:
    return {
        field.id: tuple(choice.key for choice in field.options[: field.choose])
        if isinstance(field, SelectField)
        else ("written-in",)
        for field in option.fields
    }


def test_every_offered_option_round_trips_through_the_generic_form() -> None:
    """Each option id is its decision's discriminator and each field id that decision's field
    name, so a rename on either side has to break here rather than in the renderer."""
    engine, state = initial_story_game()
    for _ in range(3):
        state = engine.resolve(dump_direction(setback_direction()), state, Random(2)).state

    form = engine.advancement_form(state)

    assert {option.id for option in form.options} == {
        "raise_approach",
        "add_tag",
        "remove_burden",
        "rewrite_burden",
        "acquire_gear",
        "increase_maximum_stress",
    }
    for option in form.options:
        choice = AdvancementChoice(option_id=option.id, values=_values(option))
        assert engine.advancement_review(state, choice).decision.choice["choice"] == option.id


def test_story_gear_advancement_creates_one_carried_core_item() -> None:
    """`acquire_gear` is the one option whose fields do not map one-to-one: `gear` is nested."""
    engine, state = initial_story_game()
    for _ in range(3):
        state = engine.resolve(dump_direction(setback_direction()), state, Random(2)).state
    assert engine.advancement_available(state)

    form = engine.advancement_form(state)
    gear = next(option for option in form.options if option.id == "acquire_gear")
    review = engine.advancement_review(
        state,
        AdvancementChoice(
            option_id=gear.id,
            values={
                "item_name": ("a silver compass",),
                "item_brief": ("Its needle points toward unfinished promises.",),
                "gear_name": ("Promise Compass",),
                "gear_description": ("It finds paths connected to a sincere vow.",),
            },
        ),
    )

    assert review.decision.choice["gear"] == {
        "name": "Promise Compass",
        "description": "It finds paths connected to a sincere vow.",
    }
    transition = engine.advance(review.decision, state, Random(0))
    created = [fact for fact in transition.facts if fact.kind == "entity_created"]
    assert len(created) == 1
    gear_facts = [fact for fact in transition.facts if fact.kind == "gear_acquired"]
    assert len(gear_facts) == 1

    after = transition.state
    entity_id = created[0].data["entity_id"]
    assert isinstance(entity_id, str)
    entity = after.world.require(EntityId(entity_id))
    assert entity.kind == "item"
    assert entity.parent_id == PLAYER_ID
    assert player_state(after).growth_marks == 0
    assert not engine.advancement_available(after)


def test_increasing_maximum_stress_revives_a_taken_out_player() -> None:
    # F54: leaving taken-out must be as observable as entering it. Five setbacks with
    # Random(2) (the deterministic setback seed every other Story test uses) mark three
    # growth and stack five stress, exactly reaching Kael's default max_stress of 5.
    engine, state = initial_story_game()
    for _ in range(5):
        direction = dump_direction(setback_direction(take_stress=True))
        state = engine.resolve(direction, state, Random(2)).state
    before = player_state(state)
    assert (before.stress, before.max_stress, before.taken_out) == (5, 5, True)
    assert engine.advancement_available(state)

    transition = engine.advance(dump_decision(IncreaseMaximumStress()), state, Random(0))
    assert len([fact for fact in transition.facts if fact.kind == "revived"]) == 1

    player = player_state(transition.state)
    assert (player.stress, player.max_stress) == (5, 6)
    assert player.taken_out is False
