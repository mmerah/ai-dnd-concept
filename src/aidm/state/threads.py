from aidm.state.facts import Fact
from aidm.state.model import AdvanceThread, Game
from aidm.state.tools import DirectorTool, director_tool


def advance_thread(draft: Game, effect: AdvanceThread) -> list[Fact]:
    """Threads are the Director's bookkeeping, so nothing here reaches the Narrator."""
    thread = draft.world.thread(effect.thread_id)
    if thread is None:
        known = ", ".join(sorted(draft.world.threads)) or "(none)"
        raise ValueError(f"unknown thread {effect.thread_id!r}. The threads are: {known}")
    thread.status = effect.status or thread.status
    if effect.note is not None:
        thread.note = effect.note
    moved = f"thread {thread.title}[{thread.id}] — status {thread.status}"
    if thread.note:
        moved += f" — note: {thread.note}"
    return [Fact(kind="thread_advanced", trace=moved)]


ADVANCE_THREAD: DirectorTool = director_tool(
    "advance_thread",
    "Update an active storyline's status or note.",
    AdvanceThread,
    lambda draft, one, _rng: advance_thread(draft, one),
    during_suspension=True,
)
