from random import Random

from core_test_support import capability
from story_test_support import grown, story_game

from aidm.engines.counters import CounterChange
from aidm.engines.loader import Engine
from aidm.engines.story.advance import MAX_APPROACH, MAX_STRESS, Growth
from aidm.engines.story.mechanics import read, write
from aidm.state.base import PLAYER_ID, EntityId
from aidm.state.effects import TraitChange
from aidm.state.plan import OutcomeBranch, TurnPlanBase
from aidm.state.world import GameState
from aidm.turn.prompts import SceneSnapshot, check_speaker

RAT = EntityId("cloister_rat")
STRONG = OutcomeBranch(
    outcome="strong",
    effects=(TraitChange(mode="add", entity_id=PLAYER_ID, trait_id="sure-footed"),),
)
SETBACK = OutcomeBranch(
    outcome="setback",
    effects=(
        CounterChange(
            mode="adjust", entity_id=PLAYER_ID, counter="stress", amount=2, why="the door holds"
        ),
    ),
)


def _plan(engine: Engine, **action: object) -> TurnPlanBase:
    return engine.plan_type.model_validate(
        {
            "branches": (STRONG, SETBACK),
            "action": {
                "act": "risk",
                "approach": "bold",
                "difficulty": "risky",
                "stakes": "forcing the door",
            }
            | action,
        }
    )


def _certain(state: GameState, bonus: int) -> GameState:
    """2d6 spans 2..12, so an approach this far out of range fixes the outcome under any seed."""
    draft = state.draft()
    mechanics = read(draft)
    mechanics.actors[PLAYER_ID].bold = bonus
    write(draft, mechanics)
    return draft.committed()


def _capped(state: GameState) -> GameState:
    """The player already at both story caps, so one more mark would break each of them."""
    draft = state.draft()
    mechanics = read(draft)
    actor = mechanics.actors[PLAYER_ID]
    actor.bold = MAX_APPROACH
    actor.stress.maximum = MAX_STRESS
    write(draft, mechanics)
    return draft.committed()


def test_a_risk_rolls_once_against_seven_and_applies_only_the_branch_it_landed_on() -> None:
    engine, state = story_game()
    draft = _certain(state, 8).draft()

    facts = engine.resolve_action(draft, _plan(engine, actor_id=PLAYER_ID), Random(3))

    (rolled,) = [fact for fact in facts if fact.kind == "dice_rolled"]
    assert (rolled.data["vs"], rolled.data["success"]) == (7, True)
    assert [fact.kind for fact in facts] == ["dice_rolled", "trait_added"]
    assert draft.world.require(PLAYER_ID).trait("sure-footed") is not None
    assert read(draft).actors[PLAYER_ID].growth.current == 0


def test_a_setback_on_the_player_marks_growth_the_model_never_writes() -> None:
    engine, state = story_game()
    draft = _certain(state, -7).draft()

    facts = engine.resolve_action(draft, _plan(engine, actor_id=PLAYER_ID), Random(3))

    assert [fact.kind for fact in facts] == ["dice_rolled", "counter_changed", "counter_changed"]
    actor = read(draft).actors[PLAYER_ID]
    assert actor.growth.current == 1
    assert actor.stress.current == 2
    assert draft.world.require(PLAYER_ID).trait("sure-footed") is None


def test_check_plan_refuses_what_the_procedure_cannot_resolve() -> None:
    """A trait must be held to count; whether a held trait helps or hinders stays the model's
    call."""
    engine, state = story_game()
    gear = _plan(engine, actor_id=PLAYER_ID, helping_trait_id="unsteady-lantern")

    assert engine.check_plan(state, gear) is None
    assert "not here with the player" in _refusal(engine, state, _plan(engine, actor_id=RAT))
    absent = _plan(engine, actor_id=PLAYER_ID, helping_trait_id="lockpicking")
    assert "nothing helps them here" in _refusal(engine, state, absent)
    hinders = _plan(engine, actor_id=PLAYER_ID, hindering_trait_id="unsteady-lantern")
    assert "nothing hinders them here" in _refusal(engine, state, hinders)

    quiet = engine.plan_type.model_validate({"branches": (STRONG,)})
    assert "settles no outcome" in _refusal(engine, state, quiet)

    taken_out = state.draft()
    mechanics = read(taken_out)
    mechanics.actors[PLAYER_ID].stress.current = 5
    write(taken_out, mechanics)
    assert "TAKEN OUT" in _refusal(engine, taken_out.committed(), _plan(engine, actor_id=PLAYER_ID))


def test_check_speaker_refuses_who_the_narrator_may_not_voice() -> None:
    """The speaker guard is what keeps the Narrator from voicing the player or an unmet NPC."""
    _, state = story_game()
    scene = SceneSnapshot.of(state)

    assert check_speaker(scene, EntityId("mara")) is None
    assert check_speaker(scene, None) is None
    assert "never the player" in str(check_speaker(scene, PLAYER_ID))
    assert "unknown speaker" in str(check_speaker(scene, EntityId("nobody")))
    for absent in (EntityId("tomas"), EntityId("elena")):
        assert "met and who is here" in str(check_speaker(scene, absent))


def test_growth_opens_an_offer_and_storys_own_caps_refuse_what_breaks_them() -> None:
    engine, state = story_game()
    growth = capability(engine)
    assert growth.offered(state) is None

    ready = grown(state)
    offer = growth.offered(ready)
    assert offer is not None
    maxed = _capped(ready)

    legal = Growth(approach="clever", why="patience earned")
    over_approach = Growth(approach="bold", why="greed")
    over_stress = Growth(resilience=True, why="steady now")

    assert growth.violation(ready, offer, legal) is None
    assert growth.violation(maxed, offer, over_approach) == (
        f"an approach cannot pass +{MAX_APPROACH}: ['bold']"
    )
    assert growth.violation(maxed, offer, over_stress) == (
        f"the stress maximum cannot pass {MAX_STRESS}, and this proposal reaches {MAX_STRESS + 1}"
    )


def test_the_one_action_is_worked_through_in_the_directors_instructions() -> None:
    """An action without an example teaches the model nothing: coverage is asserted, not hoped."""
    engine, _ = story_game()

    assert engine.director_instructions.count('"act": "risk"') == 1


def _refusal(engine: Engine, state: GameState, plan: TurnPlanBase) -> str:
    refused = engine.check_plan(state, plan)
    assert refused is not None
    return refused
