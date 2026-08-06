from dataclasses import dataclass

from pydantic_ai import ModelRetry, NativeOutput, RunContext

from ..core.config import Settings
from ..core.engine import AdvancementOffer, Engine, entity_renderer
from ..core.sheet import SheetDelta
from ..core.world import GameState
from .roles import Stage, stage

CORE_ADVISOR = """You are the ADVISOR of a tabletop roleplaying game. The player has earned an \
advancement and says how they want to grow. Turn that into the exact changes their character sheet \
needs, and nothing else.

You write only the player's own sheet, one change per thing that changes, each with a short `why` \
the player will read before confirming. Stay inside what is ON OFFER: propose exactly the picks it \
asks for, and never a pick it does not list. Keep every change small, concrete, and grounded in \
the rules text you are given — invent no capability the text does not grant.

A change that breaks the rules comes back to you with the reason; fix that change and answer \
again."""


@dataclass(frozen=True, slots=True)
class AdvisorContext:
    engine: Engine
    state: GameState
    offer: AdvancementOffer


def advisor(engine: Engine, settings: Settings) -> Stage[AdvisorContext, SheetDelta]:
    built = stage(
        "advisor",
        settings,
        instructions=f"{CORE_ADVISOR}\n\n{engine.proposal.instructions}",
        output_type=NativeOutput(SheetDelta, name="SheetDelta"),
        deps_type=AdvisorContext,
    )

    def legal(ctx: RunContext[AdvisorContext], delta: SheetDelta) -> SheetDelta:
        deps = ctx.deps
        refused = deps.engine.proposal.violation(deps.state, deps.offer, delta)
        if refused is not None:
            raise ModelRetry(refused)
        return delta

    _ = built.agent.output_validator(legal)
    return built


def render_proposal(engine: Engine, state: GameState, offer: AdvancementOffer, intent: str) -> str:
    player = state.player
    sections = (
        ("ON OFFER", offer.prompt),
        ("RULES TEXT", offer.text),
        (f"PICK EXACTLY {offer.choose}", "\n".join(f"- {ref}" for ref in offer.options)),
        ("THE CHARACTER", f"{player.name}\n{entity_renderer(engine, state)(player)}"),
        ("WHAT THE PLAYER WANTS", intent),
    )
    return "\n\n".join(f"{title}\n{body}" for title, body in sections if body)
