from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from random import Random
from typing import Self

from pydantic import JsonValue

from aidm.core.creation import option_of
from aidm.core.entities import Refusal
from aidm.core.facts import NOTHING, Fact, traced
from aidm.core.model import AnyGame
from aidm.core.play import Answer, Line
from aidm.core.tools import Play
from aidm.engines.seam import COMMISSION, WORLDSMITH_WAIT, AnyEngine
from aidm.turn.context import render_master

RULES_WAIT = "the rules now wait on the player's decision"
ANSWERED_BY_OPTION = (
    "The player chose the option above and the rules have applied it. Develop what it caused; "
    "do not settle it again."
)
NO_TURN = "no turn is open. The player starts one from the page; wait to be spawned again."
GAME_OVER = "The game is over; the player restarts from the page."
# A bound on the re-spawn loop, not a design choice.
COMMISSIONS_PER_TURN = 1


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
    notes: list[str] = field(default_factory=list)
    commissioned: int = 0

    @classmethod
    def begin(cls, engine: AnyEngine, state: AnyGame, answer: Answer, rng: Random) -> Self:
        turn = cls(engine=engine, draft=state.draft(), rng=rng)
        turn._consume(answer)
        # Notes are read once; a note a tool writes after this steers the next turn.
        turn.notes, turn.draft.notes = turn.draft.notes, []
        return turn

    def _consume(self, answer: Answer) -> None:
        engine, draft = self.engine, self.draft
        if (ended := engine.over(draft)) is not None:
            raise Refusal(f"{ended} The only way on is to restart.")
        # Any input consumes the decision, a revision included: it never survives its own answer.
        consumed, draft.pending = draft.pending, None
        chosen = answer.option_id
        if consumed is not None and not consumed.allows_text and chosen is None:
            raise Refusal(f"the {consumed.kind!r} decision takes one of its options, not words")
        if chosen is None:
            if consumed is not None:
                draft.note(
                    f'The rules paused play to ask the player: "{consumed.prompt}" '
                    "The PLAYER ACTION is their answer."
                )
            self.prompt = self.action = answer.text
            return
        if consumed is None:
            raise Refusal(f"no decision is open, so option {chosen!r} answers nothing")
        option = option_of(consumed.options, chosen)
        if option is None:
            raise Refusal(f"the {consumed.kind!r} decision offers no option {chosen!r}")
        # A refusal raises: the engine enumerated the option, so it is never model error.
        facts = self._apply(lambda copy, dice: engine.answer(copy, option, dice))
        traces = traced(facts)
        # An answer that re-suspended has no tool answer to carry the wait, so the note says it.
        if self.draft.pending is not None:
            traces += f"\n- {RULES_WAIT}"
        self.draft.note(
            f'The rules paused play to ask the player: "{consumed.prompt}" '
            f"They chose: {option.label}. Already resolved:\n{traces}"
        )
        self.prompt, self.action = option.label, ANSWERED_BY_OPTION

    def picture(self) -> str:
        return render_master(
            self.engine.instructions,
            self.engine.master_sections(self.draft),
            self.draft,
            self.engine.scenes(self.draft),
            self.action,
            played=len(self.engine.history(self.draft)),
            notes=(*self.notes, *self.draft.notes),
        )

    def call(self, name: str, raw: Mapping[str, JsonValue]) -> str:
        """The one gate: every published tool is refused, answered or applied here."""
        if (ended := self.engine.over(self.draft)) is not None:
            raise Refusal(f"{ended} {GAME_OVER}")
        found = self.engine.tool(name)
        pending = self.draft.pending
        if pending is not None:
            # A plain answer, not a refusal: a retry prompt would tell the model to try again.
            return (
                f"the rules are waiting on the player: {pending.prompt}\n"
                "Stop here and exit; the player's answer opens the next turn."
            )
        if self.draft.wanted() is not None:
            return WORLDSMITH_WAIT
        commissioning = name == COMMISSION
        if commissioning and self.commissioned >= COMMISSIONS_PER_TURN:
            raise Refusal("one commission per turn: play on with what you have")
        answer = self.apply(lambda draft, rng: found.call(draft, raw, rng))
        if commissioning:
            self.commissioned += 1
        return answer

    def apply(self, play: Play[AnyGame]) -> str:
        """What the call changed, as the game master reads it back."""
        already_pending = len(self.draft.notes)
        decided_before = self.draft.pending
        wanted_before = self.draft.wanted()
        facts = self._apply(play)
        lines = [f"- {fact.trace}" for fact in facts]
        lines.extend(f"- {note}" for note in self.draft.notes[already_pending:])
        if decided_before is None and self.draft.pending is not None:
            lines.append(f"- {RULES_WAIT}")
        if wanted_before is None and self.draft.wanted() is not None:
            lines.append(f"- {WORLDSMITH_WAIT}")
        return "\n".join(lines) or NOTHING

    def finish(self, lines: tuple[Line, ...]) -> AnyGame:
        return self.engine.close(self.draft, self.prompt, lines, tuple(self.facts))

    def _apply(self, play: Play[AnyGame]) -> tuple[Fact, ...]:
        """One execution against a candidate; a refused call leaves the draft and the dice alone."""
        candidate, dice = self.draft.draft(), deepcopy(self.rng)
        before = candidate.pending
        facts = play(candidate, dice)
        if before is not None and candidate.pending is not before:
            raise Refusal("the rules already wait on a decision; they take one at a time")
        self.draft = self.engine.commit(candidate)
        self.rng.setstate(dice.getstate())
        self.facts.extend(facts)
        return facts
