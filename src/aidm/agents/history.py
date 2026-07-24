"""Play history as native LLM messages."""

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
    """Each exchange becomes a user turn (the player prompt) and an assistant turn (the narration),
    so a role reads the conversation in the shape the model was trained on."""
    messages: list[ModelMessage] = []
    for exchange in history:
        messages.append(ModelRequest(parts=[UserPromptPart(content=exchange.prompt)]))
        messages.append(ModelResponse(parts=[TextPart(content=exchange.narration)]))
    return messages
