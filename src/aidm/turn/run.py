from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from random import Random
from typing import Literal, Self

from pydantic import JsonValue, ValidationError

from aidm.core.facts import NOTHING, Fact, cards, traced
from aidm.core.model import AnyGame
from aidm.core.play import Answer, Exchange, Line, Narration, SpokenLine
from aidm.core.tools import Play, apply_to_draft
from aidm.core.views import NarratorView
from aidm.engines.seam import AnyEngine
from aidm.turn.context import ANSWERED_BY_OPTION, render_master

RULES_WAIT = "the rules now wait on the player's decision"
NO_TURN = "no turn is open. The player starts one from the page; wait to be spawned again."
GAME_OVER = "The game is over; the player restarts from the page."

type TurnStep = Literal["master", "narrator", "worldsmith"]


@dataclass(slots=True, kw_only=True)
class Turn:
    """The transaction: one player input applied to a draft. The session owns the lifecycle."""

    engine: AnyEngine
    draft: AnyGame
    rng: Random
    facts: list[Fact] = field(default_factory=list)
    prompt: str = ""
    # What the master reads as PLAYER ACTION: the prompt, or the marker for a chosen option.
    action: str = ""
    notes: tuple[str, ...] = ()

    @classmethod
    def begin(
        cls,
        engine: AnyEngine,
        state: AnyGame,
        player_input: str | Answer,
        rng: Random,
    ) -> Self:
        turn = cls(engine=engine, draft=state.draft(), rng=rng)
        turn.prompt, turn.action = consume_answer(turn, player_input)
        # Notes are read once; a note a tool writes after this steers the next turn.
        turn.notes, turn.draft.notes = turn.draft.notes, ()
        return turn

    def picture(self) -> str:
        return render_master(
            self.engine.instructions,
            self.engine.master_sections(self.draft),
            self.draft,
            self.engine.scenes(self.draft),
            self.action,
            notes=(*self.notes, *self.draft.notes),
        )

    def call(self, name: str, raw: Mapping[str, JsonValue]) -> str:
        """The one gate: every published tool is refused, answered or applied here."""
        if (ended := self.engine.over(self.draft)) is not None:
            raise ValueError(f"{ended} {GAME_OVER}")
        found = next((one for one in self.engine.tools if one.name == name), None)
        if found is None:
            raise ValueError(f"{name!r} is not a tool of the {self.engine.id!r} engine.")
        pending = self.draft.pending
        if pending is not None:
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
    exchange = Exchange(
        prompt=prompt,
        lines=_spoken(view, lines),
        facts=cards(facts),
        decision="" if draft.pending is None else draft.pending.prompt,
    )
    engine.record(draft, exchange)
    draft.turn += 1
    return draft.committed()


def consume_answer(turn: Turn, player_input: str | Answer) -> tuple[str, str]:
    """The PLAYER ACTION and what the master reads as it."""
    engine, draft = turn.engine, turn.draft
    chosen = player_input.option_id if isinstance(player_input, Answer) else None
    if (ended := engine.over(draft)) is not None:
        raise ValueError(f"{ended} The only way on is to restart.")
    # Any input consumes the decision, a revision included: it never survives its own answer.
    consumed, draft.pending = draft.pending, None
    if consumed is not None and not consumed.allows_text and chosen is None:
        raise ValueError(f"the {consumed.kind!r} decision takes one of its options, not words")
    if isinstance(player_input, str):
        return player_input, player_input
    if chosen is None:
        if consumed is not None:
            draft.notes = (
                *draft.notes,
                f'The rules paused play to ask the player: "{consumed.prompt}" '
                "The PLAYER ACTION is their answer.",
            )
        return player_input.text, player_input.text
    if consumed is None:
        raise ValueError(f"no decision is open, so option {chosen!r} answers nothing")
    option = next((one for one in consumed.options if one.id == chosen), None)
    if option is None:
        raise ValueError(f"the {consumed.kind!r} decision offers no option {chosen!r}")
    # A refusal raises: the engine enumerated the option, so it is never model error.
    landed = _apply(turn, lambda copy, dice: engine.answer(copy, option, dice))
    traces = traced(landed)
    # An answer that re-suspended has no tool answer to carry the wait, so the note says it.
    if turn.draft.pending is not None:
        traces += f"\n- {RULES_WAIT}"
    turn.draft.notes = (
        *turn.draft.notes,
        f'The rules paused play to ask the player: "{consumed.prompt}" They chose: {option.label}. '
        f"Already resolved:\n{traces}",
    )
    return option.label, ANSWERED_BY_OPTION


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
        landed = apply_to_draft(turn.engine.validate, candidate, play, dice)
        committed = candidate.committed()
    except ValidationError as broken:
        raise ValueError(
            f"the state this leaves is invalid: {broken.errors()[0]['msg']}"
        ) from broken
    turn.draft = committed
    turn.rng.setstate(dice.getstate())
    turn.facts.extend(landed)
    return landed
