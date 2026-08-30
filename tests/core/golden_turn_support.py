from core_test_support import changed

NARRATION = "The flagstone lifts. Beyond the door, something shifts its weight and waits."

LISTENING = changed(
    "add_trait",
    entity_id="player",
    name="Listening",
    text="(condition) Listening for the next shift of weight behind the door.",
)
