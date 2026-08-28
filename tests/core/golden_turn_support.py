from core_test_support import tool_call
from pydantic_ai.messages import ModelResponse

NARRATION = "The flagstone lifts. Beyond the door, something shifts its weight and waits."

LISTENING = tool_call(
    "add_trait",
    entity_id="player",
    name="Listening",
    text="(condition) Listening for the next shift of weight behind the door.",
)


def take(item_id: str) -> ModelResponse:
    return tool_call("move", entity_id=item_id, to_id="player")
