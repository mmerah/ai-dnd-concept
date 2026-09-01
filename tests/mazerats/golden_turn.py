from core_test_support import Call, tool_call

SCRIPT: tuple[Call, ...] = (
    tool_call("move", to_id="echo-hall"),
    tool_call(
        "danger_roll",
        actor_id="player",
        ability="dexterity",
        danger="the glass warden notices the intruder",
    ),
)
