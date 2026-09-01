from core_test_support import Call, changed, tool_call

from aidm.core.model import AnyGame
from aidm.core.play import Exchange, SpokenLine
from aidm.engines.breathless.world import BreathlessGame

SCRIPT: tuple[Call, ...] = (
    changed("reveal", entity_id="drowned-marta"),
    tool_call("check", what="Listen for what moves on the flats", skill="think"),
    tool_call("change_stress", amount=1, why="the bell rang twice"),
)


def behind(state: AnyGame) -> AnyGame:
    """One prior exchange at the starting scene: RECENT PLAY has to render it."""
    if not isinstance(state, BreathlessGame):
        raise AssertionError(f"unsupported golden engine state: {type(state).__name__}")
    draft = state.draft()
    draft.payload.world.runs[0].exchanges.append(
        Exchange(
            prompt="I look around the Bell House before going further.",
            lines=(SpokenLine(text="Ovid Sarn watches you from the cracked window."),),
        )
    )
    return draft.committed()
