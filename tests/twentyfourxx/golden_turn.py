from support.table import Call, narrowed, tool_call

from aidm.core.model import AnyGame
from aidm.core.play import Exchange, SpokenLine
from aidm.engines.twentyfourxx.world import TwentyfourxxGame

SCRIPT: tuple[Call, ...] = (
    tool_call("join_party", entity_id="vessa-rune"),
    tool_call("reveal", entity_id="warden-six"),
    tool_call("roll", what="Slip along the dark gantry", skill="Stealth"),
    tool_call("spend", amount=1, why="Harl's docking logs"),
)


def behind(state: AnyGame) -> AnyGame:
    """One prior exchange at the starting scene: RECENT PLAY has to render it."""
    state = narrowed(state, TwentyfourxxGame)
    draft = state.draft()
    draft.log[0].exchanges.append(
        Exchange(
            words="I look around the docking ring before going further.",
            lines=(SpokenLine(text="Vessa Rune watches you from the airlock."),),
        )
    )
    return draft.commit()
