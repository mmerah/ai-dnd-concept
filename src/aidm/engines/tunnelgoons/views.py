from collections.abc import Iterable

from aidm.core.views import (
    NarratorView,
    Panel,
    PanelRow,
    PlayerView,
    Rows,
    Subject,
    speaker_of,
)
from aidm.engines.core import pool
from aidm.engines.hub import board_rows, jobs_panel, master_tail
from aidm.engines.tunnelgoons.world import (
    Goon,
    Item,
    Npc,
    TunnelGoonsGame,
    TunnelWorld,
    player_over,
)

REPORT_IN = "Report in."
REPORT_ROW = PanelRow(label="Report in", detail="Tell the tavern how it went.", intent=REPORT_IN)


def subject_of(one: Goon | Npc) -> Subject:
    return Subject(id=one.id, name=one.name, brief=one.brief)


def narrator_view(state: TunnelGoonsGame) -> NarratorView:
    world = state.payload.world
    place = world.current
    here = tuple(
        sorted(
            (one for one in world.here() if one.known), key=lambda one: one.id != world.player.id
        )
    )
    subjects = tuple(subject_of(one) for one in here)
    return NarratorView(
        place=place.id,
        title=place.name,
        focus=place.brief,
        situation=place.description,
        subjects=subjects,
        # A corpse may stay a subject in the room; it does not speak.
        speakers=tuple(speaker_of(subject_of(one)) for one in here if one.alive),
    )


def player_view(state: TunnelGoonsGame) -> PlayerView:
    world = state.payload.world
    player = world.player
    ways = world.ways.get(world.current.id, ())
    return PlayerView(
        player=subject_of(player),
        panels=(
            Panel(
                title="Character",
                rows=tuple(
                    PanelRow(label=label, detail=detail)
                    for label, detail in _character_rows(world, player)
                ),
            ),
            Panel(title="Here", rows=tuple(_here_rows(world, player))),
            Panel(
                title="Carrying",
                rows=tuple(
                    PanelRow(label=item.name, detail=item.brief, icon_id=item.id)
                    for item in world.carried(player.id)
                ),
            ),
            Panel(
                title="Ways out",
                rows=tuple(
                    PanelRow(
                        label=world.require_place(way.to).name,
                        detail="locked" if way.locked else "",
                    )
                    for way in ways
                    if way.known
                ),
            ),
            *(
                (
                    Panel(
                        title="Board",
                        rows=(REPORT_ROW,) if world.job_open else board_rows(world.board),
                    ),
                )
                if world.at_hub
                else ()
            ),
            Panel(
                title="Trail",
                rows=tuple(
                    PanelRow(label=world.require_place(v.place).name, detail="")
                    for v in world.job_visits()
                ),
            ),
            *jobs_panel(world.jobs()),
        ),
        prompt=state.pending,
        over=player_over(state),
    )


def master_sections(state: TunnelGoonsGame) -> Rows:
    """Every section stated, hidden canon included: the game master reads all of it."""
    world = state.payload.world
    place = world.current
    player = world.player
    return (
        ("CURRENT PLACE", f"{place.name}[{place.id}]\n{place.description}"),
        ("YOU PLAY FOR", entity_line(world, player)),
        ("CARRYING", _lines(entity_line(world, item) for item in world.carried(player.id))),
        ("HERE WITH THE PLAYER", _place_lines(world, known=True)),
        ("HIDDEN HERE (the player has not found these)", _place_lines(world, known=False)),
        ("WAYS OUT", _ways_lines(world)),
        *master_tail(world.hub, world.at_hub, world.board, world.jobs(), ""),
    )


def entity_line(world: TunnelWorld, one: Goon | Npc | Item) -> str:
    """One card line, its sheet shaped by what kind of entity it names."""
    line = f"- {one.name}[{one.id}]" + (f" — {one.brief}" if one.brief else "")
    if isinstance(one, Goon):
        sheet = "; ".join(
            f"{label.lower()}: {value}" for label, value in _character_rows(world, one)
        )
    elif isinstance(one, Npc):
        sheet = f"health: {pool(one.hp)} (its Difficulty Score)"
    else:
        sheet = ""
    if isinstance(one, Goon | Npc) and not one.alive:
        line += " (dead)"
    return f"{line}\n  {sheet}" if sheet else line


def _character_rows(world: TunnelWorld, player: Goon) -> Rows:
    carried = len(list(world.carried(player.id)))
    return tuple(
        (label, f"{carried}/{player.inventory}") if label == "Inventory" else (label, value)
        for label, value in player.rows()
    )


def _here_rows(world: TunnelWorld, player: Goon) -> list[PanelRow]:
    rows = [PanelRow(label=f"{player.name} (you)", detail=player.brief, icon_id=player.id)]
    rows.extend(
        PanelRow(label=one.name, detail=one.brief, icon_id=one.id)
        for one in world.at(world.current.id)
        if one.known
    )
    return rows


def _place_lines(world: TunnelWorld, *, known: bool) -> str:
    npcs_here = [one for one in world.at(world.current.id) if one.known == known]
    holders = (world.current.id, *(one.id for one in world.at(world.current.id)))
    items = (item for holder in holders for item in world.carried(holder) if item.known == known)
    return _lines(entity_line(world, one) for one in (*npcs_here, *items))


def _ways_lines(world: TunnelWorld) -> str:
    return _lines(
        f"- {world.require_place(way.to).name}[{way.to}] — "
        + ("known" if way.known else "unknown")
        + ("; locked" if way.locked else "")
        for way in world.ways.get(world.current.id, ())
    )


def _lines(parts: Iterable[str]) -> str:
    return "\n".join(parts) or "- (none)"
