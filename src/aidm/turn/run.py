from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from typing import Self

from pydantic import JsonValue

from aidm.core.creation import option_of
from aidm.core.entities import Refusal
from aidm.core.facts import NOTHING, Fact, traced
from aidm.core.io import read_prompt
from aidm.core.model import AnyGame
from aidm.core.play import Answer, SpokenLine
from aidm.core.prompt import Pairs, lines_of, render_history, sections
from aidm.core.tools import MasterTool, Play
from aidm.engines.seam import AnyEngine

MASTER_PROMPT = Path(__file__).parent / "prompts" / "master.md"
PAUSED_TO_ASK = 'The rules paused play to ask the player: "{prompt}" '
RULES_WAIT = "the rules now wait on the player's decision"
REQUEST_WAIT = "the worldsmith writes what you asked for once this turn ends. Stop here and exit."
ANSWERED_BY_OPTION = (
    "The player chose the option above and the rules have applied it. Develop what it caused; "
    "do not settle it again."
)
NO_TURN = "no turn is open. The player starts one from the page. Wait to be spawned again."
GAME_OVER = "The game is over. The player restarts from the page."


@dataclass(slots=True, kw_only=True)
class Turn:
    engine: AnyEngine
    draft: AnyGame
    rng: Random
    facts: list[Fact] = field(default_factory=list)
    words: str = ""
    # What the master reads as PLAYER ACTION: the words, or the marker for a chosen option.
    action: str = ""
    notes: list[str] = field(default_factory=list)

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
                    PAUSED_TO_ASK.format(prompt=consumed.prompt)
                    + "The PLAYER ACTION is their answer."
                )
            self.words = self.action = answer.text
            return
        if consumed is None:
            raise Refusal(f"no decision is open, so option {chosen!r} answers nothing")
        option = option_of(consumed.options, chosen)
        if option is None:
            raise Refusal(f"the {consumed.kind!r} decision offers no option {chosen!r}")
        # A refusal raises: the engine enumerated the option, so it is never model error.
        facts = self.apply(lambda copy, dice: engine.answer(copy, option, dice))
        traces = traced(facts)
        # An answer that re-suspended has no tool answer to carry the wait, so the note says it.
        if self.draft.pending is not None:
            traces += f"\n- {RULES_WAIT}"
        self.draft.note(
            PAUSED_TO_ASK.format(prompt=consumed.prompt)
            + f"They chose: {option.label}. Already resolved:\n{traces}"
        )
        self.words, self.action = option.label, ANSWERED_BY_OPTION

    def told(self) -> bool:
        return any(fact.told for fact in self.facts)

    def handed_over(self) -> bool:
        return self.draft.pending is not None or self.draft.generation is not None

    def narrates(self) -> bool:
        """A hand-over that moved no fiction gets no prose."""
        return self.told() or not self.handed_over()

    def picture(self) -> str:
        return render_master(
            self.engine.instructions,
            self.engine.master_sections(self.draft),
            self.draft,
            self.action,
            notes=self.notes,
        )

    def call(self, name: str, raw: JsonValue) -> str:
        """The one gate every published tool passes; returns what changed as the master reads it."""
        if (ended := self.engine.over(self.draft)) is not None:
            raise Refusal(f"{ended} {GAME_OVER}")
        found = self.engine.tools.get(name)
        if found is None:
            raise Refusal(f"{name!r} is not a tool of the {self.engine.id!r} engine.")
        pending = self.draft.pending
        if pending is not None:
            # A plain answer, not a refusal: a retry prompt would tell the model to try again.
            return (
                f"the rules are waiting on the player: {pending.prompt}\n"
                "Stop here and exit; the player's answer opens the next turn."
            )
        if self.draft.generation is not None:
            return REQUEST_WAIT
        notes_before = len(self.draft.notes)
        facts = self.apply(lambda draft, rng: found.call(draft, raw, rng))
        lines = [f"- {fact.trace}" for fact in facts]
        lines.extend(f"- {note}" for note in self.draft.notes[notes_before:])
        if self.draft.pending is not None:
            lines.append(f"- {RULES_WAIT}")
        return "\n".join(lines) or NOTHING

    def published_tools(self) -> tuple[MasterTool[AnyGame], ...]:
        return tuple(self.engine.tools.values())

    def finish(self, lines: tuple[SpokenLine, ...]) -> AnyGame:
        return self.engine.close(self.draft, lines, tuple(self.facts), words=self.words)

    def apply(self, play: Play[AnyGame]) -> tuple[Fact, ...]:
        """One execution against a candidate; a refused call leaves the draft and the dice alone."""
        candidate, dice = self.draft.draft(), deepcopy(self.rng)
        facts = play(candidate, dice)
        self.draft = self.engine.land(candidate)
        self.rng.setstate(dice.getstate())
        self.facts.extend(facts)
        return facts


def render_master(
    instructions: str,
    engine_sections: Pairs,
    state: AnyGame,
    action: str,
    *,
    notes: Sequence[str] = (),
) -> str:
    played = sum(len(chapter.exchanges) for chapter in state.log)
    return sections(
        (
            ("YOUR ROLE", read_prompt(MASTER_PROMPT)),
            ("THE RULES OF THIS GAME", instructions),
            ("SCENARIO", f"{state.scenario.title}\n{state.scenario.premise}"),
            ("THE SCOPE OF PLAY", state.scenario.scope),
            (f"RECENT PLAY (this is turn {played + 1})", render_history(state.log)),
            *engine_sections,
            ("NOTES FROM THE RULES", lines_of(f"- {note}" for note in notes)),
            ("PLAYER ACTION", action),
        )
    )
