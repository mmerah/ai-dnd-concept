from dataclasses import dataclass, field
from random import Random

import pytest
from aidm.agents.stages import director_stage, shared_stages
from aidm.application.game import GameApplication
from aidm.domain.state import GameState
from aidm.domain.turn import Turn
from aidm.pipeline import TurnOptions
from aidm.utils.models import updated
from core_test_support import TestEngine as _TestEngine
from core_test_support import character, scenario, settings


@dataclass
class MemorySaves:
    states: dict[str, GameState] = field(default_factory=dict)

    def load(self, slug: str) -> GameState | None:
        return self.states.get(slug)

    def save(self, slug: str, state: GameState) -> None:
        self.states[slug] = state

    def discard(self, slug: str) -> None:
        self.states.pop(slug, None)


@dataclass
class MemoryTraces:
    turns: list[Turn] = field(default_factory=list)

    def append(self, slug: str, turn: Turn) -> None:
        del slug
        self.turns.append(turn)

    def load(self, slug: str) -> tuple[Turn, ...]:
        del slug
        return tuple(self.turns)

    def discard(self, slug: str) -> None:
        del slug
        self.turns.clear()


def application(saves: MemorySaves, traces: MemoryTraces) -> GameApplication:
    engine = _TestEngine()
    config = settings()
    return GameApplication(
        slug="poc",
        scenario=scenario(),
        character=character(),
        engine=engine,
        director=director_stage(engine, config),
        stages=shared_stages(config),
        saves=saves,
        traces=traces,
        options=TurnOptions(history_window=6, max_growth=3),
        rng=Random(1),
    )


def test_opening_does_not_save_and_restart_discards_durable_state() -> None:
    saves = MemorySaves()
    traces = MemoryTraces()
    app = application(saves, traces)
    assert saves.states == {}

    resumed = updated(app.state, turn=7)
    saves.save("poc", resumed)
    assert application(saves, traces).state.turn == 7

    app = application(saves, traces)
    app.restart()
    assert app.state.turn == 0
    assert app.turns == []
    assert saves.states == {}
    assert traces.turns == []


def test_resume_rejects_an_exact_engine_stamp_mismatch() -> None:
    saves = MemorySaves()
    app = application(saves, MemoryTraces())
    incompatible = updated(
        app.state,
        engine=updated(app.state.engine, rules_version=2),
    )
    saves.save("poc", incompatible)

    with pytest.raises(ValueError, match="rules_version.*2.*1"):
        application(saves, MemoryTraces())
