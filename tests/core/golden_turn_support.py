from core_test_support import changed

NARRATION = "The flagstone lifts. Beyond the door, something shifts its weight and waits."

LISTENING = changed(
    "change_tags",
    entity_id="player",
    kind="condition",
    gained=["Listening"],
)
