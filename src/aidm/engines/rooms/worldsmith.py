from aidm.core.entities import Refusal
from aidm.engines.rooms.world import Dungeon, Dweller, MapDraft
from aidm.engines.scenes.worldsmith import named_unmet

MAP_ASK = "Write the opening map."


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
    if named := sorted(
        {
            name
            for place_id, place in places.items()
            for name in named_unmet(
                place.description,
                (
                    *(
                        npc
                        for npc in draft.npcs.values()
                        if npc.place == place_id and not npc.known
                    ),
                    *(
                        item
                        for item in draft.items.values()
                        if item.on == place_id and not item.known
                    ),
                ),
            )
        }
    ):
        unmet.append(f"place descriptions that do not name what is hidden there: {named}")
    return unmet


def _overlap_unmet[N: Dweller](draft: MapDraft[N], world: Dungeon[N]) -> list[str]:
    existing = {*world.places, *world.npcs, *world.items}
    added = {*draft.places, *draft.npcs, *draft.items}
    if overlap := sorted(existing & added):
        return [f"ids not already in the world: {overlap}"]
    return []
