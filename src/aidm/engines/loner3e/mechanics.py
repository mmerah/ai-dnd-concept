from aidm.engines.counters import render_counters
from aidm.engines.sheets import SheetBase, SheetMechanics
from aidm.state.base import Counter, Entity, Slug
from aidm.state.creation import ContentSlug

from .pack import SRD_PACK

LUCK_MAX = 6
TIES_PER_TWIST = 3


class Sheet(SheetBase):
    """The one sheet shape, whether it belongs to the player or to an NPC."""

    # The table set this character was built from; the twist table is read from it.
    pack: ContentSlug = SRD_PACK
    concept: str = ""
    skills: tuple[str, ...] = ()
    frailties: tuple[str, ...] = ()
    gear: tuple[str, ...] = ()
    luck: Counter = Counter(current=LUCK_MAX, maximum=LUCK_MAX)
    milestones: Counter = Counter(current=0)

    def counters(self) -> dict[Slug, Counter]:
        return {"luck": self.luck}


class Mechanics(SheetMechanics[Sheet]):
    # One tally for the whole game, as the note it fires says: a tie anywhere moves the same one.
    twist: Counter = Counter(current=0, maximum=TIES_PER_TWIST)
    # How many adventures the fiction has closed, game-wide: what advancement is owed against.
    completed: Counter = Counter(current=0)


def describe_entity(mechanics: Mechanics, entity: Entity) -> str:
    sheet = mechanics.sheets.get(entity.id)
    if sheet is None:
        return ""
    lines = (
        f"concept: {sheet.concept}" if sheet.concept else "",
        f"skills: {', '.join(sheet.skills)}" if sheet.skills else "",
        f"frailties: {', '.join(sheet.frailties)}" if sheet.frailties else "",
        f"gear: {', '.join(sheet.gear)}" if sheet.gear else "",
        f"pools: {render_counters(sheet.counters())}",
    )
    return "\n".join(line for line in lines if line)
