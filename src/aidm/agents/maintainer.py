"""MAINTAINER — grows the scenario to cover whatever the Narrator invented."""

from pydantic_ai import NativeOutput
from pydantic_ai.messages import ModelMessage

from ..domain.models import Growth
from .llm import build_agent
from .prompts.maintainer import INSTRUCTIONS

agent = build_agent("maintainer", output_type=NativeOutput(Growth), instructions=INSTRUCTIONS)


async def maintain(prompt: str, message_history: list[ModelMessage] | None = None) -> Growth:
    return (await agent().run(prompt, message_history=message_history)).output
