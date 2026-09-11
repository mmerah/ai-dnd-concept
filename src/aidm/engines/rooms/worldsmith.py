from collections.abc import Sequence

from aidm.core.entities import Refusal
from aidm.core.play import Chapter
from aidm.core.prompt import Pairs, render_history
from aidm.engines.base import Person
from aidm.engines.rooms.world import Dungeon, Dweller, MapDraft, RoomWorld

MAP_ASK = "Write the opening map."


def map_sections[N: Dweller, P: Person](
    world: RoomWorld[N, P] | None, log: Sequence[Chapter]
) -> Pairs:
    if world is None:
        return (
            ("MAP SO FAR", "(no map yet)"),
            ("SCENES SO FAR", "(no scenes yet — write the opening)"),
            ("THE PLAYER", "(no player yet — the map is authored before anyone stands in it)"),
        )
    return (
        ("MAP SO FAR", world.map_so_far()),
        ("SCENES SO FAR", render_history(log)),
        ("THE PLAYER", world.line(world.player)),
    )


def check_map[N: Dweller](draft: MapDraft[N]) -> None:
    if unmet := _start_unmet(draft):
        raise Refusal("the map needs " + "; ".join(unmet))


def check_extension[N: Dweller](draft: MapDraft[N], world: Dungeon[N]) -> None:
    if unmet := _extension_unmet(draft) + _overlap_unmet(draft, world):
        raise Refusal("the extension needs " + "; ".join(unmet))


def _start_unmet[N: Dweller](draft: MapDraft[N]) -> list[str]:
    places = draft.places
    unmet: list[str] = []
    if draft.start not in places:
        unmet.append(f"a starting place {draft.start!r}")
    else:
        if not places[draft.start].known:
            unmet.append("the starting place known to the player")
        if missing := sorted(set(places) - draft.reachable(draft.start)):
            unmet.append(f"places no walk of ways reaches from {draft.start!r}: {missing}")
    return unmet


def _extension_unmet[N: Dweller](draft: MapDraft[N]) -> list[str]:
    places = draft.places
    if not places:
        return ["at least one new place"]
    unmet: list[str] = []
    if draft.start not in places:
        unmet.append(f"a starting place {draft.start!r}")
    else:
        if places[draft.start].known:
            unmet.append("a starting place hidden from the player")
        if missing := sorted(set(places) - draft.reachable(draft.start)):
            unmet.append(f"places no walk of ways reaches from {draft.start!r}: {missing}")
    return unmet


def _overlap_unmet[N: Dweller](draft: MapDraft[N], world: Dungeon[N]) -> list[str]:
    existing = {*world.places, *world.npcs, *world.items}
    added = {*draft.places, *draft.npcs, *draft.items}
    if overlap := sorted(existing & added):
        return [f"ids not already in the world: {overlap}"]
    return []
