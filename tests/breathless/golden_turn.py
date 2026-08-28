from core_test_support import text, tool_call
from golden_turn_support import LISTENING, NARRATION, take
from pydantic_ai.messages import ModelResponse

SCRIPT: tuple[ModelResponse, ...] = (
    take("ward-card"),
    tool_call(
        "roll_check",
        actor_id="player",
        goal="Listen at the vault door without being heard",
        risk="whatever is behind the door hears him first",
        dangerous=False,
        skill="Sneak",
    ),
    LISTENING,
    text(NARRATION),
)
