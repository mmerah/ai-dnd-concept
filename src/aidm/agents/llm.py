"""The only place that knows about the model provider."""

from functools import cache

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from ..config import settings

RETRIES = 3  # small models mis-name things; let them be corrected instead of failing the turn


@cache
def model() -> OpenAIChatModel:
    """Deferred so importing a role never needs an API key."""
    conf = settings()
    provider = OpenAIProvider(base_url=conf.ai_base_url, api_key=conf.ai_api_key)
    return OpenAIChatModel(conf.ai_model, provider=provider)
