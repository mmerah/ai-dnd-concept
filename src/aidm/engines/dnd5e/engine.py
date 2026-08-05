from collections.abc import Sequence
from pathlib import Path

from aidm.core.config import Settings
from aidm.core.engine import AdvancementOffer, Engine
from aidm.core.enginepack import load_engine
from aidm.core.packs import Content, ContentMiss, ContentRef, LenientRecord, Value
from aidm.core.registry import EnginePlugin
from aidm.core.sheet import Sheet, SheetDelta, apply_delta, player_sheet
from aidm.core.world import GameState, rules_of

from .identity import ENGINE_ID

ENGINE_DIR = Path(__file__).parent
ADVANCEMENT_READY = "advancement-ready"
LEVEL = "level"
MILESTONE_LEVEL = "milestone-level"


class Dnd5eConfig(Value):
    pack_paths: tuple[Path, ...] | None = None


def _offered(state: GameState[Sheet], content: Content) -> AdvancementOffer | None:
    sheet = player_sheet(state)
    if sheet.tag(ADVANCEMENT_READY) is None and not _milestone_reached(state, sheet):
        return None
    next_level = sheet.numbers[LEVEL] + 1
    record = content.get(_level_ref(sheet, next_level), LenientRecord)
    if isinstance(record, ContentMiss):
        # The class runs out of level rows at 20, which is the end of advancement, not a fault.
        return None
    return AdvancementOffer(
        prompt=f"{record.name} is ready to take.",
        text=record.text,
        options=record.options,
        choose=record.choose or 0,
    )


def _milestone_reached(state: GameState[Sheet], sheet: Sheet) -> bool:
    """A milestone is a fact the scenario states, not a judgment: a location's `milestone-level`
    opens the offer to any player standing there below it."""
    here = rules_of(state.world.record(state.player_location), Sheet)
    earned = here.numbers.get(MILESTONE_LEVEL)
    return earned is not None and sheet.numbers[LEVEL] < earned


def _check(state: GameState[Sheet], offer: AdvancementOffer, delta: SheetDelta) -> str | None:
    """5e's own caps: the level moves by exactly one, and a tag that opened the offer is spent."""
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


def _level_ref(sheet: Sheet, level: int) -> ContentRef:
    classes = [ref for ref in sheet.refs if ref.collection == "classes"]
    if len(classes) != 1:
        held = ", ".join(str(ref) for ref in classes) or "(none)"
        raise ValueError(f"a 5e character advances by exactly one class, and this one holds {held}")
    return classes[0].sibling("levels", f"{classes[0].index}-{level}")


def build_dnd5e_engine(pack_paths: Sequence[Path] | None = None) -> Engine[Sheet]:
    return load_engine(ENGINE_DIR, ENGINE_ID, pack_paths, offered=_offered, check=_check)


def _build(config: Settings) -> Engine[Sheet]:
    section = Dnd5eConfig.model_validate(config.engines.get(ENGINE_ID, {}))
    return build_dnd5e_engine(section.pack_paths)


PLUGIN = EnginePlugin(id=ENGINE_ID, build=_build, badge=("D&D 5E", "red-9"))
