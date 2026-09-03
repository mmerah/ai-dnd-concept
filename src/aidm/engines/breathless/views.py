from aidm.core.views import Rows
from aidm.engines.base import party_rows
from aidm.engines.breathless.world import BreathlessGame
from aidm.engines.hub import master_tail, question_heading
from aidm.engines.scenes.world import entity_line


def master_sections(state: BreathlessGame) -> Rows:
    """Every section stated, hidden canon included: the game master reads all of it."""
    world = state.payload
    scene = world.run
    player = world.player
    backpack_lines = [f"- {item.name}[{key}] — d{item.die}" for key, item in player.items.items()]
    if player.med_kit:
        backpack_lines.append("- med kit")
    return (
        ("SCENE", f"{scene.title}\n{scene.situation}"),
        (question_heading(world.at_hub), scene.question),
        ("YOU PLAY FOR", entity_line(player)),
        ("BACKPACK", "\n".join(backpack_lines) or "- (none)"),
        ("HERE WITH THE PLAYER", world.here_lines()),
        *party_rows(world.members()),
        ("HIDDEN HERE (the player has not found these)", world.hidden_lines()),
        *master_tail(world.hub, world.at_hub, world.board, world.closed_jobs(), world.open_job()),
    )
