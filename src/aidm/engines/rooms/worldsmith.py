from collections.abc import Sequence

from aidm.core.entities import Refusal
from aidm.core.play import Chapter
from aidm.core.prompt import Sections, render_history
from aidm.engines.base import Person
from aidm.engines.rooms.world import Dungeon, Dweller, MapDraft, RoomWorld

MAP_ASK = "Write the opening map."


def map_sections[N: Dweller, P: Person](
    world: RoomWorld[N, P] | None, log: Sequence[Chapter]
) -> Sections:
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
    if unmet := _map_unmet(draft, start_known=True):
        raise Refusal("the map needs " + "; ".join(unmet))


def check_extension[N: Dweller](draft: MapDraft[N], world: Dungeon[N]) -> None:
    if not draft.places:
        raise Refusal("the extension needs at least one new place")
    if unmet := _map_unmet(draft, start_known=False) + _overlap_unmet(draft, world):
        raise Refusal("the extension needs " + "; ".join(unmet))


def _map_unmet[N: Dweller](draft: MapDraft[N], *, start_known: bool) -> list[str]:
    places = draft.places
    if draft.start not in places:
        return [f"a starting place {draft.start!r}"]
    unmet: list[str] = []
    if places[draft.start].known != start_known:
        unmet.append(
            "the starting place known to the player"
            if start_known
            else "a starting place hidden from the player"
        )
    if missing := sorted(set(places) - draft.reachable(draft.start)):
        unmet.append(f"places no walk of ways reaches from {draft.start!r}: {missing}")
    return unmet


def _overlap_unmet[N: Dweller](draft: MapDraft[N], world: Dungeon[N]) -> list[str]:
    existing = {*world.places, *world.npcs, *world.items}
    added = {*draft.places, *draft.npcs, *draft.items}
    if overlap := sorted(existing & added):
        return [f"ids not already in the world: {overlap}"]
    return []
