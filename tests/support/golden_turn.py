import json

from support.table import tool_call

NARRATION = "The flagstone lifts. Beyond the door, something shifts its weight and waits."
INTERJECTION = json.dumps(
    {
        "lines": [{"speaker_id": "vessa-rune", "text": "Six days locked to a dark relay."}],
        "proposal": "I ask Vessa why she hasn't left the docking ring.",
    }
)

LISTENING = tool_call(
    "change_tags",
    entity_id="player",
    kind="condition",
    gained=["Listening"],
)
