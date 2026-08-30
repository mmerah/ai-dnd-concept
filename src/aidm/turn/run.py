from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from random import Random
from typing import Literal, Self

from pydantic import JsonValue
from pydantic_ai import Agent, ModelRetry, NativeOutput, RunContext, Tool
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import UsageLimits

from aidm.config import Settings
from aidm.engines.core import Engine
from aidm.kernel.views import NarratorView
from aidm.kits.scenes.boundary import SPENT_NOTE, scene_spent
from aidm.llm import build_agent, schema_of
from aidm.state.facts import NOTHING, Fact, cards, told_traces, traced
from aidm.state.model import Game, draft_refusal
from aidm.state.play import Answer, Exchange, Line, Narration, SpokenLine
from aidm.state.tools import DirectorTool, Play, apply_to_draft

from . import context

RULES_WAIT = "the rules now wait on the player's decision"


@dataclass(slots=True, kw_only=True)
class Turn:
    """One player input to the next hand-back; the draft is the only state that moves."""

    engine: Engine
    draft: Game
    rng: Random
    # Receives the draft: builtin passes a no-op and commits once, code mode saves per call.
    commit: Callable[[Game], None]
    on_fact: Callable[[Fact], None] | None = None
    facts: list[Fact] = field(default_factory=list)
    # The run began with a re-suspended decision: it develops what the answer caused, no more.
    suspended_at_start: bool = False
    prompt: str = ""
    resumed: str = ""
    notes: tuple[str, ...] = ()

    @classmethod
    def begin(
        cls,
        engine: Engine,
        state: Game,
        player_input: str | Answer,
        rng: Random,
        commit: Callable[[Game], None],
        on_fact: Callable[[Fact], None] | None = None,
    ) -> Self:
        turn = cls(engine=engine, draft=state.draft(), rng=rng, commit=commit, on_fact=on_fact)
        turn.prompt, turn.resumed = consume_answer(turn, player_input)
        turn.notes = turn.draft.take_notes()
        turn.suspended_at_start = turn.draft.pending is not None
        commit(turn.draft)
        return turn

    def landed(self, facts: tuple[Fact, ...]) -> None:
        self.facts.extend(facts)
        # On the draft too: a harness that commits per tool call reaches the page only through it.
        self.draft.turn_facts = cards(tuple(self.facts))
        if self.on_fact is not None:
            for fact in facts:
                self.on_fact(fact)

    def picture(self) -> str:
        draft = self.draft
        return context.render_director(
            self.engine.views(draft).director.sections,
            draft.scenario,
            self.prompt,
            resumed=self.resumed,
            notes=(*self.notes, *draft.notes),
        )

    def call(self, name: str, raw: Mapping[str, JsonValue]) -> str:
        """The one gate: a decision on the table blocks everything but developing its answer."""
        found = next((one for one in self.engine.tools if one.name == name), None)
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
        already_pending = len(self.draft.notes)
        decided_before = self.draft.pending
        landed = _apply(self, play)
        lines = [f"- {fact.trace}" for fact in landed]
        lines.extend(f"- {note}" for note in self.draft.notes[already_pending:])
        if decided_before is None and self.draft.pending is not None:
            lines.append(f"- {RULES_WAIT}")
        return "\n".join(lines) or NOTHING

    def finish(self, lines: tuple[Line, ...]) -> Game:
        return close_segment(
            self.engine.views(self.draft).narrator,
            self.draft,
            self.prompt,
            lines,
            tuple(self.facts),
        )


def _apply(turn: Turn, play: Play) -> tuple[Fact, ...]:
    """Refused whole against a throwaway copy before one change of it reaches the draft."""
    engine, draft = turn.engine, turn.draft
    if refused := draft_refusal(
        draft, lambda copy: apply_to_draft(engine.validate, copy, play, deepcopy(turn.rng))
    ):
        raise ValueError(refused)
    landed = apply_to_draft(engine.validate, draft, play, turn.rng)
    turn.landed(landed)
    return landed


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
    return FunctionToolset(tools=[as_tool(one) for one in engine.tools], max_retries=2)


@dataclass(frozen=True, slots=True)
class TurnAgents:
    director: Agent[Turn, str]
    narrator: Agent[NarratorView, Narration]


def director_agent(
    engine: Engine,
    settings: Settings,
) -> Agent[Turn, str]:
    """Everything that happens this turn happens through a tool; the closing text only traces."""
    return build_agent(
        "director",
        settings,
        instructions=context.director_instructions(engine.instructions),
        output_type=str,
        deps_type=Turn,
        toolsets=[director_toolset(engine)],
    )


def speakers_refusal(view: NarratorView, lines: Sequence[Line]) -> str | None:
    """Only the player or someone here with them speaks; the leak rule holds by check, not trust."""
    here = {one.id for one in view.speakers}
    strangers = sorted(
        {
            line.speaker_id
            for line in lines
            if line.speaker_id is not None and line.speaker_id not in here
        }
    )
    if not strangers:
        return None
    return (
        f"nobody here has id {', '.join(strangers)}. Only the player or someone here with "
        "them speaks; leave `speaker_id` null for narration."
    )


def narrator_agent(settings: Settings) -> Agent[NarratorView, Narration]:
    def attributed(ctx: RunContext[NarratorView], narration: Narration) -> Narration:
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
        deps_type=NarratorView,
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
    return f"[At {exchange.scene}]\n{body}"


type TurnStep = Literal["director", "narrator", "scenario_creator"]


async def run_segment(
    turn: Turn,
    *,
    stages: TurnAgents,
    settings: Settings,
    on_step: Callable[[TurnStep], None] | None = None,
) -> tuple[Line, ...]:
    def announce(step: TurnStep) -> None:
        if on_step is not None:
            on_step(step)

    draft, prompt = turn.draft, turn.prompt
    history = exchanges_to_messages(draft.history[-settings.turn.recent_exchanges :])

    announce("director")
    director_prompt = turn.picture()
    _ = await stages.director.run(
        director_prompt,
        deps=turn,
        message_history=history,
        usage_limits=UsageLimits(request_limit=settings.turn.director_request_limit),
    )
    facts = list(turn.facts)

    lines: tuple[Line, ...] = ()
    if draft.pending is None or told_traces(facts):
        announce("narrator")
        view = turn.engine.views(draft).narrator
        narrator_prompt = context.render_narrator(
            view,
            draft.scenario,
            evidence=traced(facts, told_only=True),
            prompt=prompt,
        )
        narration = (
            await stages.narrator.run(narrator_prompt, deps=view, message_history=history)
        ).output
        lines = narration.lines

    return lines


def spoken(view: NarratorView, lines: Sequence[Line]) -> tuple[SpokenLine, ...]:
    """Attribution is denormalized here, so chat and journal never resolve ids through state."""
    here = {one.id: one for one in view.speakers}

    def one(line: Line) -> SpokenLine:
        if line.speaker_id is None:
            return SpokenLine(text=line.text)
        who = here.get(line.speaker_id)
        if who is None:
            raise ValueError(f"nobody here has id {line.speaker_id!r}")
        return SpokenLine(speaker=who, text=line.text)

    return tuple(one(line) for line in lines)


def close_segment(
    view: NarratorView,
    draft: Game,
    prompt: str,
    lines: tuple[Line, ...],
    facts: tuple[Fact, ...],
) -> Game:
    """The one place a segment becomes history: builtin and code mode differ only in when."""
    draft.record(draft.world.current.title, prompt, spoken(view, lines), facts)
    draft.turn += 1
    # Directive text at the decision point is what fixed trigger reliability when it was measured.
    if (reason := scene_spent(draft)) is not None:
        draft.notes = (*draft.notes, SPENT_NOTE.format(reason=reason))
    return draft.committed()


def consume_answer(turn: Turn, player_input: str | Answer) -> tuple[str, str]:
    """The PLAYER ACTION and what a closed answer resolved."""
    engine, draft = turn.engine, turn.draft
    chosen = player_input.option_id if isinstance(player_input, Answer) else None
    if (ended := engine.over(draft)) is not None:
        raise ValueError(f"{ended} The only way on is to restart.")
    # A new segment starts with no cards: an interrupted turn left its own on the draft.
    draft.turn_facts = ()
    # Any input consumes the decision, a revision included: it never survives its own answer.
    consumed, draft.pending = draft.pending, None
    if consumed is not None and not consumed.allows_text and chosen is None:
        raise ValueError(f"the {consumed.kind!r} decision takes one of its options, not words")
    if isinstance(player_input, str):
        return player_input, ""
    if chosen is None:
        if consumed is not None:
            draft.notes = (
                *draft.notes,
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
    landed = _apply(turn, lambda copy, dice: engine.answer(copy, option, dice))
    traces = traced(landed)
    # A resume that re-suspended has no tool answer to carry the wait, so the prompt says it.
    if draft.pending is not None:
        traces += f"\n- {RULES_WAIT}"
    section = f"asked: {consumed.prompt}\nthe player chose: {option.label}\n{traces}"
    return option.label, section
