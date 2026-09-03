from aidm.core.views import Rows
from aidm.engines.core import party_rows
from aidm.engines.hub import master_tail, question_heading
from aidm.engines.scenes.world import entity_line
from aidm.engines.twentyfourxx.world import Item, TwentyfourxxGame


def gear_detail(item: Item) -> str:
    parts: list[str] = []
    if item.bulky:
        parts.append("bulky")
    if item.broken:
        parts.append("broken")
    elif item.breaks > 1 and item.broken_times > 0:
        parts.append(f"broken {item.broken_times}/{item.breaks}")
    return ", ".join(parts)


def master_sections(state: TwentyfourxxGame) -> Rows:
    """Every section stated, hidden canon included: the game master reads all of it."""
    world = state.payload
    scene = world.run
    gear_lines: list[str] = []
    for key, item in world.player.items.items():
        line = f"- {item.name}[{key}]"
        if detail := gear_detail(item):
            line += f" — {detail}"
        gear_lines.append(line)
    return (
        ("SCENE", f"{scene.title}\n{scene.situation}"),
        (question_heading(world.at_hub), scene.question),
        ("YOU PLAY FOR", entity_line(world.player)),
        ("GEAR", "\n".join(gear_lines) or "- (none)"),
        ("HERE WITH THE PLAYER", world.here_lines()),
        *party_rows(world.members()),
        ("HIDDEN HERE (the player has not found these)", world.hidden_lines()),
        *master_tail(world.hub, world.at_hub, world.board, world.closed_jobs(), world.open_job()),
    )
