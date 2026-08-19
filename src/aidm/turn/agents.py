from collections.abc import Sequence
from dataclasses import dataclass
from random import Random

from pydantic_ai import (
    Agent,
    ModelRetry,
    NativeOutput,
    RunContext,
    UnexpectedModelBehavior,
)
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset

from aidm.config import Settings
from aidm.content.sources import CanonSource
from aidm.engines.advancement import Advancement, Offer, ProposalBase
from aidm.engines.engine import Engine, PlanContext
from aidm.engines.sheets import SheetBase
from aidm.engines.transact import apply_to_draft
from aidm.llm import build_agent
from aidm.state.base import EntityId, Kind
from aidm.state.history import Exchange, Narration
from aidm.state.resolution import check_draft
from aidm.state.world import GameState

from . import prompts
from .expansion import MAX_EXPANSIONS, ExpansionPatch, apply_patch, capped, record, written
from .reports import WorldkeeperReport
from .scene import SceneSnapshot, VisibleScene
from .tools import core_toolset, possible, sequential_toolset


@dataclass(frozen=True, slots=True)
class AdvancementContext:
    advancement: Advancement
    state: GameState
    offer: Offer


@dataclass(frozen=True, slots=True)
class TurnAgents:
    """The turn's model-facing roles, built once per session."""

    director: Agent[PlanContext, str]
    narrator: Agent[VisibleScene, Narration]
    worldkeeper: Agent[GameState, WorldkeeperReport]
    # Built only when the adventure may expand; the turn reaches it through the Director's tool.
    expander: Agent[PlanContext, ExpansionPatch] | None = None


def director_agent(
    engine: Engine[SheetBase],
    settings: Settings,
    expand_tool: FunctionToolset[PlanContext] | None = None,
) -> Agent[PlanContext, str]:
    """Everything that happens this turn happens through a tool; the closing text only traces."""
    toolsets: list[AbstractToolset[PlanContext]] = [
        core_toolset().filtered(lambda ctx, tool: possible(tool.name, ctx.deps.state)),
        *engine.director_toolsets,
    ]
    if expand_tool is not None:
        toolsets.append(expand_tool.filtered(lambda ctx, _tool: not capped(ctx.deps.log)))
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


def worldkeeper_agent(settings: Settings) -> Agent[GameState, WorldkeeperReport]:
    def known(ctx: RunContext[GameState], report: WorldkeeperReport) -> WorldkeeperReport:
        state = ctx.deps
        strangers = sorted(
            {
                memory.owner_id
                for memory in report.memories
                if memory.owner_id is not None and state.world.find(memory.owner_id) is None
            }
        )
        if strangers:
            raise ModelRetry(
                f"nobody holds a memory who does not exist: {', '.join(strangers)}. Use an exact "
                "id from the catalogue, or null for the world."
            )
        return report

    return build_agent(
        "worldkeeper",
        settings,
        instructions=prompts.WORLDKEEPER,
        output_type=NativeOutput(WorldkeeperReport),
        deps_type=GameState,
        validator=known,
    )


def expander_agent(settings: Settings) -> Agent[PlanContext, ExpansionPatch]:
    """A patch that would not commit is refused here, against a throwaway draft, so the turn's own
    draft only ever sees canon that lands."""

    def sound(ctx: RunContext[PlanContext], patch: ExpansionPatch) -> ExpansionPatch:
        deps = ctx.deps

        # The whole mutation sequence the real one will run, hooks and seeding included: whatever
        # a thinner trial skipped would fail the turn outright instead of asking again.
        def trial(draft: GameState) -> object:
            return apply_to_draft(
                deps.engine, draft, lambda copy, _rng: apply_patch(copy, patch), Random(0)
            )

        if refused := check_draft(deps.state, trial):
            raise ModelRetry(refused)
        return patch

    return build_agent(
        "expander",
        settings,
        instructions=prompts.EXPANDER,
        output_type=NativeOutput(ExpansionPatch),
        deps_type=PlanContext,
        validator=sound,
    )


def expansion_toolset(
    engine: Engine[SheetBase],
    expander: Agent[PlanContext, ExpansionPatch],
    source: CanonSource,
) -> FunctionToolset[PlanContext]:
    async def expand_world(
        ctx: RunContext[PlanContext],
        kind: Kind,
        anchor_id: EntityId,
        need: str,
        queries: tuple[str, ...] = (),
    ) -> str:
        """Write canon this world does not hold yet, when what the turn reaches for is genuinely
        absent — never as a replacement for something that already exists. Read EXISTS BUT THE
        PLAYER DOES NOT KNOW IT YET first: while anything there answers the turn, this call is
        wrong, and so is calling it for a turn that reaches for nothing in particular. What comes
        back is unknown to the player, so reveal it or move them to it in this same turn. Returns
        the ids written.

        Args:
            kind: The kind of thing that is missing.
            anchor_id: Exact id of the entity the missing thing hangs off.
            need: The need it fills, in a sentence of plain words.
            queries: The words the adventure's own text would use for it — names, places, and
                objects — which is how the source is looked up for you.
        """
        deps, draft = ctx.deps, ctx.deps.state
        anchor = draft.world.find(anchor_id)
        if anchor is None:
            raise ModelRetry(f"nothing here has id {anchor_id!r}. Use an id you were shown.")
        if capped(deps.log):
            raise ModelRetry(
                f"you have already reached for new canon {MAX_EXPANSIONS} times this turn. Plan "
                "the rest with what already exists."
            )
        # The anchor name is folded in because a `need` written as an identifier retrieves nothing
        # on its own.
        found = source.passages(" ".join((anchor.name, need, *queries)))
        if not found:
            raise ModelRetry(
                f"the source holds nothing about {need!r}. Ask again with the words the "
                "adventure's own text would use for it, or plan this turn with what exists."
            )
        asked = (
            f"kind: {kind}\nanchor: {anchor.name}[id={prompts.prompt_id(anchor.id)}]\nneed: {need}"
        )
        prompt = prompts.render_expander(
            SceneSnapshot.of(draft),
            engine.renderer(draft),
            draft.scenario,
            context=found,
            request=asked,
        )
        try:
            patch = (await expander.run(prompt, deps=deps)).output
        except UnexpectedModelBehavior as refused:
            # Recorded before the retry: an expansion that wrote nothing is the one the trace is
            # read for, and the Expander's own prompt and reason exist nowhere else.
            record(deps.log, prompt, f"no canon written: {refused}")
            raise ModelRetry(
                f"no canon could be written ({refused}). Plan this turn with what already exists."
            ) from refused
        record(deps.log, prompt, patch)
        # Outside the retry: the patch's own author already ran this sequence against a throwaway
        # draft, and a half-applied draft is not a state the rest of the turn can act against.
        landed = apply_to_draft(
            engine, draft, lambda copy, _rng: apply_patch(copy, patch), deps.rng
        )
        deps.log.facts.extend(landed.facts)
        deps.log.fired.extend(landed.fired)
        return written(patch)

    return sequential_toolset([expand_world])


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


def build_turn_agents(
    engine: Engine[SheetBase], settings: Settings, source: CanonSource | None = None
) -> TurnAgents:
    """A game with nothing to expand from builds no Expander, so its Director agent is the one
    shipped today."""
    expander: Agent[PlanContext, ExpansionPatch] | None = None
    expand_tool: FunctionToolset[PlanContext] | None = None
    if source is not None:
        expander = expander_agent(settings)
        expand_tool = expansion_toolset(engine, expander, source)
    return TurnAgents(
        director=director_agent(engine, settings, expand_tool),
        narrator=narrator_agent(settings),
        worldkeeper=worldkeeper_agent(settings),
        expander=expander,
    )


def exchanges_to_messages(history: Sequence[Exchange]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for exchange in history:
        messages.append(ModelRequest(parts=[UserPromptPart(content=exchange.prompt)]))
        messages.append(ModelResponse(parts=[TextPart(content=exchange.narration)]))
    return messages
