from dataclasses import dataclass

from pydantic_ai import ModelRetry, NativeOutput, RunContext

from aidm.config import Settings
from aidm.engines.loader import Advancement, Engine
from aidm.state.advancement import AdvancementOffer, ProposalBase
from aidm.state.world import GameState

from .prompts import entity_state
from .roles import Stage, stage

CORE_ADVISOR = """You are the ADVISOR of a tabletop roleplaying game. The player has earned an \
advancement and says how they want to grow. Turn that into the exact changes their character sheet \
needs, and nothing else.

You write only the player's own character, each change carrying a short `why` the player will \
read before confirming. Stay inside what is ON OFFER: propose exactly the picks it asks for, and \
never a pick it does not list. Keep every change small, concrete, and grounded in \
the rules text you are given — invent no capability the text does not grant.

A change that breaks the rules comes back to you with the reason; fix that change and answer \
again."""


@dataclass(frozen=True, slots=True)
class AdvisorContext:
    advancement: Advancement
    state: GameState
    offer: AdvancementOffer


def advisor(advancement: Advancement, settings: Settings) -> Stage[AdvisorContext, ProposalBase]:
    built = stage(
        "advisor",
        settings,
        instructions=f"{CORE_ADVISOR}\n\n{advancement.instructions}",
        output_type=NativeOutput(advancement.proposal_type),
        deps_type=AdvisorContext,
    )

    def legal(ctx: RunContext[AdvisorContext], proposal: ProposalBase) -> ProposalBase:
        deps = ctx.deps
        refused = deps.advancement.violation(deps.state, deps.offer, proposal)
        if refused is not None:
            raise ModelRetry(refused)
        return proposal

    _ = built.agent.output_validator(legal)
    return built


def render_proposal(engine: Engine, state: GameState, offer: AdvancementOffer, intent: str) -> str:
    player = state.player
    sections = (
        ("ON OFFER", offer.prompt),
        ("RULES TEXT", offer.text),
        (f"PICK EXACTLY {offer.choose}", "\n".join(f"- {ref}" for ref in offer.options)),
        ("THE CHARACTER", f"{player.name}\n{entity_state(player, engine.renderer(state))}"),
        ("WHAT THE PLAYER WANTS", intent),
    )
    return "\n\n".join(f"{title}\n{body}" for title, body in sections if body)
