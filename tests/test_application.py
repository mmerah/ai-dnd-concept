"""The application layer: one open game, three actions, and nothing that needs a browser or a disk.

Both repositories here are dictionaries — the thing a `store`-shaped dependency made impossible to
write, and the reason this file can assert *when* a game becomes durable rather than only what it
holds."""

from contextlib import ExitStack
from dataclasses import dataclass, field
from random import Random

import pytest
from support import (
    OPTIONS,
    new_game,
    ruleset,
    scenario,
    sheet,
    structured,
    stubs,
    text,
)

from aidm.application.game import GameApplication
from aidm.application.ports import SaveRepository, TraceSink
from aidm.domain.models import SAVE_VERSION, Direction, GameState, Growth, Turn, updated

SLUG = "poc"


@dataclass
class MemorySaves:
    saved: dict[str, GameState] = field(default_factory=dict)

    def load(self, slug: str) -> GameState | None:
        return self.saved.get(slug)

    def save(self, slug: str, state: GameState) -> None:
        self.saved[slug] = state

    def discard(self, slug: str) -> None:
        self.saved.pop(slug, None)


@dataclass
class MemoryTraces:
    written: list[Turn] = field(default_factory=list)

    def append(self, slug: str, turn: Turn) -> None:
        self.written.append(turn)

    def discard(self, slug: str) -> None:
        self.written.clear()


def application(saves: SaveRepository, traces: TraceSink) -> GameApplication:
    """What `bootstrap.create_application` builds, with the two files replaced by dictionaries."""
    return GameApplication(
        slug=SLUG,
        scenario=scenario(),
        sheet=sheet(),
        ruleset=ruleset(),
        saves=saves,
        traces=traces,
        options=OPTIONS,
        rng=Random(1),
    )


def test_a_game_is_begun_when_nothing_is_saved_and_resumed_when_something_is() -> None:
    """Opening is not committing: a game nobody has played is not written back, so a crash before
    the first turn leaves no half-game behind."""
    saves = MemorySaves()
    begun = application(saves, MemoryTraces())
    assert begun.state.player.progression is not None and saves.saved == {}

    saves.save(SLUG, updated(begun.state, turn=7))
    assert application(saves, MemoryTraces()).state.turn == 7


def test_a_save_this_build_cannot_play_stops_the_application_opening() -> None:
    """The refusal belongs here rather than in the repository: reading the file worked, and what
    moved is the content under the save."""
    saves = MemorySaves()
    saves.save(SLUG, updated(new_game(), version=SAVE_VERSION - 1))
    with pytest.raises(ValueError, match=f"needs v{SAVE_VERSION}"):
        application(saves, MemoryTraces())


async def test_a_committed_turn_is_saved_traced_and_kept_for_the_panel() -> None:
    """The four things a turn does, in one place: advance the state, keep the turn for the trace
    panel, write the save, append the trace."""
    saves, traces = MemorySaves(), MemoryTraces()
    app = application(saves, traces)
    with ExitStack() as stack:
        stubs(
            stack,
            director=structured(intent="Kael listens at the door.", tone="hushed", mechanics=[]),
            narrator=text("Nothing but the settling of old stone."),
            maintainer=structured(requests=[]),
        )
        turn = await app.submit("I listen at the door.")

    assert app.state is turn.state and app.turns == [turn]
    assert saves.saved[SLUG] == turn.state
    assert [t.prompt for t in traces.written] == ["I listen at the door."]


def test_a_level_is_durable_without_a_turn_and_a_restart_discards_both() -> None:
    """A level-up runs no role, so there is nothing to trace — but it must still survive a reload.
    A restart drops the save and the trace together: keeping either would open the next game with
    someone else's history."""
    saves, traces = MemorySaves(), MemoryTraces()
    app = application(saves, traces)
    traces.append(SLUG, _traced(app.state))
    app.advance({})  # a fighter's second level asks nothing

    advanced = app.state.player.progression
    assert advanced is not None and advanced.level == 2
    assert saves.saved[SLUG] == app.state and traces.written  # durable, and no trace of its own

    app.restart()
    restarted = app.state.player.progression
    assert restarted is not None and restarted.level == 1
    assert app.turns == [] and traces.written == [] and saves.saved[SLUG] == app.state


def _traced(state: GameState) -> Turn:
    """A turn already written, so `restart` has something to discard."""
    return Turn(
        prompt="I listen.",
        direction=Direction(intent="i", tone="t"),
        narration="n",
        growth=Growth(),
        state=state,
    )
