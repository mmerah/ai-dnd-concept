from support.table import Call, changed, narrowed, tool_call

from aidm.core.model import AnyGame
from aidm.core.play import Exchange, SpokenLine
from aidm.engines.twentyfourxx.world import TwentyfourxxGame

SCRIPT: tuple[Call, ...] = (
    changed("reveal", entity_id="warden-six"),
    tool_call("attempt", what="Slip along the dark gantry", skill="Stealth"),
    changed("spend", amount=1, why="Harl's docking logs"),
)


def behind(state: AnyGame) -> AnyGame:
    """One prior exchange at the starting scene: RECENT PLAY has to render it."""
    state = narrowed(state, TwentyfourxxGame)
    draft = state.draft()
    draft.payload.runs[0].exchanges.append(
        Exchange(
            prompt="I look around the docking ring before going further.",
            lines=(SpokenLine(text="Vessa Rune watches you from the airlock."),),
        )
    )
    return draft.commit()
