from pathlib import Path
from random import Random

from aidm.engines.engine import Engine
from aidm.engines.packs import load_packs, pack_paths
from aidm.state.base import PLAYER_ID, Counter, EngineId, Entity
from aidm.state.world import Game

from .advance import Loner3eAdvancement
from .create import Loner3eCreation
from .mechanics import Mechanics, Sheet, describe_entity
from .pack import Pack, twist_table
from .tools import director_toolset

ENGINE_ID: EngineId = EngineId("loner3e")


class Loner3eEngine(Engine[Sheet]):
    id = ENGINE_ID
    badge = ("LONER 3E", "teal-7")
    chapter_ending = "the adventure has ended"
    engine_dir = Path(__file__).parent
    sheet_type = Sheet
    mechanics_type = Mechanics

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.advancement = Loner3eAdvancement(self.engine_dir)
        self.creation = Loner3eCreation(self.packs)
        self.director_toolsets = (director_toolset(self.twists),)

    def check_mechanics(self, state: Game) -> None:
        if (chosen := Mechanics.of(state).sheets[PLAYER_ID].pack) not in self.packs:
            raise ValueError(f"this game plays the {chosen!r} table set, which is not installed")

    def new_sheet(self, draft: Game, rng: Random) -> Sheet:
        del rng  # nothing on a loner3e sheet is rolled
        # A newcomer starts level with the party: milestones earned before they joined are not owed.
        return Sheet(milestones=Counter(current=Mechanics.of(draft).completed.current))

    def describe(self, state: Game, entity: Entity) -> str:
        return describe_entity(Mechanics.of(state), entity)

    def sheet_view(self, state: Game) -> tuple[tuple[str, str], ...]:
        sheet = Mechanics.of(state).sheets[PLAYER_ID]
        return (
            ("Concept", sheet.concept),
            ("Skills", ", ".join(sheet.skills)),
            ("Frailties", ", ".join(sheet.frailties)),
            ("Gear", ", ".join(sheet.gear)),
            ("Luck", f"{sheet.luck.current} / {sheet.luck.maximum}"),
        )

    def twists(self, state: Game) -> tuple[tuple[str, str], ...]:
        """The player's own table set: an NPC sheet is seeded with the default and never selects."""
        return twist_table(self.packs, Mechanics.of(state).sheets[PLAYER_ID].pack)
