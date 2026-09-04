from collections.abc import Mapping

from httpx import AsyncClient
from pydantic import JsonValue

from aidm.config import ProviderConfig


def claim(generating: set[str], key: str) -> bool:
    # Synchronous: an await between the read and the write would let two callers both pay.
    if key in generating:
        return False
    generating.add(key)
    return True


async def post_bearer(
    provider: ProviderConfig, path: str, body: Mapping[str, JsonValue], timeout: float
) -> bytes:
    """Free: a provider config is settings, not one of our objects.

    One bearer POST; the caller parses the bytes, since one reply is JSON, another audio."""
    async with AsyncClient(timeout=timeout) as client:
        reply = await client.post(
            f"{provider.base_url}{path}",
            headers={"Authorization": f"Bearer {provider.api_key.get_secret_value()}"},
            json=body,
        )
        reply.raise_for_status()
        return reply.content
