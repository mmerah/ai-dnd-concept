from collections.abc import Sequence

from aidm.state.base import Frozen, Slug, ThreadStatus
from aidm.state.history import Exchange, Line
from aidm.state.trace import TraceEntry, Turn
from aidm.state.world import GameState
from aidm.turn.scene import SceneSnapshot, VisibleScene


def player_scene(state: GameState) -> VisibleScene:
    """What any player-facing surface may see, stripped of unrevealed canon by construction."""
    return VisibleScene.of(SceneSnapshot.of(state))


class ThreadSummary(Frozen):
    title: str
    status: ThreadStatus
    stage: Slug | None = None
    clock: str = ""


def thread_summaries(state: GameState) -> tuple[ThreadSummary, ...]:
    return tuple(
        ThreadSummary(
            title=thread.title,
            status=thread.status,
            stage=thread.stage,
            clock=""
            if thread.clock is None
            else f"{thread.clock.current} / {thread.clock.maximum}",
        )
        for thread in sorted(state.world.threads, key=lambda thread: thread.title)
    )


class PlayedTurn(Frozen):
    """One exchange and the player-safe rendering of what its facts settled."""

    exchange: Exchange
    outcomes: tuple[str, ...] = ()


def played_turns(
    history: Sequence[Exchange], entries: Sequence[TraceEntry]
) -> tuple[PlayedTurn, ...]:
    """History and trace both grow one entry per turn, so pairing them from the end cannot slip."""
    turns = [entry for entry in entries if isinstance(entry, Turn)]
    paired = dict(zip(reversed(range(len(history))), reversed(turns), strict=False))
    return tuple(
        PlayedTurn(exchange=exchange, outcomes=_outcomes(paired.get(index)))
        for index, exchange in enumerate(history)
    )


def _outcomes(turn: Turn | None) -> tuple[str, ...]:
    if turn is None:
        return ()
    return tuple(told for fact in turn.facts if (told := fact.narrator) is not None)


class JournalView(Frozen):
    """What the player may read back: their own exchanges, the threads, and met-owner memories."""

    chronicle: tuple[Exchange, ...] = ()
    threads: tuple[ThreadSummary, ...] = ()
    memories: tuple[str, ...] = ()

    @classmethod
    def of(cls, state: GameState) -> "JournalView":
        world = state.world
        return cls(
            chronicle=state.history,
            threads=thread_summaries(state),
            # An authored memory can belong to someone the player has not met.
            memories=tuple(
                memory.text
                for memory in world.memories
                if memory.owner is None or world.require(memory.owner).known
            ),
        )


def journal_markdown(state: GameState) -> str:
    """A projection only: the journal is written for a reader and never read back."""
    view = JournalView.of(state)
    lines = [f"# {state.scenario.title}", "", state.scenario.premise, ""]
    for number, exchange in enumerate(view.chronicle, start=1):
        told = "\n".join(attributed_line(state, line) for line in exchange.lines)
        lines.extend((f"## Turn {number}", "", f"> {exchange.prompt}", "", told, ""))
    if view.threads:
        lines.extend(("## Threads", ""))
        lines.extend(f"- {_thread_line(thread)}" for thread in view.threads)
        lines.append("")
    if view.memories:
        lines.extend(("## What is remembered", ""))
        lines.extend(f"- {memory}" for memory in view.memories)
        lines.append("")
    return "\n".join(lines)


def attributed_line(state: GameState, line: Line) -> str:
    """A speaker is named, because a bare quote reads as narration once the bubbles are gone."""
    speaker = None if line.speaker_id is None else state.world.require(line.speaker_id)
    return line.text if speaker is None else f"**{speaker.name}:** {line.text}"


def _thread_line(thread: ThreadSummary) -> str:
    stage = f" at {thread.stage}" if thread.stage is not None else ""
    clock = f" [{thread.clock}]" if thread.clock else ""
    return f"**{thread.title}** — {thread.status}{stage}{clock}"
