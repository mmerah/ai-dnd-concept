from core_test_support import text, tool_call
from golden_turn_support import LISTENING, NARRATION, take
from pydantic_ai.messages import ModelResponse

SCRIPT: tuple[ModelResponse, ...] = (
    take("cipher-spike"),
    tool_call(
        "roll_attempt",
        actor_id="player",
        goal="Listen at the vault door without being heard",
        risk="whatever is behind the door hears him first",
        hit=False,
        skill="Stealth",
        helped="the relic-hunter's ear for old stone",
        luck_test="something behind the door is already listening back",
    ),
    LISTENING,
    text(NARRATION),
)
