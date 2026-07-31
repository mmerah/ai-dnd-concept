from story_test_support import initial_story_game

from aidm.agents.context import SceneSnapshot, VisibleScene
from aidm.agents.prompting import render_narrator
from aidm.engines import entity_renderer


def test_story_narrator_receives_visible_actor_and_gear_state() -> None:
    engine, state = initial_story_game()
    prompt = render_narrator(
        VisibleScene.of(SceneSnapshot.of(state)),
        entity_renderer(engine, state),
        state.scenario,
        intent="Mara watches Kael search.",
        tone="wary",
        speaker_id=None,
        evidence="- nothing mechanical changes",
        prompt="I inspect the desk.",
    )

    assert "Mara[id=mara]" in prompt
    assert "stress 0/5" in prompt
    assert "status active" in prompt
    assert "gear benefit: Unsteady Lantern" in prompt
    assert "Elena" not in prompt
