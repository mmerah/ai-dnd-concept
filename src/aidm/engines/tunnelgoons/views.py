from collections.abc import Iterable

from aidm.core.views import PanelRow
from aidm.engines.tunnelgoons.world import TunnelGoonsWorld

REPORT_IN = "Report in."
REPORT_ROW = PanelRow(label="Report in", detail="Tell the tavern how it went.", intent=REPORT_IN)


def place_lines(world: TunnelGoonsWorld, *, known: bool) -> str:
    npcs_here = [one for one in world.at(world.current.id) if one.known == known]
    holders = (world.current.id, *(one.id for one in world.at(world.current.id)))
    items = (item for holder in holders for item in world.carried(holder) if item.known == known)
    return lines_of(world.line(one) for one in (*npcs_here, *items))


def ways_lines(world: TunnelGoonsWorld) -> str:
    return lines_of(
        f"- {world.require_place(way.to).name}[{way.to}] — "
        + ("known" if way.known else "unknown")
        + ("; locked" if way.locked else "")
        for way in world.ways.get(world.current.id, ())
    )


def lines_of(parts: Iterable[str]) -> str:
    return "\n".join(parts) or "- (none)"
