from core_test_support import Call, changed, tool_call
from golden_turn_support import LISTENING

from aidm.core.model import AnyGame
from aidm.core.play import Exchange, SpokenLine
from aidm.engines.core import PLAYER_ID
from aidm.engines.loner3e.world import Loner3eGame
from aidm.engines.scenes import Scene, SceneRun

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
    if not isinstance(state, Loner3eGame):
        raise AssertionError(f"unsupported golden engine state: {type(state).__name__}")
    draft = state.draft()
    draft.payload.world.runs.insert(
        0,
        SceneRun(
            scene=Scene(
                place="vault-stair",
                title="The Vault Stair",
                question="Is there a way past the vault door from the stair?",
                situation=(
                    "A short flight of steps ends at an iron door, sealed, "
                    "the abbey's dust undisturbed on its sill."
                ),
            ),
            present=[PLAYER_ID],
            exchanges=[
                Exchange(
                    prompt="I try the vault door.",
                    lines=(SpokenLine(text="The iron handle does not turn."),),
                )
            ],
        ),
    )
    draft.payload.world.run.exchanges = [
        Exchange(
            prompt="I look for another way in.",
            lines=(SpokenLine(text="A flagstone by the wall sits proud of its neighbours."),),
        )
    ]
    return draft.committed()
