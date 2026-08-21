from aidm.state.model import Frozen, Game, Line, ThreadStatus


class ThreadSummary(Frozen):
    title: str
    status: ThreadStatus
    stage: str | None = None
    clock: str = ""


def thread_summaries(state: Game) -> tuple[ThreadSummary, ...]:
    return tuple(
        ThreadSummary(
            title=thread.title,
            status=thread.status,
            stage=None if thread.stage is None else thread.stage.replace("-", " "),
            clock=""
            if thread.clock is None
            else f"{thread.clock.current} / {thread.clock.maximum}",
        )
        for thread in sorted(state.world.threads, key=lambda thread: thread.title)
    )


def journal_markdown(state: Game) -> str:
    """A projection only: the journal is written for a reader and never read back."""
    threads = thread_summaries(state)
    lines = [f"# {state.scenario.title}", "", state.scenario.premise, ""]
    for number, exchange in enumerate(state.history, start=1):
        told = "\n".join(attributed_line(state, line) for line in exchange.lines)
        lines.extend((f"## Turn {number}", "", f"> {exchange.prompt}", "", told, ""))
    if threads:
        lines.extend(("## Threads", ""))
        lines.extend(f"- {_thread_line(thread)}" for thread in threads)
        lines.append("")
    return "\n".join(lines)


def attributed_line(state: Game, line: Line) -> str:
    """A speaker is named, because a bare quote reads as narration once the bubbles are gone."""
    speaker = None if line.speaker_id is None else state.world.require(line.speaker_id)
    return line.text if speaker is None else f"**{speaker.name}:** {line.text}"


def _thread_line(thread: ThreadSummary) -> str:
    stage = f" at {thread.stage}" if thread.stage is not None else ""
    clock = f" [{thread.clock}]" if thread.clock else ""
    return f"**{thread.title}** — {thread.status}{stage}{clock}"
