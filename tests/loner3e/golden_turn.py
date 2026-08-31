from core_test_support import Call, changed, tool_call
from golden_turn_support import LISTENING

SCRIPT: tuple[Call, ...] = (
    changed("reveal", entity_id="vault-map"),
    tool_call(
        "roll_question",
        actor_id="player",
        question="Does he hear what waits past the vault door without being heard?",
        position="advantage",
        edge="Quiet Hands",
    ),
    LISTENING,
)
