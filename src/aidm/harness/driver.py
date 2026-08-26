from collections.abc import AsyncIterator
from typing import Protocol


class Driver(Protocol):
    def play(self, text: str) -> AsyncIterator[str]:
        """Yields dev-log lines only; the turn itself lands through the MCP tools."""
        ...

    async def interrupt(self) -> None: ...

    async def close(self) -> None: ...


def opening(slug: str | None, text: str) -> str:
    if slug is None:
        return (
            "Write a new scenario: run the `authoring-aidm` skill against this server's "
            f"begin_scenario and finish_scenario tools. {text}"
        )
    return (
        f"Play the game {slug!r} with the `playing-aidm` skill, opening it if it is not open yet. "
        "The player is watching this window, not a terminal, so end_turn's prose is what they "
        "read. The tools carry the whole game: do not read, search or run anything in the "
        f"repository. Their action: {text}"
    )


def clip(text: str, limit: int = 160) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else f"{flat[:limit]}…"
