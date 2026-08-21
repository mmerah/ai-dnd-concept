from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.engines.core import Engine, actor_sheets, check_sheets, load_packs, pack_paths
from aidm.state.model import PLAYER_ID, Counter, EngineId, Entity, Game, WorldState

from .actions import director_toolset
from .advance import Loner3eAdvancement
from .create import Loner3eCreation
from .mechanics import Mechanics, Sheet, describe_entity
from .pack import Pack, twist_table

ENGINE_ID: EngineId = EngineId("loner3e")


class Loner3eEngine(Engine):
    id = ENGINE_ID
    badge = ("LONER 3E", "teal-7")
    engine_dir = Path(__file__).parent
    mechanics_type = Mechanics

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.advancement = Loner3eAdvancement(self.engine_dir)
        self.creation = Loner3eCreation(self.packs)
        self.director_toolsets = (director_toolset(self.twists),)

    def check_overlay(self, rules: dict[str, JsonValue]) -> None:
        _ = Sheet.model_validate(rules)

    def opening_mechanics(self, world: WorldState, player_rules: dict[str, JsonValue]) -> Mechanics:
        return Mechanics(sheets=actor_sheets(world, player_rules, Sheet))

    def validate(self, state: Game) -> None:
        mechanics = Mechanics.of(state)
        check_sheets(state.world, mechanics.sheets, self.id)
        if (chosen := mechanics.sheets[PLAYER_ID].pack) not in self.packs:
            raise ValueError(f"this game plays the {chosen!r} table set, which is not installed")

    def seed(self, draft: Game, entity: Entity, rng: Random) -> None:
        del rng  # nothing on a loner3e sheet is rolled
        mechanics = Mechanics.of(draft)
        if entity.kind != "actor" or entity.id in mechanics.sheets:
            return
        # A newcomer starts level with the party: milestones earned before they joined are not owed.
        mechanics.sheets[entity.id] = Sheet(milestones=Counter(current=mechanics.completed.current))

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
