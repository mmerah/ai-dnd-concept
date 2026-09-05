from pydantic import BaseModel

from aidm.core.tools import schema_text
from aidm.core.views import sections
from aidm.engines.rooms.drafts import MapDraft
from aidm.engines.rooms.world import Dungeon, Dweller

MAP_ASK = "Write the opening map."


def worldsmith_prompt(
    role: str,
    *,
    source: str,
    scope: str,
    map_so_far: str,
    history: str,
    player: str,
    intent: str,
    guidance: str,
    answer: type[BaseModel],
) -> str:
    return sections(
        (
            ("YOUR ROLE", role),
            ("SOURCE MATERIAL", source or "(none — write from the setting)"),
            ("THE SCOPE OF PLAY", scope),
            ("MAP SO FAR", map_so_far),
            ("SCENES SO FAR", history),
            ("THE PLAYER", player),
            ("WHAT COMES NEXT", intent),
            ("ENGINE GUIDANCE", guidance),
            ("ANSWER WITH", schema_text(answer)),
        )
    )


def map_refusal[N: Dweller](draft: MapDraft[N]) -> str | None:
    unmet = _start_unmet(draft)
    return None if not unmet else "the map needs " + "; ".join(unmet)


def extension_refusal[N: Dweller](draft: MapDraft[N], world: Dungeon[N]) -> str | None:
    unmet = _extension_unmet(draft) + _overlap_unmet(draft, world)
    return None if not unmet else "the extension needs " + "; ".join(unmet)


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
