from core_test_support import Call, changed, tool_call

from aidm.core.model import AnyGame
from aidm.core.play import Exchange, SpokenLine
from aidm.engines.tunnelgoons.world import TunnelGoonsGame

SCRIPT: tuple[Call, ...] = (
    tool_call("move", to_id="cellar"),
    tool_call(
        "action_roll",
        what="Wade through the flooded cellar",
        ability="skulker",
        difficulty=10,
        dangerous=True,
    ),
    changed("reveal", entity_id="lurker"),
)


def behind(state: AnyGame) -> AnyGame:
    """One prior exchange at the starting place: RECENT PLAY has to render it."""
    if not isinstance(state, TunnelGoonsGame):
        raise AssertionError(f"unsupported golden engine state: {type(state).__name__}")
    draft = state.draft()
    draft.payload.world.visits[0].exchanges.append(
        Exchange(
            prompt="I look around the archway before going further.",
            lines=(SpokenLine(text="Grix waves you toward the corridor, impatient."),),
        )
    )
    return draft.committed()
