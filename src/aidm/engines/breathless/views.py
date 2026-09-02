from aidm.core.views import Panel, PanelRow, PlayerView, Rows
from aidm.engines import scenes
from aidm.engines.breathless.world import BreathlessGame
from aidm.engines.core import party_rows
from aidm.engines.hub import master_tail, question_heading


def master_sections(state: BreathlessGame) -> Rows:
    """Every section stated, hidden canon included: the game master reads all of it."""
    world = state.payload.world
    scene = world.current
    player = world.player
    backpack_lines = [f"- {item.name}[{key}] — d{item.die}" for key, item in player.items.items()]
    if player.med_kit:
        backpack_lines.append("- med kit")
    return (
        ("SCENE", f"{scene.title}\n{scene.situation}"),
        (question_heading(world.at_hub), scene.question),
        ("YOU PLAY FOR", scenes.entity_line(player)),
        ("BACKPACK", "\n".join(backpack_lines) or "- (none)"),
        ("HERE WITH THE PLAYER", scenes.here_lines(world)),
        *party_rows(world.members()),
        ("HIDDEN HERE (the player has not found these)", scenes.hidden_lines(world)),
        ("THE SCENE'S SECRET (never narrate this)", scene.secret or "(none)"),
        *master_tail(world.hub, world.at_hub, world.board, world.jobs(), world.job),
    )


def player_view(state: BreathlessGame) -> PlayerView:
    player = state.payload.world.player
    backpack_rows = [
        PanelRow(label=item.name, detail=f"d{item.die}") for item in player.items.values()
    ]
    if player.med_kit:
        backpack_rows.append(PanelRow(label="Med kit", detail="held"))
    return scenes.player_view(state, (Panel(title="Backpack", rows=tuple(backpack_rows)),))
