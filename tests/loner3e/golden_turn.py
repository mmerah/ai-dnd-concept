from support.golden_turn import LISTENING
from support.table import Call, changed, tool_call

from aidm.core.model import AnyGame
from aidm.core.play import Exchange, SpokenLine
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.world import Loner3eGame
from aidm.engines.scenes.world import SceneRun

SCRIPT: tuple[Call, ...] = (
    changed("reveal", entity_id="vault-map"),
    tool_call(
        "roll_question",
        actor_id="player",
        question="Does he hear what waits past the vault door without being heard?",
        position="advantage",
        edge="Quiet Hands",
    ),
    LISTENING,
)


def behind(state: AnyGame) -> AnyGame:
    """One played turn in the scene before this one: RECENT PLAY has to group by run, not title."""
    assert isinstance(state, Loner3eGame), (
        f"unsupported golden engine state: {type(state).__name__}"
    )
    draft = state.draft()
    draft.payload.runs.insert(
        0,
        SceneRun(
            place="vault-stair",
            title="The Vault Stair",
            question="Is there a way past the vault door from the stair?",
            situation=(
                "A short flight of steps ends at an iron door, sealed, "
                "the abbey's dust undisturbed on its sill."
            ),
            here=[PLAYER_ID],
            exchanges=[
                Exchange(
                    prompt="I try the vault door.",
                    lines=(SpokenLine(text="The iron handle does not turn."),),
                )
            ],
        ),
    )
    draft.payload.run.exchanges = [
        Exchange(
            prompt="I look for another way in.",
            lines=(SpokenLine(text="A flagstone by the wall sits proud of its neighbours."),),
        )
    ]
    return draft.commit()
