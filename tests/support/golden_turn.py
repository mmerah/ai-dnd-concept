import json
from collections.abc import Callable
from functools import partial

from aidm.core.entities import EngineId
from aidm.core.model import AnyGame
from aidm.core.play import Chapter, Exchange, SpokenLine
from aidm.engines.base import PLAYER_ID
from aidm.engines.scenes.world import SceneRun
from support.table import Call, tool_call

NARRATION = "The flagstone lifts. Beyond the door, something shifts its weight and waits."
INTERJECTION = json.dumps(
    {
        "lines": [{"speaker_id": "vessa-rune", "text": "Six days locked to a dark relay."}],
        "proposal": "I ask Vessa why she hasn't left the docking ring.",
    }
)

LISTENING = tool_call(
    "change_tags",
    entity_id="player",
    kind="condition",
    gained=["Listening"],
)


def _one_exchange(state: AnyGame, words: str, said: str) -> AnyGame:
    """One prior exchange at the starting scene: RECENT PLAY has to render it."""
    draft = state.draft()
    draft.log[0].exchanges.append(Exchange(words=words, lines=(SpokenLine(text=said),)))
    return draft.commit()


def _loner3e_behind(state: AnyGame) -> AnyGame:
    """One played turn in the scene before this one: RECENT PLAY has to group by run, not title."""
    draft = state.draft()
    draft.payload.runs.insert(
        0,
        SceneRun(
            place="vault-stair",
            title="The Vault Stair",
            focus="Is there a way past the vault door from the stair?",
            situation=(
                "A short flight of steps ends at an iron door, sealed, "
                "the abbey's dust undisturbed on its sill."
            ),
            here=[PLAYER_ID],
        ),
    )
    draft.log.insert(
        0,
        Chapter(
            title="The Vault Stair",
            focus="Is there a way past the vault door from the stair?",
            exchanges=[
                Exchange(
                    words="I try the vault door.",
                    lines=(SpokenLine(text="The iron handle does not turn."),),
                )
            ],
        ),
    )
    draft.log[-1].exchanges = [
        Exchange(
            words="I look for another way in.",
            lines=(SpokenLine(text="A flagstone by the wall sits proud of its neighbours."),),
        )
    ]
    return draft.commit()


_LONER3E_SCRIPT: tuple[Call, ...] = (
    tool_call("reveal", entity_id="vault-map"),
    tool_call(
        "roll",
        what="Listen at the vault door",
        actor_id="player",
        question="Does he hear what waits past the vault door without being heard?",
        position="advantage",
        edge="Quiet Hands",
    ),
    LISTENING,
)

_TUNNELGOONS_SCRIPT: tuple[Call, ...] = (
    tool_call("move", to_id="cellar"),
    tool_call(
        "roll",
        what="Wade through the flooded cellar",
        ability="skulker",
        difficulty=10,
        dangerous=True,
    ),
    tool_call("reveal", entity_id="lurker"),
)

_TWENTYFOURXX_SCRIPT: tuple[Call, ...] = (
    tool_call("join_party", entity_id="vessa-rune"),
    tool_call("reveal", entity_id="warden-six"),
    tool_call("roll", what="Slip along the dark gantry", skill="Stealth"),
    tool_call("spend", amount=1, why="Harl's docking logs"),
)

SCRIPTS: dict[EngineId, tuple[tuple[Call, ...], Callable[[AnyGame], AnyGame]]] = {
    EngineId("loner3e"): (_LONER3E_SCRIPT, _loner3e_behind),
    EngineId("tunnelgoons"): (
        _TUNNELGOONS_SCRIPT,
        partial(
            _one_exchange,
            words="I look around the archway before going further.",
            said="Grix waves you toward the corridor, impatient.",
        ),
    ),
    EngineId("twentyfourxx"): (
        _TWENTYFOURXX_SCRIPT,
        partial(
            _one_exchange,
            words="I look around the docking ring before going further.",
            said="Vessa Rune watches you from the airlock.",
        ),
    ),
}
