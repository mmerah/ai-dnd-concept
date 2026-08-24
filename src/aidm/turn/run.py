from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random
from typing import Literal

from pydantic_ai import Agent, ModelRetry, NativeOutput, RunContext
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.tools import ToolDefinition, ToolFuncEither
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import UsageLimits

from aidm.config import Role, Settings
from aidm.engines.core import (
    NOTHING_CHANGED,
    RULES_WAIT,
    Advancement,
    Engine,
    EventCause,
    Offer,
    PlanContext,
    ProposalBase,
    TurnLog,
    act,
    apply_to_draft,
    sequential_toolset,
    with_enum,
)
from aidm.llm import build_agent
from aidm.state import actions
from aidm.state.entities import PLAYER_ID, EntityId, Slug
from aidm.state.facts import Fact, narrator_evidence, narrator_lines
from aidm.state.model import AdvanceThread, Game, draft_refusal
from aidm.state.play import (
    Answer,
    Exchange,
    Line,
    MechanicEvent,
    Narration,
    Option,
    PendingDecision,
    StepTrace,
    Turn,
    narration_text,
)

from . import context
from .context import SceneSnapshot, VisibleScene


@dataclass(frozen=True, slots=True)
class CoreTool:
    """A director tool with the state predicate that decides whether it is offered at all."""

    func: ToolFuncEither[PlanContext, ...]
    applies: Callable[[Game], bool] = lambda _state: True


def core_toolset() -> AbstractToolset[PlanContext]:
    def reveal(ctx: RunContext[PlanContext], entity_id: EntityId) -> str:
        """Reveal an entity that exists but the player does not know yet: they notice it, are told
        of it, or reach it.

        Args:
            entity_id: Exact id of the unrevealed canon entity.
        """
        return _resolved(ctx, lambda draft: actions.reveal(draft, entity_id))

    def move(ctx: RunContext[PlanContext], entity_id: EntityId, to_id: EntityId) -> str:
        """Move an actor who actually changes location, or one item within the player's reach:
        picked up, set down here, or handed to an actor here.

        Args:
            entity_id: Exact id of the actor or item that moves; `player` is the played character.
                An item must be one the player carries, or one loose at their location.
            to_id: Exact id of where it goes: for an actor the location they enter; for an item,
                `player` to pick it up, an actor here with the player to hand it over, or the
                player's own location to set it down.
        """
        return _resolved(ctx, lambda draft: actions.move(draft, entity_id, to_id))

    def gain_improvised_item(ctx: RunContext[PlanContext], item_name: str) -> str:
        """Give the player an ordinary incidental object that is not in canon and is not worth a
        canon entry of its own.

        Args:
            item_name: The object written out, such as 'a handful of gravel'.
        """
        return _resolved(ctx, lambda draft: actions.improvise(draft, item_name))

    def add_trait(
        ctx: RunContext[PlanContext], entity_id: EntityId, trait_id: Slug, text: str
    ) -> str:
        """Put a lasting condition, skill, or frailty on an entity.

        Args:
            entity_id: Exact id of the entity affected; an actor must be here with the player.
            trait_id: Stable slug for the trait, such as `poisoned`; it shows written out, so
                `battle-worn` appears as Battle Worn.
            text: The constraint or benefit it puts on the entity, in prose.
        """
        return _resolved(ctx, lambda draft: actions.add_trait(draft, entity_id, trait_id, text))

    def remove_trait(ctx: RunContext[PlanContext], entity_id: EntityId, trait_id: Slug) -> str:
        """Lift a lasting condition, skill, or frailty the fiction has ended.

        Args:
            entity_id: Exact id of the entity affected; an actor must be here with the player.
            trait_id: Exact id of a trait the entity carries.
        """
        return _resolved(ctx, lambda draft: actions.remove_trait(draft, entity_id, trait_id))

    def advance_thread(ctx: RunContext[PlanContext], advance: AdvanceThread) -> str:
        """Move a storyline the scenario is tracking: where it stands now, or that it is over.

        Args:
            advance: The movement to apply.
        """
        return _resolved(ctx, lambda draft: actions.advance_thread(draft, advance))

    def unlock_exit(ctx: RunContext[PlanContext], to_id: EntityId) -> str:
        """Open a locked way out of the player's location.

        Args:
            to_id: Exact id of the location the way leads to.
        """
        return _resolved(ctx, lambda draft: actions.unlock_exit(draft, to_id))

    def join_party(ctx: RunContext[PlanContext], actor_id: EntityId) -> str:
        """Put an actor into the player's party.

        Args:
            actor_id: Exact id of the actor joining, who must be here with the player.
        """
        return _resolved(ctx, lambda draft: actions.join_party(draft, actor_id))

    def leave_party(ctx: RunContext[PlanContext], actor_id: EntityId) -> str:
        """Take an actor out of the player's party when the fiction parts them.

        Args:
            actor_id: Exact id of the actor leaving.
        """
        return _resolved(ctx, lambda draft: actions.leave_party(draft, actor_id))

    tools = (
        CoreTool(reveal),
        CoreTool(move),
        CoreTool(gain_improvised_item),
        CoreTool(add_trait),
        CoreTool(remove_trait, _a_trait_in_reach),
        CoreTool(advance_thread, _an_unresolved_thread),
        CoreTool(unlock_exit, _a_locked_way_out),
        CoreTool(join_party, _an_actor_to_recruit),
        CoreTool(leave_party, _a_party_member),
    )
    # Keyed off the functions themselves, so a renamed tool cannot lose its predicate.
    applies = {tool.func.__name__: tool.applies for tool in tools}
    return (
        sequential_toolset([tool.func for tool in tools])
        .prepared(_narrow_unlock_targets)
        .filtered(lambda ctx, tool: applies[tool.name](ctx.deps.state))
    )


def _resolved(ctx: RunContext[PlanContext], apply: Callable[[Game], list[Fact]]) -> str:
    return act(ctx, lambda draft, _rng: tuple(apply(draft)))


def _unlock_targets(state: Game) -> list[str]:
    here = state.world.require_kind(state.player_location, "location")
    return sorted(w.to for w in here.exits if w.locked)


def _narrow_unlock_targets(
    ctx: RunContext[PlanContext], tools: list[ToolDefinition]
) -> list[ToolDefinition]:
    # This runs before impossible tools are filtered, so an empty enum would have no legal value.
    targets = _unlock_targets(ctx.deps.state)
    return [
        with_enum(tool, ("to_id",), targets) if tool.name == "unlock_exit" and targets else tool
        for tool in tools
    ]


def _a_locked_way_out(state: Game) -> bool:
    return bool(_unlock_targets(state))


def _an_actor_to_recruit(state: Game) -> bool:
    return any(
        entity.kind == "actor" and entity.id != PLAYER_ID and entity.id not in state.world.party
        for entity in state.world.entities
        if state.is_here(entity)
    )


def _a_party_member(state: Game) -> bool:
    return bool(state.world.party)


def _an_unresolved_thread(state: Game) -> bool:
    # The set the scene renders under ACTIVE THREADS: a thread put dormant is still movable.
    return any(thread.status != "resolved" for thread in state.world.threads)


def _a_trait_in_reach(state: Game) -> bool:
    # `is_here` is false of a location, which carries tags of its own that `add_trait` may write.
    return any(
        entity.traits
        for entity in state.world.entities
        if state.is_here(entity) or entity.id == state.player_location
    )


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
        core_toolset().filtered(
            lambda ctx, _tool: ctx.deps.state.pending is None or ctx.deps.suspended_at_start
        ),
        # A suspended run may develop what the answer caused; it may not open new mechanics.
        *(
            toolset.filtered(lambda ctx, _tool: ctx.deps.state.pending is None)
            for toolset in engine.director_toolsets
        ),
    ]
    return build_agent(
        "director",
        settings,
        instructions=context.director_instructions(engine.director_instructions),
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
        instructions=context.NARRATOR,
        output_type=NativeOutput(Narration),
        deps_type=VisibleScene,
        validator=attributed,
    )


def advisor_agent(
    advancement: Advancement, settings: Settings
) -> Agent[AdvancementContext, ProposalBase]:
    def legal(ctx: RunContext[AdvancementContext], proposal: ProposalBase) -> ProposalBase:
        deps = ctx.deps
        refused = deps.advancement.advance_refusal(deps.state, deps.offer, proposal)
        if refused is not None:
            raise ModelRetry(refused)
        return proposal

    return build_agent(
        "advisor",
        settings,
        instructions=context.advisor_instructions(advancement.instructions),
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
        messages.append(ModelResponse(parts=[TextPart(content=_replayed(exchange))]))
    return messages


def _replayed(exchange: Exchange) -> str:
    parts = [exchange.narration]
    if exchange.decision:
        parts.append(f"[The rules paused the turn for the player: {exchange.decision}]")
    body = "\n".join(part for part in parts if part)
    if not body:
        raise ValueError("an exchange with neither prose nor a decision has nothing to replay")
    return body


@dataclass(frozen=True, slots=True)
class TurnResult:
    state: Game
    turn: Turn


type TurnStep = Literal["director", "narrator", "worldsmith"]


async def run_segment(
    state: Game,
    player_input: str | Answer,
    *,
    engine: Engine,
    stages: TurnAgents,
    settings: Settings,
    rng: Random,
    on_step: Callable[[TurnStep], None] | None = None,
    on_event: Callable[[MechanicEvent], None] | None = None,
) -> TurnResult:
    """One player input to the next hand-back, committed whole."""

    def announce(step: TurnStep) -> None:
        if on_step is not None:
            on_step(step)

    history = exchanges_to_messages(state.history)
    history_chars = sum(
        len(exchange.prompt) + len(exchange.narration) + len(exchange.decision)
        for exchange in state.history
    )
    log = TurnLog(on_event=on_event)
    draft = state.draft()
    # Any input consumes the decision, a revision included: it never survives its own answer.
    consumed, draft.pending = draft.pending, None
    prompt, resumed, answered = _consume(engine, draft, player_input, consumed, rng, log)

    scene, describe = SceneSnapshot.from_game(draft), engine.renderer(draft)

    announce("director")
    director_prompt = context.render_director(
        scene, describe, draft.scenario, prompt, resumed=resumed
    )
    _ensure_input_budget("director", settings, director_prompt, history_chars)
    shown = len(draft.world.pending_notes)
    directed = await stages.director.run(
        director_prompt,
        deps=PlanContext(
            engine=engine,
            state=draft,
            rng=rng,
            log=log,
            suspended_at_start=draft.pending is not None,
            answered=answered,
        ),
        message_history=history,
        usage_limits=UsageLimits(request_limit=settings.turn.director_request_limit),
    )
    # Only what the prompt rendered is spent; a note its own tools wrote steers the next turn too.
    draft.world.pending_notes = draft.world.pending_notes[shown:]
    facts = list(log.facts)
    steps: list[StepTrace] = [
        StepTrace(name="director", prompt=director_prompt, output=directed.output),
        *log.steps,
    ]

    lines: tuple[Line, ...] = ()
    if draft.pending is None or narrator_lines(facts):
        announce("narrator")
        visible = VisibleScene.revealed_from(SceneSnapshot.from_game(draft))
        narrator_prompt = context.render_narrator(
            visible,
            engine.renderer(draft),
            draft.scenario,
            evidence=narrator_evidence(facts),
            prompt=prompt,
        )
        _ensure_input_budget("narrator", settings, narrator_prompt, history_chars)
        narration = (
            await stages.narrator.run(narrator_prompt, deps=visible, message_history=history)
        ).output
        if not narration.text:
            raise ValueError("the narrator answered with nothing")
        lines = narration.lines
        steps.append(
            StepTrace(
                name="narrator", prompt=narrator_prompt, output=narration.model_dump(mode="json")
            )
        )

    draft.history = (
        *draft.history,
        Exchange(
            prompt=prompt,
            lines=lines,
            events=tuple(log.events),
            decision="" if draft.pending is None else draft.pending.prompt,
        ),
    )
    draft.turn += 1
    return TurnResult(
        state=draft.committed(),
        turn=Turn(
            prompt=prompt,
            facts=tuple(facts),
            narration=narration_text(lines),
            steps=tuple(steps),
        ),
    )


def _consume(
    engine: Engine,
    draft: Game,
    player_input: str | Answer,
    consumed: PendingDecision | None,
    rng: Random,
    log: TurnLog,
) -> tuple[str, str, PendingDecision | None]:
    """The PLAYER ACTION, what a closed answer resolved, and the decision an open answer used."""
    if isinstance(player_input, str):
        return player_input, "", None
    chosen = player_input.option_id
    if chosen is None:
        if consumed is not None:
            draft.world.pending_notes = (
                *draft.world.pending_notes,
                f'The rules paused play to ask the player: "{consumed.prompt}" '
                "The PLAYER ACTION is their answer.",
            )
        return player_input.text, "", consumed
    if consumed is None:
        raise ValueError(f"no decision is open, so option {chosen!r} answers nothing")
    option = next((one for one in consumed.options if one.id == chosen), None)
    if option is None:
        raise ValueError(f"the {consumed.kind!r} decision offers no option {chosen!r}")
    landed = _resume(engine, draft, consumed, option, rng, log)
    traces = "\n".join(f"- {fact.trace}" for fact in landed) or NOTHING_CHANGED
    # A resume that re-suspended has no tool answer to carry the wait, so the prompt says it.
    if draft.pending is not None:
        traces += f"\n- {RULES_WAIT}"
    section = f"asked: {consumed.prompt}\nthe player chose: {option.label}\n{traces}"
    return option.label, section, None


def _resume(
    engine: Engine,
    draft: Game,
    pending: PendingDecision,
    option: Option,
    rng: Random,
    log: TurnLog,
) -> tuple[Fact, ...]:
    """A refusal raises: the engine enumerated the option, so it is never model error."""

    def play(target: Game, dice: Random) -> tuple[Fact, ...]:
        return engine.resume(target, pending, option.id, dice)

    if refused := draft_refusal(draft, lambda copy: apply_to_draft(engine, copy, play, Random(0))):
        raise ValueError(refused)
    landed = apply_to_draft(engine, draft, play, rng)
    log.landed(landed, engine.player_events(EventCause("decision", pending.kind), landed))
    return landed


def _ensure_input_budget(role: Role, settings: Settings, rendered: str, history_chars: int) -> None:
    ceiling = settings.role(role).max_input_tokens
    estimate = (len(rendered) + history_chars) // settings.turn.chars_per_token
    if estimate > ceiling:
        raise ValueError(
            f"{role} input is about {estimate} tokens, over its {ceiling}-token ceiling; "
            "this game has too much history for a turn to fit"
        )
