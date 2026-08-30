from core_test_support import changed
from pydantic_ai.messages import ModelResponse

NARRATION = "The flagstone lifts. Beyond the door, something shifts its weight and waits."

LISTENING = changed(
    "add_trait",
    entity_id="player",
    name="Listening",
    text="(condition) Listening for the next shift of weight behind the door.",
)


def take(item_id: str) -> ModelResponse:
    return changed("move", entity_id=item_id, to_id="player")
