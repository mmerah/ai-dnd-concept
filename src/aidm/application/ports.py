"""What the application needs from the world outside it. Protocols, so `application/` imports no
adapter and a test can hand it a dictionary.

Two ports rather than one, because the two have different lifecycles: a save is read back and
refused when the schema or the packs under it moved, a trace is written and never read."""

from typing import Protocol

from ..domain.models import GameState, Turn


class SaveRepository(Protocol):
    """One `GameState` per slug, the whole of what survives a restart."""

    def load(self, slug: str) -> GameState | None: ...
    def save(self, slug: str, state: GameState) -> None: ...
    def discard(self, slug: str) -> None: ...


class TraceSink(Protocol):
    """Append-only. The application never reads this back: the panel keeps this session's turns in
    memory, so a trace is a record for outside the process."""

    def append(self, slug: str, turn: Turn) -> None: ...
    def discard(self, slug: str) -> None: ...
