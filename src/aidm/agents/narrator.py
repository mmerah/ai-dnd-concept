from pydantic_ai.messages import ModelMessage

from .llm import build_agent
from .prompts.narrator import INSTRUCTIONS

agent = build_agent("narrator", output_type=str, instructions=INSTRUCTIONS)


async def narrate(prompt: str, message_history: list[ModelMessage] | None = None) -> str:
    return (await agent().run(prompt, message_history=message_history)).output
