from collections.abc import Mapping

from aidm.core.views import Rows
from aidm.engines import scenes
from aidm.engines.core import party_rows
from aidm.engines.hub import master_tail, question_heading
from aidm.engines.loner3e.creation import Pack
from aidm.engines.loner3e.tools import meanings
from aidm.engines.loner3e.world import Loner3eGame


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
        ("YOU PLAY FOR", scenes.entity_line(world.player)),
        ("HERE WITH THE PLAYER", scenes.here_lines(world)),
        *party_rows(world.members()),
        ("HIDDEN HERE (the player has not found these)", scenes.hidden_lines(world)),
        *spelled,
        ("THE SCENE'S SECRET (never narrate this)", scene.secret or "(none)"),
        *scenes.recap_rows(world),
        *master_tail(world.hub, world.at_hub, world.board, world.jobs(), world.job),
    )
