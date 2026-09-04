from support.table import Call, changed, narrowed, tool_call

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
    state = narrowed(state, TunnelGoonsGame)
    draft = state.draft()
    draft.payload.visits[0].exchanges.append(
        Exchange(
            prompt="I look around the archway before going further.",
            lines=(SpokenLine(text="Grix waves you toward the corridor, impatient."),),
        )
    )
    return draft.commit()
