from core_test_support import text, tool_call
from golden_turn_support import LISTENING, NARRATION, take
from pydantic_ai.messages import ModelResponse

SCRIPT: tuple[ModelResponse, ...] = (
    take("vault-map"),
    tool_call(
        "roll_question",
        actor_id="player",
        question="Does he hear what waits past the vault door without being heard?",
        position="advantage",
        edge="Quiet Hands",
    ),
    LISTENING,
    text(NARRATION),
)
