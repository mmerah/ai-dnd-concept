from pathlib import Path
from random import Random

from aidm.engines.packs import load_packs, pack_paths
from aidm.engines.sheet_engine import SheetEngine
from aidm.engines.sheets import resolved_threads
from aidm.state.base import Counter, EngineId, Entity
from aidm.state.world import GameState

from .actions import TurnBeat, TurnPlan, TwentyfourxxAction
from .advance import TwentyfourxxAdvancement
from .create import TwentyfourxxCreation
from .mechanics import EFFECTS, Mechanics, Sheet, describe_entity
from .pack import Pack

ENGINE_ID: EngineId = EngineId("twentyfourxx")


class TwentyfourxxEngine(SheetEngine[Sheet, TwentyfourxxAction]):
    id = ENGINE_ID
    badge = ("24XX", "indigo-7")
    engine_dir = Path(__file__).parent
    plan_type = TurnPlan
    beat_type = TurnBeat
    sheet_type = Sheet
    mechanics_type = Mechanics
    effects = EFFECTS

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.subsystems = (TwentyfourxxAdvancement(self.engine_dir),)
        self.creation = TwentyfourxxCreation(self.packs)

    def new_sheet(self, draft: GameState, rng: Random) -> Sheet:
        del rng  # nothing on a fresh 24xx sheet is rolled
        # A newcomer starts level with the party: jobs done before they joined are not owed.
        return Sheet(jobs=Counter(current=resolved_threads(draft.world)))

    def describe(self, state: GameState, entity: Entity) -> str:
        return describe_entity(state.mechanics_as(Mechanics), entity)


ENGINE = TwentyfourxxEngine
