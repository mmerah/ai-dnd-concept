from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import partial
from random import Random
from typing import Literal, NamedTuple, Self

from pydantic import JsonValue
from pydantic_ai import Agent, ModelRetry, NativeOutput, RunContext, Tool
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import UsageLimits

from aidm.config import Settings
from aidm.engines.core import (
    DirectorTool,
    Engine,
    Play,
    apply_to_draft,
    succession_decision,
)
from aidm.llm import build_agent, schema_of
from aidm.state.entities import DEAD
from aidm.state.facts import NOTHING, Fact, player_events, told_traces, traced
from aidm.state.model import Game, draft_refusal
from aidm.state.play import (
    Answer,
    Exchange,
    Line,
    MechanicEvent,
    Narration,
    StepTrace,
    TurnTrace,
    narration_text,
)

from . import context
from .context import SceneSnapshot, VisibleScene

RULES_WAIT = "the rules now wait on the player's decision"


class TurnResult(NamedTuple):
    state: Game
    turn: TurnTrace


@dataclass(slots=True)
class TurnRecord:
    facts: list[Fact] = field(default_factory=list)
    events: list[MechanicEvent] = field(default_factory=list)
    on_event: Callable[[MechanicEvent], None] | None = None

    def landed(
        self, draft: Game, facts: tuple[Fact, ...], events: tuple[MechanicEvent, ...]
    ) -> None:
        self.facts.extend(facts)
        self.events.extend(events)
        # On the draft too: a harness that commits per tool call reaches the page only through it.
        draft.turn_events = tuple(self.events)
        if self.on_event is not None:
            for event in events:
                self.on_event(event)


@dataclass(frozen=True, slots=True, kw_only=True)
class Turn:
    """One player input to the next hand-back; the draft is the only state that moves."""

    engine: Engine
    draft: Game
    rng: Random
    log: TurnRecord
    # The run began with a re-suspended decision: it develops what the answer caused, no more.
    suspended_at_start: bool = False
    # Receives the draft: builtin passes a no-op and commits once, code mode saves per call.
    commit: Callable[[Game], None]
    prompt: str
    resumed: str
    notes: tuple[str, ...]

    @classmethod
    def begin(
        cls,
        engine: Engine,
        state: Game,
        player_input: str | Answer,
        rng: Random,
        commit: Callable[[Game], None],
        on_event: Callable[[MechanicEvent], None] | None = None,
    ) -> Self:
        log = TurnRecord(on_event=on_event)
        draft = state.draft()
        prompt, resumed = consume_answer(engine, draft, player_input, rng, log)
        notes = draft.take_notes()
        commit(draft)
        return cls(
            engine=engine,
            draft=draft,
            rng=rng,
            commit=commit,
            prompt=prompt,
            resumed=resumed,
            notes=notes,
            log=log,
            suspended_at_start=draft.pending is not None,
        )

    def picture(self) -> str:
        draft = self.draft
        notes = (*self.notes, *self.engine.notes(draft))
        return context.render_director(
            SceneSnapshot.from_game(draft, notes),
            partial(self.engine.describe, draft),
            draft.scenario,
            self.prompt,
            resumed=self.resumed,
        )

    def call(self, name: str, raw: Mapping[str, JsonValue]) -> str:
        """The one gate: a decision on the table blocks everything but developing its answer."""
        found = next((one for one in self.engine.director_tools if one.name == name), None)
        if found is None:
            raise ValueError(f"{name!r} is not a tool of the {self.engine.id!r} engine.")
        pending = self.draft.pending
        if pending is not None and not (found.during_suspension and self.suspended_at_start):
            # A plain answer, not a refusal: a retry prompt would tell the model to try again.
            return (
                f"the rules are waiting on the player: {pending.prompt}\n"
                "Put that to the player, then start the next turn with their answer."
            )
        answered = self._applied(lambda draft, rng: found.call(draft, raw, rng))
        self.commit(self.draft)
        return answered

    def _applied(self, play: Play) -> str:
        """What the call changed, as the Director reads it back."""
        already_pending = len(self.draft.world.pending_notes)
        decided_before = self.draft.pending
        landed = _apply(self.engine, self.draft, play, self.rng, self.log)
        lines = [f"- {fact.trace}" for fact in landed]
        lines.extend(f"- {note}" for note in self.draft.world.pending_notes[already_pending:])
        lines.extend(_reached(self.draft, landed))
        if decided_before is None and self.draft.pending is not None:
            lines.append(f"- {RULES_WAIT}")
        return "\n".join(lines) or NOTHING

    def finish(self, lines: tuple[Line, ...], steps: tuple[StepTrace, ...] = ()) -> TurnResult:
        state = close_segment(self.engine, self.draft, self.prompt, lines, tuple(self.log.events))
        trace = TurnTrace(
            prompt=self.prompt,
            facts=tuple(self.log.facts),
            narration=narration_text(lines),
            steps=steps,
        )
        return TurnResult(state, trace)


def _apply(
    engine: Engine, draft: Game, play: Play, rng: Random, log: TurnRecord
) -> tuple[Fact, ...]:
    """Refused whole against a throwaway copy before one change of it reaches the draft."""
    if refused := draft_refusal(draft, lambda copy: apply_to_draft(engine, copy, play, Random(0))):
        raise ValueError(refused)
    landed = apply_to_draft(engine, draft, play, rng)
    log.landed(draft, landed, player_events(landed))
    return landed


def _reached(draft: Game, facts: Sequence[Fact]) -> list[str]:
    # The prompt was rendered before the discovery, so the instruction authored for it arrives here.
    lines: list[str] = []
    for fact in facts:
        if fact.kind != "entity_discovered" or fact.entity_id is None:
            continue
        reached = draft.world.require(fact.entity_id).when_reached
        if reached:
            lines.append(f"- {reached}")
    return lines


def as_tool(found: DirectorTool) -> Tool[Turn]:
    async def call(ctx: RunContext[Turn], **raw: JsonValue) -> str:
        try:
            return ctx.deps.call(found.name, raw)
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


def director_toolset(engine: Engine) -> FunctionToolset[Turn]:
    return FunctionToolset(tools=[as_tool(one) for one in engine.director_tools], max_retries=2)


@dataclass(frozen=True, slots=True)
class TurnAgents:
    director: Agent[Turn, str]
    narrator: Agent[VisibleScene, Narration]


def director_agent(
    engine: Engine,
    settings: Settings,
) -> Agent[Turn, str]:
    """Everything that happens this turn happens through a tool; the closing text only traces."""
    return build_agent(
        "director",
        settings,
        instructions=context.director_instructions(engine.director_instructions),
        output_type=str,
        deps_type=Turn,
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
        if not narration.text:
            raise ModelRetry("write the narration lines: an empty answer shows the player nothing.")
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
    turn = Turn.begin(engine, state, player_input, rng, lambda _: None, on_event)
    draft, prompt = turn.draft, turn.prompt

    announce("director")
    director_prompt = turn.picture()
    directed = await stages.director.run(
        director_prompt,
        deps=turn,
        message_history=history,
        usage_limits=UsageLimits(request_limit=settings.turn.director_request_limit),
    )
    facts = list(turn.log.facts)
    steps = [
        StepTrace(
            name="director",
            prompt=director_prompt,
            output=directed.output,
            refusals=retry_prompts(directed.new_messages()),
        )
    ]

    lines: tuple[Line, ...] = ()
    if draft.pending is None or told_traces(facts):
        announce("narrator")
        visible = VisibleScene.revealed_from(SceneSnapshot.from_game(draft))
        narrator_prompt = context.render_narrator(
            visible,
            partial(engine.describe, draft),
            draft.scenario,
            evidence=traced(facts, told_only=True),
            prompt=prompt,
        )
        narration = (
            await stages.narrator.run(narrator_prompt, deps=visible, message_history=history)
        ).output
        lines = narration.lines
        steps.append(
            StepTrace(
                name="narrator", prompt=narrator_prompt, output=narration.model_dump(mode="json")
            )
        )

    return turn.finish(lines, tuple(steps))


def retry_prompts(messages: Sequence[ModelMessage]) -> tuple[str, ...]:
    return tuple(
        part.model_response()
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, RetryPromptPart)
    )


def close_segment(
    engine: Engine,
    draft: Game,
    prompt: str,
    lines: tuple[Line, ...],
    events: tuple[MechanicEvent, ...],
) -> Game:
    """The one place a segment becomes history: builtin and code mode differ only in when."""
    if draft.pending is None and draft.player.trait(DEAD) is not None:
        draft.pending = succession_decision(engine, draft)
    draft.record(prompt, lines, events)
    draft.turn += 1
    return draft.committed()


def consume_answer(
    engine: Engine,
    draft: Game,
    player_input: str | Answer,
    rng: Random,
    log: TurnRecord,
) -> tuple[str, str]:
    """The PLAYER ACTION and what a closed answer resolved."""
    chosen = player_input.option_id if isinstance(player_input, Answer) else None
    # Only a listed option — succession, in practice — carries a dead player character's game on.
    if chosen is None and draft.player.trait(DEAD) is not None:
        raise ValueError("the player is dead. The only way on is to restart.")
    # A new segment starts with no cards: an interrupted turn left its own on the draft.
    draft.turn_events = ()
    # Any input consumes the decision, a revision included: it never survives its own answer.
    consumed, draft.pending = draft.pending, None
    if consumed is not None and not consumed.allows_text and chosen is None:
        raise ValueError(f"the {consumed.kind!r} decision takes one of its options, not words")
    if isinstance(player_input, str):
        return player_input, ""
    if chosen is None:
        if consumed is not None:
            draft.world.pending_notes = (
                *draft.world.pending_notes,
                f'The rules paused play to ask the player: "{consumed.prompt}" '
                "The PLAYER ACTION is their answer.",
            )
        return player_input.text, ""
    if consumed is None:
        raise ValueError(f"no decision is open, so option {chosen!r} answers nothing")
    option = next((one for one in consumed.options if one.id == chosen), None)
    if option is None:
        raise ValueError(f"the {consumed.kind!r} decision offers no option {chosen!r}")
    # A refusal raises: the engine enumerated the option, so it is never model error.
    landed = _apply(
        engine, draft, lambda copy, dice: engine.resume(copy, consumed, option.id, dice), rng, log
    )
    traces = traced(landed)
    # A resume that re-suspended has no tool answer to carry the wait, so the prompt says it.
    if draft.pending is not None:
        traces += f"\n- {RULES_WAIT}"
    section = f"asked: {consumed.prompt}\nthe player chose: {option.label}\n{traces}"
    return option.label, section
