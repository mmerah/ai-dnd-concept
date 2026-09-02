from aidm.core.views import Panel, PanelRow, PlayerView, Rows
from aidm.engines import scenes
from aidm.engines.core import party_rows
from aidm.engines.hub import master_tail, question_heading
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
    world = state.payload.world
    scene = world.current
    gear_lines: list[str] = []
    for key, item in world.player.items.items():
        line = f"- {item.name}[{key}]"
        if detail := gear_detail(item):
            line += f" — {detail}"
        gear_lines.append(line)
    return (
        ("SCENE", f"{scene.title}\n{scene.situation}"),
        (question_heading(world.at_hub), scene.question),
        ("YOU PLAY FOR", scenes.entity_line(world.player)),
        ("GEAR", "\n".join(gear_lines) or "- (none)"),
        ("HERE WITH THE PLAYER", scenes.here_lines(world)),
        *party_rows(world.members()),
        ("HIDDEN HERE (the player has not found these)", scenes.hidden_lines(world)),
        ("THE SCENE'S SECRET (never narrate this)", scene.secret or "(none)"),
        *master_tail(world.hub, world.at_hub, world.board, world.jobs(), world.job),
    )


def player_view(state: TwentyfourxxGame) -> PlayerView:
    gear_rows = tuple(
        PanelRow(label=item.name, detail=gear_detail(item))
        for item in state.payload.world.player.items.values()
    )
    return scenes.player_view(state, (Panel(title="Gear", rows=gear_rows),))
