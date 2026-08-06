from aidm.core.engine import AdvancementOffer
from aidm.core.packs import Content, ContentMiss, ContentRef, LenientRecord
from aidm.core.sheet import Sheet, SheetDelta, apply_delta
from aidm.core.world import GameState, player_sheet, sheet_of

ADVANCEMENT_READY = "advancement-ready"
LEVEL = "level"
MILESTONE_LEVEL = "milestone-level"


def offered(state: GameState, content: Content) -> AdvancementOffer | None:
    sheet = player_sheet(state)
    if sheet.tag(ADVANCEMENT_READY) is None and not _milestone_reached(state, sheet):
        return None
    next_level = sheet.numbers[LEVEL] + 1
    record = content.get(level_ref(sheet, next_level), LenientRecord)
    if isinstance(record, ContentMiss):
        # The class runs out of level rows at 20, which is the end of advancement, not a fault.
        return None
    return AdvancementOffer(
        prompt=f"{record.name} is ready to take.",
        text=record.text,
        options=record.options,
        choose=record.choose or 0,
    )


def _milestone_reached(state: GameState, sheet: Sheet) -> bool:
    here = sheet_of(state, state.player_location)
    earned = here.numbers.get(MILESTONE_LEVEL)
    return earned is not None and sheet.numbers[LEVEL] < earned


def check(state: GameState, offer: AdvancementOffer, delta: SheetDelta) -> str | None:
    del offer
    before = player_sheet(state)
    after = before.model_copy(deep=True)
    _ = apply_delta(after, delta)
    reached = before.numbers[LEVEL] + 1
    if after.numbers[LEVEL] != reached:
        return f"this level-up reaches level {reached}: set `{LEVEL}` to exactly that"
    if before.tag(ADVANCEMENT_READY) is not None and after.tag(ADVANCEMENT_READY) is not None:
        return f"the level-up is spent by removing the {ADVANCEMENT_READY!r} tag"
    return None


def level_ref(sheet: Sheet, level: int) -> ContentRef:
    classes = [ref for ref in sheet.refs if ref.collection == "classes"]
    if len(classes) != 1:
        held = ", ".join(str(ref) for ref in classes) or "(none)"
        raise ValueError(f"a 5e character advances by exactly one class, and this one holds {held}")
    return classes[0].sibling("levels", f"{classes[0].index}-{level}")
