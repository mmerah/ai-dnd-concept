from pathlib import Path
from random import Random

from aidm.engines.engine import Engine
from aidm.engines.packs import load_packs, pack_paths
from aidm.state.base import PLAYER_ID, Counter, EngineId, Entity, Frozen
from aidm.state.beat import Resolution
from aidm.state.facts import Fact
from aidm.state.world import GameState

from .actions import (
    Attempt,
    ChangeCredits,
    CompleteJob,
    LuckTest,
    TwentyfourxxBeat,
    apply_change_credits,
    apply_complete_job,
    resolve_attempt,
    resolve_luck_test,
)
from .advance import TwentyfourxxAdvancement
from .create import TwentyfourxxCreation
from .mechanics import Mechanics, Sheet, describe_entity
from .pack import Pack

ENGINE_ID: EngineId = EngineId("twentyfourxx")


class TwentyfourxxEngine(Engine[Sheet]):
    id = ENGINE_ID
    badge = ("24XX", "indigo-7")
    engine_dir = Path(__file__).parent
    sheet_type = Sheet
    mechanics_type = Mechanics
    beat_type = TwentyfourxxBeat

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.advancement = TwentyfourxxAdvancement(self.engine_dir)
        self.creation = TwentyfourxxCreation(self.packs)

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

    def resolve_roll(self, draft: GameState, roll: Frozen, rng: Random) -> Resolution:
        match roll:
            case Attempt():
                return resolve_attempt(draft, roll, rng)
            case LuckTest():
                return resolve_luck_test(draft, roll, rng)
            case _:
                raise TypeError(f"{type(roll).__name__} is no 24xx roll")

    def unpack_beat(self, beat: Frozen) -> tuple[Frozen | None, tuple[Frozen, ...]]:
        if not isinstance(beat, TwentyfourxxBeat):
            raise TypeError(f"{type(beat).__name__} is no 24xx beat")
        return beat.roll, beat.effects

    def apply(self, draft: GameState, effect: Frozen) -> list[Fact]:
        match effect:
            case ChangeCredits():
                return apply_change_credits(draft, effect)
            case CompleteJob():
                return apply_complete_job(draft)
            case _:
                return super().apply(draft, effect)
