"""MAINTAINER — grows the scenario to cover whatever the Narrator invented."""

from pydantic_ai import NativeOutput
from pydantic_ai.messages import ModelMessage

from ..domain.models import Growth
from .llm import build_agent

INSTRUCTIONS = """You are the MAINTAINER of a tabletop RPG world. You read what was just told to \
the player and keep the world catalogue complete.

Request one entry for every NAMED person, place or item that appears in the narration and is \
missing from the catalogue. Give the exact name used and a one-sentence brief consistent with \
the narration.

- Match loosely: a name already in the catalogue in any spelling is not new, and neither is \
something the catalogue already describes under a different name. You are shown each entry's \
brief precisely so you can recognise it under a new description.
- WHAT HAPPENED lists what the engine already recorded this turn. Anything covered there is \
already accounted for and is not new.
- Ignore unnamed background detail, scenery, crowds and objects nobody could interact with.
- Returning nothing is normal and is the right answer most turns."""


agent = build_agent("maintainer", output_type=NativeOutput(Growth), instructions=INSTRUCTIONS)


async def maintain(prompt: str, message_history: list[ModelMessage] | None = None) -> Growth:
    return (await agent().run(prompt, message_history=message_history)).output
