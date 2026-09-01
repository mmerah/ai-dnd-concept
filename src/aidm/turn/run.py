from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from random import Random
from typing import Literal, Self

from pydantic import BaseModel, JsonValue, ValidationError

from aidm.core.facts import NOTHING, Fact, traced
from aidm.core.model import AnyGame
from aidm.core.play import Answer, Line, Narration, SpokenLine
from aidm.core.tools import NoArgs, Play, apply_to_draft
from aidm.core.views import NarratorView
from aidm.engines.core import AnyEngine
from aidm.turn.context import render_picture

RULES_WAIT = "the rules now wait on the player's decision"
NO_TURN = "no turn is open. The player starts one from the page; wait to be spawned again."
START_FIRST = "call `start_turn` first: it opens the turn and hands back the picture."
ALREADY_OPEN = "the turn is already open. `scene` gives the picture back."
DECIDING = "the rules are waiting on the player; the scene after this one waits with them."
GAME_OVER = "The game is over; the player restarts from the page."

type TurnStep = Literal["master", "narrator", "worldsmith"]


@dataclass(slots=True, kw_only=True)
class Turn:
    """The transaction: one player input applied to a draft. The session owns the lifecycle."""

    engine: AnyEngine
    draft: AnyGame
    rng: Random
    on_fact: Callable[[Fact], None] | None = None
    facts: list[Fact] = field(default_factory=list)
    # The run began with a re-suspended decision: it develops what the answer caused, no more.
    suspended_at_start: bool = False
    prompt: str = ""
    resumed: str = ""
    notes: tuple[str, ...] = ()
    # Injected, so `turn` reads no settings itself.
    recent: int = 0
    # The game master has called `start_turn`; nothing may change the world before it does.
    started: bool = False

    @classmethod
    def begin(
        cls,
        engine: AnyEngine,
        state: AnyGame,
        player_input: str | Answer,
        rng: Random,
        recent: int,
        on_fact: Callable[[Fact], None] | None = None,
    ) -> Self:
        turn = cls(engine=engine, draft=state.draft(), rng=rng, recent=recent, on_fact=on_fact)
        turn.prompt, turn.resumed = consume_answer(turn, player_input)
        # Notes are read once; a note a tool writes after this steers the next turn.
        turn.notes, turn.draft.notes = turn.draft.notes, ()
        turn.suspended_at_start = turn.draft.pending is not None
        return turn

    def start_turn(self) -> str:
        self.started = True
        return self.picture()

    def picture(self) -> str:
        return render_picture(
            self.engine.master_sections(self.draft),
            self.draft,
            self.engine.history(self.draft),
            self.prompt,
            resumed=self.resumed,
            notes=(*self.notes, *self.draft.notes),
            recent=self.recent,
        )

    def call(self, name: str, raw: Mapping[str, JsonValue]) -> str:
        """The one gate: every published tool is refused, answered or applied here."""
        if name == "start_turn" and self.started:
            raise ValueError(ALREADY_OPEN)
        if name not in ("scene", "start_turn"):
            if not self.started:
                raise ValueError(START_FIRST)
            if (ended := self.engine.over(self.draft)) is not None:
                raise ValueError(f"{ended} {GAME_OVER}")
        if (served := next((one for one in TURN_TOOLS if one.name == name), None)) is not None:
            _ = served.args.model_validate(raw)
            return served.run(self)
        found = next(
            (one for one in self.engine.tools if one.name == name),
            None,
        )
        if found is None:
            raise ValueError(f"{name!r} is not a tool of the {self.engine.id!r} engine.")
        pending = self.draft.pending
        if name == "next_scene" and pending is not None:
            raise ValueError(DECIDING)
        if pending is not None and not (found.during_suspension and self.suspended_at_start):
            # A plain answer, not a refusal: a retry prompt would tell the model to try again.
            return (
                f"the rules are waiting on the player: {pending.prompt}\n"
                "Stop here and exit; the player's answer opens the next turn."
            )
        return self.apply(lambda draft, rng: found.call(draft, raw, rng))

    def apply(self, play: Play[AnyGame]) -> str:
        """What the call changed, as the game master reads it back."""
        already_pending = len(self.draft.notes)
        decided_before = self.draft.pending
        landed = _apply(self, play)
        lines = [f"- {fact.trace}" for fact in landed]
        lines.extend(f"- {note}" for note in self.draft.notes[already_pending:])
        if decided_before is None and self.draft.pending is not None:
            lines.append(f"- {RULES_WAIT}")
        return "\n".join(lines) or NOTHING

    def finish(self, lines: tuple[Line, ...]) -> AnyGame:
        return close_segment(
            self.engine,
            self.engine.narrator_view(self.draft),
            self.draft,
            self.prompt,
            lines,
            tuple(self.facts),
        )


@dataclass(frozen=True, slots=True)
class TurnTool:
    name: str
    description: str
    run: Callable[[Turn], str]
    args: type[BaseModel] = NoArgs


TURN_TOOLS: tuple[TurnTool, ...] = (
    TurnTool(
        "start_turn",
        "Open the turn and get the whole game back: the scene, who is here, what is hidden here,"
        " the threads, the notes from the rules and the recent play. Call it first every turn.",
        Turn.start_turn,
    ),
    TurnTool(
        "scene",
        "The same picture start_turn gives, for when you were compacted mid-turn.",
        Turn.picture,
    ),
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


def narration_refusal(view: NarratorView, written: Narration) -> str | None:
    if not written.lines:
        return "write the narration lines: an empty answer shows the player nothing."
    return speakers_refusal(view, written.lines)


def close_segment(
    engine: AnyEngine,
    view: NarratorView,
    draft: AnyGame,
    prompt: str,
    lines: tuple[Line, ...],
    facts: tuple[Fact, ...],
) -> AnyGame:
    notes = engine.record(draft, prompt, _spoken(view, lines), facts)
    draft.notes = (*draft.notes, *notes)
    draft.turn += 1
    return draft.committed()


def consume_answer(turn: Turn, player_input: str | Answer) -> tuple[str, str]:
    """The PLAYER ACTION and what a closed answer resolved."""
    engine, draft = turn.engine, turn.draft
    chosen = player_input.option_id if isinstance(player_input, Answer) else None
    if (ended := engine.over(draft)) is not None:
        raise ValueError(f"{ended} The only way on is to restart.")
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
    if turn.draft.pending is not None:
        traces += f"\n- {RULES_WAIT}"
    section = f"asked: {consumed.prompt}\nthe player chose: {option.label}\n{traces}"
    return option.label, section


def _spoken(view: NarratorView, lines: Sequence[Line]) -> tuple[SpokenLine, ...]:
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


def _apply(turn: Turn, play: Play[AnyGame]) -> tuple[Fact, ...]:
    """One execution against a candidate; a refused call leaves the draft and the dice alone."""
    candidate, dice = turn.draft.draft(), deepcopy(turn.rng)
    try:
        landed = apply_to_draft(turn.engine.validate, turn.engine.known, candidate, play, dice)
        committed = candidate.committed()
    except ValidationError as broken:
        raise ValueError(
            f"the state this leaves is invalid: {broken.errors()[0]['msg']}"
        ) from broken
    turn.draft = committed
    turn.rng.setstate(dice.getstate())
    turn.facts.extend(landed)
    if turn.on_fact is not None:
        for fact in landed:
            turn.on_fact(fact)
    return landed
