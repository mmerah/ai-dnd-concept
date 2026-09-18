from aidm.core.entities import Refusal
from aidm.core.prompt import Sections
from aidm.engines.base import PLAYER_ID, leaked_names, required_unmet
from aidm.engines.rooms.world import Dungeon, Dweller, MapProposal

MAP_ASK = "Write the opening map."
OPENING_SECTIONS: Sections = (
    ("MAP SO FAR", "(no map yet)"),
    ("SCENES SO FAR", "(no scenes yet — write the opening)"),
    ("THE PLAYER", "(no player yet — the map is authored before anyone stands in it)"),
)


def check_map[N: Dweller](draft: MapProposal[N]) -> None:
    if unmet := _map_unmet(draft, start_known=True) + _named_unmet(draft):
        raise Refusal("the map needs " + "; ".join(unmet))


def check_extension[N: Dweller](draft: MapProposal[N], world: Dungeon[N]) -> None:
    if not draft.places:
        raise Refusal("the extension needs at least one new place")
    if unmet := (
        _map_unmet(draft, start_known=False)
        + _overlap_unmet(draft, world)
        + _named_unmet(draft)
        + _planted_unmet(draft)
    ):
        raise Refusal("the extension needs " + "; ".join(unmet))


def _planted_unmet[N: Dweller](draft: MapProposal[N]) -> list[str]:
    """An extension may not put items straight into the player's pack: no fact, no narration."""
    if planted := sorted(item.id for item in draft.items.values() if item.on == PLAYER_ID):
        return [f"no item planted on the player: {planted}"]
    return []


def _map_unmet[N: Dweller](draft: MapProposal[N], *, start_known: bool) -> list[str]:
    places = draft.places
    if draft.start not in places:
        return [f"a starting place {draft.start!r}"]
    unmet: list[str] = []
    if broken := required_unmet(draft.npcs, ()):
        unmet.append(f"npcs as the worldsmith may write them: {broken}")
    if places[draft.start].known != start_known:
        unmet.append(
            "the starting place known to the player"
            if start_known
            else "a starting place hidden from the player"
        )
    if missing := sorted(set(places) - draft.reachable(draft.start)):
        unmet.append(f"places no walk of ways reaches from {draft.start!r}: {missing}")
    return unmet


def _overlap_unmet[N: Dweller](draft: MapProposal[N], world: Dungeon[N]) -> list[str]:
    existing = {*world.places, *world.npcs, *world.items}
    added = {*draft.places, *draft.npcs, *draft.items}
    if overlap := sorted(existing & added):
        return [f"ids not already in the world: {overlap}"]
    return []


def _named_unmet[N: Dweller](draft: MapProposal[N]) -> list[str]:
    leaked: set[str] = set()
    hidden = [thing for thing in (*draft.npcs.values(), *draft.items.values()) if not thing.known]
    for place_id, place in draft.places.items():
        things = [
            *draft.things_at(place_id),
            *(draft.carried(PLAYER_ID) if place_id == draft.start else ()),
        ]
        read = "\n".join((place.name, place.brief, place.description))
        leaked.update(leaked_names(read, things, hidden))
    if named := sorted(leaked):
        return [f"places that do not name what the player has not met: {named}"]
    return []
