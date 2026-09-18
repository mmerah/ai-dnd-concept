from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field

from httpx import AsyncClient
from pydantic import JsonValue

from aidm.config import ProviderConfig

_client: AsyncClient | None = None


@dataclass(slots=True)
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


def client() -> AsyncClient:
    """One pool for the process: a client per call pays a new handshake."""
    global _client
    if _client is None:
        _client = AsyncClient()
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def post_bearer(
    provider: ProviderConfig, path: str, body: Mapping[str, JsonValue], timeout: float
) -> bytes:
    """Returns bytes: one reply is JSON, another audio."""
    reply = await client().post(
        f"{provider.base_url}{path}",
        headers={"Authorization": f"Bearer {provider.api_key.get_secret_value()}"},
        json=body,
        timeout=timeout,
    )
    reply.raise_for_status()
    return reply.content
