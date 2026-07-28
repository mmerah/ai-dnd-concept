from collections.abc import Sequence

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from ..domain.models import Exchange


def exchanges_to_messages(history: Sequence[Exchange]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for exchange in history:
        messages.append(ModelRequest(parts=[UserPromptPart(content=exchange.prompt)]))
        messages.append(ModelResponse(parts=[TextPart(content=exchange.narration)]))
    return messages
