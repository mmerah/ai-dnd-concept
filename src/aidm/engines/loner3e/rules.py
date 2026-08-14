from pathlib import Path
from random import Random

from aidm.engines.packs import load_packs, pack_paths
from aidm.engines.sheet_engine import SheetEngine
from aidm.engines.sheets import resolved_threads
from aidm.state.base import PLAYER_ID, Counter, EngineId, Entity
from aidm.state.world import GameState

from .actions import Question, TurnBeat, TurnPlan
from .advance import Loner3eAdvancement
from .create import Loner3eCreation
from .mechanics import EFFECTS, Mechanics, Sheet, describe_entity
from .pack import Pack, twist_table

ENGINE_ID: EngineId = EngineId("loner3e")


class Loner3eEngine(SheetEngine[Sheet, Question]):
    id = ENGINE_ID
    badge = ("LONER 3E", "teal-7")
    engine_dir = Path(__file__).parent
    plan_type = TurnPlan
    beat_type = TurnBeat
    sheet_type = Sheet
    mechanics_type = Mechanics
    effects = EFFECTS

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.subsystems = (Loner3eAdvancement(self.engine_dir),)
        self.creation = Loner3eCreation(self.packs)

    def check_mechanics(self, state: GameState) -> None:
        if (chosen := state.mechanics_as(Mechanics).sheets[PLAYER_ID].pack) not in self.packs:
            raise ValueError(f"this game plays the {chosen!r} table set, which is not installed")

    def new_sheet(self, draft: GameState, rng: Random) -> Sheet:
        del rng  # nothing on a loner3e sheet is rolled
        # A newcomer starts level with the party: milestones earned before they joined are not owed.
        return Sheet(milestones=Counter(current=resolved_threads(draft.world)))

    def describe(self, state: GameState, entity: Entity) -> str:
        return describe_entity(state.mechanics_as(Mechanics), entity)

    def twists(self, state: GameState) -> tuple[tuple[str, str], ...]:
        """The player's own table set: an NPC sheet is seeded with the default and never selects."""
        return twist_table(self.packs, state.mechanics_as(Mechanics).sheets[PLAYER_ID].pack)


ENGINE = Loner3eEngine
