from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field

from httpx import AsyncClient
from pydantic import JsonValue

from aidm.config import ProviderConfig


@dataclass(slots=True)
class Claims:
    """Keys being generated now, so two callers never both pay for one image or clip."""

    held: set[str] = field(default_factory=set)

    @contextmanager
    def hold(self, key: str) -> Generator[bool]:
        """Yields whether this caller won the claim; releases only what it won."""
        won = self._claim(key)
        try:
            yield won
        finally:
            if won:
                self._release(key)

    def _claim(self, key: str) -> bool:
        # Synchronous: an await between the read and the write would let two callers both pay.
        if key in self.held:
            return False
        self.held.add(key)
        return True

    def _release(self, key: str) -> None:
        self.held.discard(key)


async def post_bearer(
    provider: ProviderConfig, path: str, body: Mapping[str, JsonValue], timeout: float
) -> bytes:
    """Returns bytes: one reply is JSON, another audio."""
    async with AsyncClient(timeout=timeout) as client:
        reply = await client.post(
            f"{provider.base_url}{path}",
            headers={"Authorization": f"Bearer {provider.api_key.get_secret_value()}"},
            json=body,
        )
        reply.raise_for_status()
        return reply.content
