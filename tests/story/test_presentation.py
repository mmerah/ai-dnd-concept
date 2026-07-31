from story_test_support import initial_story_game

from aidm.agents.context import NarratorContext, build_narrator_scene
from aidm.agents.prompting import build_narrator_prompt


def test_story_narrator_receives_visible_actor_and_gear_state() -> None:
    engine, state = initial_story_game()
    prompt = build_narrator_prompt(
        NarratorContext(
            scene=build_narrator_scene(state, engine.presentation.entity_state),
            scenario_title=state.scenario.title,
            scenario_premise=state.scenario.premise,
            intent="Mara watches Kael search.",
            tone="wary",
            speaker_id=None,
            evidence="- nothing mechanical changes",
            prompt="I inspect the desk.",
        )
    )

    assert "Mara[id=mara]" in prompt
    assert "stress 0/5" in prompt
    assert "status active" in prompt
    assert "gear benefit: Unsteady Lantern" in prompt
    assert "Elena" not in prompt
