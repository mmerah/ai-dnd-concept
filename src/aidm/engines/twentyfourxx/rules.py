from pathlib import Path
from random import Random

from aidm.engines.engine import Engine
from aidm.engines.packs import load_packs, pack_paths
from aidm.state.base import PLAYER_ID, Counter, EngineId, Entity
from aidm.state.world import GameState

from .advance import TwentyfourxxAdvancement
from .create import TwentyfourxxCreation
from .mechanics import Mechanics, Sheet, describe_entity
from .pack import Pack
from .tools import director_toolset

ENGINE_ID: EngineId = EngineId("twentyfourxx")


class TwentyfourxxEngine(Engine[Sheet]):
    id = ENGINE_ID
    badge = ("24XX", "indigo-7")
    engine_dir = Path(__file__).parent
    sheet_type = Sheet
    mechanics_type = Mechanics

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.advancement = TwentyfourxxAdvancement(self.engine_dir)
        self.creation = TwentyfourxxCreation(self.packs)
        self.director_toolsets = (director_toolset(),)

    def new_sheet(self, draft: GameState, rng: Random) -> Sheet:
        del rng  # nothing on a fresh 24xx sheet is rolled
        # A newcomer starts level with the party: jobs done before they joined are not owed.
        return Sheet(jobs=Counter(current=draft.mechanics_as(Mechanics).completed.current))

    def describe(self, state: GameState, entity: Entity) -> str:
        return describe_entity(state.mechanics_as(Mechanics), entity)

    def sheet_view(self, state: GameState) -> tuple[tuple[str, str], ...]:
        sheet = state.mechanics_as(Mechanics).sheets[PLAYER_ID]
        return (
            ("Specialty", sheet.specialty),
            ("Origin", sheet.origin),
            (
                "Skills",
                ", ".join(f"{name} d{face}" for name, face in sorted(sheet.skills.items())),
            ),
            ("Credits", str(sheet.credits.current)),
        )
