from collections.abc import Sequence
from dataclasses import dataclass

from pydantic_ai import Agent, ModelRetry, NativeOutput, RunContext
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.toolsets import AbstractToolset

from aidm.config import Settings
from aidm.engines.advancement import Advancement, Offer, ProposalBase
from aidm.engines.engine import Engine, PlanContext
from aidm.llm import build_agent
from aidm.state.model import Exchange, Game, Narration

from . import prompts
from .scene import VisibleScene
from .tools import core_toolset, possible


@dataclass(frozen=True, slots=True)
class AdvancementContext:
    advancement: Advancement
    state: Game
    offer: Offer


@dataclass(frozen=True, slots=True)
class TurnAgents:
    director: Agent[PlanContext, str]
    narrator: Agent[VisibleScene, Narration]


def director_agent(
    engine: Engine,
    settings: Settings,
) -> Agent[PlanContext, str]:
    """Everything that happens this turn happens through a tool; the closing text only traces."""
    toolsets: list[AbstractToolset[PlanContext]] = [
        core_toolset().filtered(lambda ctx, tool: possible(tool.name, ctx.deps.state)),
        *engine.director_toolsets,
    ]
    return build_agent(
        "director",
        settings,
        instructions=prompts.director_instructions(engine.director_instructions),
        output_type=str,
        deps_type=PlanContext,
        toolsets=toolsets,
    )


def narrator_agent(settings: Settings) -> Agent[VisibleScene, Narration]:
    def attributed(ctx: RunContext[VisibleScene], narration: Narration) -> Narration:
        """The leak rule holds through the validator, not through trust."""
        present = {ctx.deps.player.id, *(entity.id for entity in ctx.deps.here)}
        strangers = sorted(
            {
                line.speaker_id
                for line in narration.lines
                if line.speaker_id is not None and line.speaker_id not in present
            }
        )
        if strangers:
            raise ModelRetry(
                f"nobody here has id {', '.join(strangers)}. Only the player or someone here with "
                "them speaks; leave `speaker_id` null for narration."
            )
        return narration

    return build_agent(
        "narrator",
        settings,
        instructions=prompts.NARRATOR,
        output_type=NativeOutput(Narration),
        deps_type=VisibleScene,
        validator=attributed,
    )


def advisor_agent(
    advancement: Advancement, settings: Settings
) -> Agent[AdvancementContext, ProposalBase]:
    def legal(ctx: RunContext[AdvancementContext], proposal: ProposalBase) -> ProposalBase:
        deps = ctx.deps
        refused = deps.advancement.violation(deps.state, deps.offer, proposal)
        if refused is not None:
            raise ModelRetry(refused)
        return proposal

    return build_agent(
        "advisor",
        settings,
        instructions=prompts.advisor_instructions(advancement.instructions),
        output_type=NativeOutput(advancement.proposal_type),
        deps_type=AdvancementContext,
        validator=legal,
    )


def build_turn_agents(engine: Engine, settings: Settings) -> TurnAgents:
    return TurnAgents(director=director_agent(engine, settings), narrator=narrator_agent(settings))


def exchanges_to_messages(history: Sequence[Exchange]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for exchange in history:
        messages.append(ModelRequest(parts=[UserPromptPart(content=exchange.prompt)]))
        messages.append(ModelResponse(parts=[TextPart(content=exchange.narration)]))
    return messages
