from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random
from typing import Literal

from pydantic import JsonValue
from pydantic_ai import Agent, ModelRetry, NativeOutput, RunContext, Tool
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import UsageLimits

from aidm.config import Settings
from aidm.engines.core import (
    RULES_WAIT,
    Advancement,
    AdvancementOffer,
    Command,
    DirectorContext,
    Engine,
    ProposalBase,
    TurnRecord,
    apply_to_draft,
    run_command,
)
from aidm.engines.world import commands
from aidm.llm import build_agent, schema_of
from aidm.state.entities import DEAD
from aidm.state.facts import Fact, narrator_evidence, narrator_lines, player_events, traced
from aidm.state.model import Game, draft_refusal
from aidm.state.play import (
    Answer,
    DecisionOption,
    Exchange,
    Line,
    MechanicEvent,
    Narration,
    PendingDecision,
    StepTrace,
    TurnTrace,
    narration_text,
)

from . import context
from .context import SceneSnapshot, VisibleScene


def as_tool(found: Command) -> Tool[DirectorContext]:
    async def call(ctx: RunContext[DirectorContext], **raw: JsonValue) -> str:
        try:
            return run_command(found, ctx.deps, raw)
        except ValueError as refused:
            raise ModelRetry(str(refused)) from refused

    return Tool.from_schema(
        call,
        found.name,
        found.description,
        schema_of(found.args),
        takes_ctx=True,
        sequential=True,
    )


def director_toolset(engine: Engine) -> FunctionToolset[DirectorContext]:
    return FunctionToolset(tools=[as_tool(one) for one in commands(engine)], max_retries=2)


@dataclass(frozen=True, slots=True)
class AdvancementContext:
    advancement: Advancement
    state: Game
    offer: AdvancementOffer


@dataclass(frozen=True, slots=True)
class TurnAgents:
    director: Agent[DirectorContext, str]
    narrator: Agent[VisibleScene, Narration]


def director_agent(
    engine: Engine,
    settings: Settings,
) -> Agent[DirectorContext, str]:
    """Everything that happens this turn happens through a tool; the closing text only traces."""
    return build_agent(
        "director",
        settings,
        instructions=context.director_instructions(engine.director_instructions),
        output_type=str,
        deps_type=DirectorContext,
        toolsets=[director_toolset(engine)],
    )


def speakers_refusal(scene: VisibleScene, lines: Sequence[Line]) -> str | None:
    """Only the player or someone here with them speaks; the leak rule holds by check, not trust."""
    present = {scene.player.id, *(entity.id for entity in scene.here)}
    strangers = sorted(
        {
            line.speaker_id
            for line in lines
            if line.speaker_id is not None and line.speaker_id not in present
        }
    )
    if not strangers:
        return None
    return (
        f"nobody here has id {', '.join(strangers)}. Only the player or someone here with "
        "them speaks; leave `speaker_id` null for narration."
    )


def narrator_agent(settings: Settings) -> Agent[VisibleScene, Narration]:
    def attributed(ctx: RunContext[VisibleScene], narration: Narration) -> Narration:
        if refused := speakers_refusal(ctx.deps, narration.lines):
            raise ModelRetry(refused)
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
    return f"[At {exchange.place}]\n{body}"


@dataclass(frozen=True, slots=True)
class TurnResult:
    state: Game
    turn: TurnTrace


type TurnStep = Literal["director", "narrator", "scenario_creator"]


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

    history = exchanges_to_messages(state.history[-settings.turn.recent_exchanges :])
    log = TurnRecord(on_event=on_event)
    draft = state.draft()
    prompt, resumed, answered = consume_answer(engine, draft, player_input, rng, log)

    scene, describe = SceneSnapshot.from_game(draft, draft.take_notes()), engine.renderer(draft)

    announce("director")
    director_prompt = context.render_director(
        scene, describe, draft.scenario, prompt, resumed=resumed
    )
    directed = await stages.director.run(
        director_prompt,
        deps=DirectorContext(
            engine=engine,
            draft=draft,
            rng=rng,
            log=log,
            suspended_at_start=draft.pending is not None,
            answered=answered,
        ),
        message_history=history,
        usage_limits=UsageLimits(request_limit=settings.turn.director_request_limit),
    )
    facts = list(log.facts)
    steps = [StepTrace(name="director", prompt=director_prompt, output=directed.output)]

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

    return TurnResult(
        state=close_segment(draft, prompt, lines, tuple(log.events)),
        turn=TurnTrace(
            prompt=prompt,
            facts=tuple(facts),
            narration=narration_text(lines),
            steps=tuple(steps),
        ),
    )


def close_segment(
    draft: Game, prompt: str, lines: tuple[Line, ...], events: tuple[MechanicEvent, ...]
) -> Game:
    """The one place a segment becomes history: builtin and code mode differ only in when."""
    draft.turn_events = ()
    draft.history = (
        *draft.history,
        Exchange(
            prompt=prompt,
            place=draft.world.require(draft.player_location).name,
            lines=lines,
            events=events,
            decision="" if draft.pending is None else draft.pending.prompt,
        ),
    )
    draft.turn += 1
    return draft.committed()


def consume_answer(
    engine: Engine,
    draft: Game,
    player_input: str | Answer,
    rng: Random,
    log: TurnRecord,
) -> tuple[str, str, PendingDecision | None]:
    """The PLAYER ACTION, what a closed answer resolved, and the decision an open answer used."""
    if draft.player.trait(DEAD) is not None:
        raise ValueError("the player is dead. The only way on is to restart.")
    # A new segment starts with no cards: an interrupted turn left its own on the draft.
    draft.turn_events = ()
    # Any input consumes the decision, a revision included: it never survives its own answer.
    consumed, draft.pending = draft.pending, None
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
    traces = traced(landed)
    # A resume that re-suspended has no tool answer to carry the wait, so the prompt says it.
    if draft.pending is not None:
        traces += f"\n- {RULES_WAIT}"
    section = f"asked: {consumed.prompt}\nthe player chose: {option.label}\n{traces}"
    return option.label, section, None


def _resume(
    engine: Engine,
    draft: Game,
    pending: PendingDecision,
    option: DecisionOption,
    rng: Random,
    log: TurnRecord,
) -> tuple[Fact, ...]:
    """A refusal raises: the engine enumerated the option, so it is never model error."""

    def play(target: Game, dice: Random) -> tuple[Fact, ...]:
        return engine.resume(target, pending, option.id, dice)

    if refused := draft_refusal(draft, lambda copy: apply_to_draft(engine, copy, play, Random(0))):
        raise ValueError(refused)
    landed = apply_to_draft(engine, draft, play, rng)
    log.landed(draft, landed, player_events(landed))
    return landed
