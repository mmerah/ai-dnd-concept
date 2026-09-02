from collections.abc import Mapping

from aidm.core.views import Rows
from aidm.engines.core import party_rows
from aidm.engines.hub import master_tail, question_heading
from aidm.engines.loner3e.creation import Pack
from aidm.engines.loner3e.tools import meanings
from aidm.engines.loner3e.world import Loner3eGame
from aidm.engines.scenes.world import entity_line


def master_sections(packs: Mapping[str, Pack], state: Loner3eGame) -> Rows:
    """Every section stated, hidden canon included: the game master reads all of it."""
    world = state.payload.world
    scene = world.current
    glossary: dict[str, str] = {}
    for one in world.here():
        glossary.update(meanings(packs, state.packs, one))
    lines = "\n".join(f"- {tag}: {detail}" for tag, detail in glossary.items())
    spelled = (("WHAT THE TAGS IN PLAY MEAN", lines),) if glossary else ()
    return (
        ("SCENE", f"{scene.title}\n{scene.situation}"),
        (question_heading(world.at_hub), scene.question),
        ("YOU PLAY FOR", entity_line(world.player)),
        ("HERE WITH THE PLAYER", world.here_lines()),
        *party_rows(world.members()),
        ("HIDDEN HERE (the player has not found these)", world.hidden_lines()),
        *spelled,
        ("THE SCENE'S SECRET (never narrate this)", scene.secret or "(none)"),
        *master_tail(world.hub, world.at_hub, world.board, world.jobs(), world.job),
    )
