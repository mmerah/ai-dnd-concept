from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cache

from httpx import AsyncClient
from pydantic import JsonValue

from aidm.config import ProviderConfig


@dataclass(frozen=True, slots=True)
class Claims:
    """Keys being generated now, so two callers never both pay for one image or clip."""

    held: set[str] = field(default_factory=set)

    @contextmanager
    def hold(self, key: str) -> Generator[bool]:
        # Synchronous: an await between the read and the write would let two callers both pay.
        won = key not in self.held
        self.held.add(key)
        try:
            yield won
        finally:
            if won:
                self.held.discard(key)


@cache
def posting() -> AsyncClient:
    """One pool for the process: a client per call pays a new handshake."""
    return AsyncClient()


async def close_posting() -> None:
    if posting.cache_info().currsize:
        await posting().aclose()
        posting.cache_clear()


async def post_bearer(
    provider: ProviderConfig, path: str, body: Mapping[str, JsonValue], timeout: float
) -> bytes:
    """Returns bytes: one reply is JSON, another audio."""
    reply = await posting().post(
        f"{provider.base_url}{path}",
        headers={"Authorization": f"Bearer {provider.api_key.get_secret_value()}"},
        json=body,
        timeout=timeout,
    )
    reply.raise_for_status()
    return reply.content
