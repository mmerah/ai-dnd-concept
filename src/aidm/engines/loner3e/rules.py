from pathlib import Path
from random import Random

from aidm.engines.loader import Engine
from aidm.engines.packs import load_packs, pack_paths
from aidm.engines.sheets import resolved_threads
from aidm.state.base import PLAYER_ID, Counter, EngineId, Entity, Frozen
from aidm.state.plan import Resolution
from aidm.state.world import GameState

from .actions import Question, resolve_question
from .advance import Loner3eAdvancement
from .create import Loner3eCreation
from .mechanics import Mechanics, Sheet, describe_entity
from .pack import Pack, twist_table

ENGINE_ID: EngineId = EngineId("loner3e")


class Loner3eEngine(Engine[Sheet]):
    id = ENGINE_ID
    badge = ("LONER 3E", "teal-7")
    engine_dir = Path(__file__).parent
    sheet_type = Sheet
    mechanics_type = Mechanics
    actions = {"question": Question}

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.advancement = Loner3eAdvancement(self.engine_dir)
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

    def resolve_roll(self, draft: GameState, roll: Frozen, rng: Random) -> Resolution:
        if not isinstance(roll, Question):
            raise TypeError(f"{type(roll).__name__} is no loner3e roll")
        return resolve_question(draft, roll, rng, self.twists(draft))

    def twists(self, state: GameState) -> tuple[tuple[str, str], ...]:
        """The player's own table set: an NPC sheet is seeded with the default and never selects."""
        return twist_table(self.packs, state.mechanics_as(Mechanics).sheets[PLAYER_ID].pack)


ENGINE = Loner3eEngine
