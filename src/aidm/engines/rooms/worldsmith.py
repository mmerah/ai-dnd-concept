from aidm.core.entities import Refusal
from aidm.engines.base import named_unmet
from aidm.engines.rooms.world import Dungeon, Dweller, MapDraft

MAP_ASK = "Write the opening map."


def check_map[N: Dweller](draft: MapDraft[N]) -> None:
    if unmet := _map_unmet(draft, start_known=True) + _named_unmet(draft):
        raise Refusal("the map needs " + "; ".join(unmet))


def check_extension[N: Dweller](draft: MapDraft[N], world: Dungeon[N]) -> None:
    if not draft.places:
        raise Refusal("the extension needs at least one new place")
    if unmet := (
        _map_unmet(draft, start_known=False) + _overlap_unmet(draft, world) + _named_unmet(draft)
    ):
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


def _named_unmet[N: Dweller](draft: MapDraft[N]) -> list[str]:
    if named := sorted(
        {
            name
            for place_id, place in draft.places.items()
            for name in named_unmet(
                f"{place.name}\n{place.brief}\n{place.description}",
                (thing for thing in draft.things_at(place_id) if not thing.known),
            )
        }
    ):
        return [f"places that do not name what is hidden there: {named}"]
    return []
