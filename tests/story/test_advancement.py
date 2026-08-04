from collections.abc import Callable
from random import Random

from story_test_support import initial_story_game, setback

from aidm.core.base import PLAYER_ID, EntityId
from aidm.engines.story.advancement import (
    AcquireGear,
    AddTag,
    IncreaseMaximumStress,
    RaiseApproach,
    RemoveBurden,
    RewriteBurden,
    StoryAdvancementDecision,
    burdens,
    dump_decision,
    raisable_approaches,
    stress_raisable,
)
from aidm.engines.story.state import (
    APPROACH_NAMES,
    MAX_APPROACH,
    MAX_MAX_STRESS,
    StoryActorState,
    StoryApproaches,
    StoryGearTag,
    player_state,
)


def test_each_advancement_writes_what_it_promises_and_spends_the_growth() -> None:
    engine, state = initial_story_game()
    for _ in range(3):
        state = setback(engine, state)[0]
    before = player_state(state)
    burden = burdens(before)[0]
    cases: tuple[tuple[StoryAdvancementDecision, str, Callable[[StoryActorState], bool]], ...] = (
        (
            RaiseApproach(approach="bold"),
            "approach_raised",
            lambda player: player.approaches.bold == before.approaches.bold + 1,
        ),
        (
            AddTag(id="sworn-ally", name="Sworn ally", kind="bond", description="A debt repaid."),
            "tag_added",
            lambda player: any(tag.id == "sworn-ally" for tag in player.tags),
        ),
        (
            RemoveBurden(id=burden.id),
            "tag_removed",
            lambda player: all(tag.id != burden.id for tag in player.tags),
        ),
        (
            RewriteBurden(id=burden.id, name="A quieter debt", description="Still owed, softer."),
            "tag_rewritten",
            lambda player: any(tag.name == "A quieter debt" for tag in player.tags),
        ),
    )

    for decision, kind, written in cases:
        transition = engine.advance(dump_decision(decision), state, Random(0))

        assert [fact.kind for fact in transition.facts] == [kind, "growth_reset"]
        after = player_state(transition.state)
        assert written(after)
        assert after.growth_marks == 0


def test_capped_advancements_are_not_offered() -> None:
    """The panel renders whatever these report, so a cap that stops applying stops being visible."""
    _, state = initial_story_game()
    player = player_state(state)
    capped = player.model_copy(
        update={
            "approaches": StoryApproaches(**dict.fromkeys(APPROACH_NAMES, MAX_APPROACH)),
            "max_stress": MAX_MAX_STRESS,
        }
    )

    assert [name for name, _ in raisable_approaches(player)] == list(APPROACH_NAMES)
    assert stress_raisable(player)
    assert raisable_approaches(capped) == ()
    assert not stress_raisable(capped)


def test_story_gear_advancement_creates_one_carried_core_item() -> None:
    """`acquire_gear` is the one advancement that reaches past the player's payload."""
    engine, state = initial_story_game()
    for _ in range(3):
        state = setback(engine, state)[0]
    assert engine.advancement_available(state)

    decision = AcquireGear(
        item_name="a silver compass",
        item_brief="Its needle points toward unfinished promises.",
        gear=StoryGearTag(
            name="Promise Compass",
            description="It finds paths connected to a sincere vow.",
        ),
    )
    transition = engine.advance(dump_decision(decision), state, Random(0))

    created = [fact for fact in transition.facts if fact.kind == "entity_created"]
    assert len(created) == 1
    assert len([fact for fact in transition.facts if fact.kind == "gear_acquired"]) == 1

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
        state = setback(engine, state, stress=True)[0]
    before = player_state(state)
    assert (before.stress, before.max_stress, before.taken_out) == (5, 5, True)
    assert engine.advancement_available(state)

    transition = engine.advance(dump_decision(IncreaseMaximumStress()), state, Random(0))
    assert len([fact for fact in transition.facts if fact.kind == "revived"]) == 1

    player = player_state(transition.state)
    assert (player.stress, player.max_stress) == (5, 6)
    assert player.taken_out is False
