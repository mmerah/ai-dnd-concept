from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.engines.engine import Engine
from aidm.engines.packs import load_packs, pack_paths
from aidm.engines.sheets import actor_sheets, check_sheets
from aidm.state.base import PLAYER_ID, Counter, EngineId, Entity
from aidm.state.world import Game, WorldState

from .actions import director_toolset
from .advance import TwentyfourxxAdvancement
from .create import TwentyfourxxCreation
from .mechanics import Mechanics, Sheet, describe_entity
from .pack import Pack

ENGINE_ID: EngineId = EngineId("twentyfourxx")


class TwentyfourxxEngine(Engine):
    id = ENGINE_ID
    badge = ("24XX", "indigo-7")
    engine_dir = Path(__file__).parent
    mechanics_type = Mechanics

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.advancement = TwentyfourxxAdvancement(self.engine_dir)
        self.creation = TwentyfourxxCreation(self.packs)
        self.director_toolsets = (director_toolset(),)

    def check_overlay(self, rules: dict[str, JsonValue]) -> None:
        _ = Sheet.model_validate(rules)

    def opening_mechanics(self, world: WorldState, player_rules: dict[str, JsonValue]) -> Mechanics:
        return Mechanics(sheets=actor_sheets(world, player_rules, Sheet))

    def validate(self, state: Game) -> None:
        check_sheets(state.world, Mechanics.of(state).sheets, self.id)

    def seed(self, draft: Game, entity: Entity, rng: Random) -> None:
        del rng  # nothing on a fresh 24xx sheet is rolled
        mechanics = Mechanics.of(draft)
        if entity.kind != "actor" or entity.id in mechanics.sheets:
            return
        # A newcomer starts level with the party: jobs done before they joined are not owed.
        mechanics.sheets[entity.id] = Sheet(jobs=Counter(current=mechanics.completed.current))

    def describe(self, state: Game, entity: Entity) -> str:
        return describe_entity(Mechanics.of(state), entity)

    def sheet_view(self, state: Game) -> tuple[tuple[str, str], ...]:
        sheet = Mechanics.of(state).sheets[PLAYER_ID]
        return (
            ("Specialty", sheet.specialty),
            ("Origin", sheet.origin),
            (
                "Skills",
                ", ".join(f"{name} d{face}" for name, face in sorted(sheet.skills.items())),
            ),
            ("Credits", str(sheet.credits.current)),
        )
