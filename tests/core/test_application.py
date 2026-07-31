from dataclasses import dataclass, field
from random import Random

import pytest
from core_test_support import character, scenario, settings
from story_test_support import setback_direction

from aidm.agents.stages import director_stage, shared_stages
from aidm.application.game import GameApplication
from aidm.domain.base import PLAYER_ID
from aidm.domain.state import GameState
from aidm.domain.turn import Advance, TraceEntry
from aidm.engines import resolve
from aidm.pipeline import TurnOptions
from aidm_story.advancement import RaiseApproach
from aidm_story.factory import build_story_engine
from aidm_story.state import story_state


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
    entries: list[TraceEntry] = field(default_factory=list)

    def append(self, slug: str, entry: TraceEntry) -> None:
        del slug
        self.entries.append(entry)

    def load(self, slug: str) -> tuple[TraceEntry, ...]:
        del slug
        return tuple(self.entries)

    def discard(self, slug: str) -> None:
        del slug
        self.entries.clear()


def application(saves: MemorySaves, traces: MemoryTraces) -> GameApplication:
    engine = build_story_engine()
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

    resumed = app.state.model_copy(deep=True)
    resumed.turn = 7
    saves.save("poc", resumed)
    assert application(saves, traces).state.turn == 7

    app = application(saves, traces)
    app.restart()
    assert app.state.turn == 0
    assert app.entries == []
    assert saves.states == {}
    assert traces.entries == []


def test_resume_rejects_a_save_from_another_scenario() -> None:
    saves = MemorySaves()
    app = application(saves, MemoryTraces())
    elsewhere = app.state.model_copy(deep=True)
    elsewhere.scenario = elsewhere.scenario.model_copy(update={"title": "Another Vault"})
    saves.save("poc", elsewhere)

    with pytest.raises(ValueError, match="save scenario is 'Another Vault'"):
        application(saves, MemoryTraces())


def test_advancement_commits_through_the_same_path_and_reaches_the_trace() -> None:
    """A level-up is a transaction like a turn: it saves, and it shows up in the trace panel."""
    saves, traces = MemorySaves(), MemoryTraces()
    app = application(saves, traces)
    for _ in range(3):
        app.state = resolve(app.engine, setback_direction(), app.state, Random(2)).state
    assert app.advancement_available()
    before = story_state(app.state).actor(PLAYER_ID).approaches.bold

    facts = app.advance(RaiseApproach(approach="bold"))

    assert [fact.fact for fact in facts] == ["approach-raised", "growth-reset"]
    assert story_state(app.state).actor(PLAYER_ID).approaches.bold == before + 1
    assert not app.advancement_available()
    assert saves.states["poc"] == app.state
    (entry,) = traces.entries
    assert isinstance(entry, Advance) and entry.facts == facts and entry.state == app.state
    assert app.entries == [entry]
