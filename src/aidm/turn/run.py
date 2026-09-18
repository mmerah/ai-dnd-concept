from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from typing import Protocol, Self

from pydantic import JsonValue

from aidm.core.creation import option_of
from aidm.core.entities import Refusal
from aidm.core.facts import NOTHING, Fact, traced
from aidm.core.io import read_cached_text
from aidm.core.model import AnyGame
from aidm.core.play import Answer, SpokenLine
from aidm.core.prompt import Sections, lines_of, render_history, sections
from aidm.core.tools import MasterTool
from aidm.engines.engine import AnyEngine

MASTER_ROLE = Path(__file__).parent / "prompts" / "master.md"
PAUSED_TO_ASK = 'The rules paused play to ask the player: "{prompt}" '
RULES_WAIT = "the rules now wait on the player's decision"
COMMISSION_WAIT = (
    "the worldsmith writes what you asked for once this turn ends. Stop here and exit."
)
ANSWERED_BY_OPTION = (
    "The player chose the option above and the rules have applied it. Develop what it caused; "
    "do not settle it again."
)
NO_TURN = "no turn is open. The player starts one from the page. Wait to be spawned again."
GAME_OVER = "The game is over. The player restarts from the page."
RESTART = "The only way on is to restart."


class Tools(Protocol):
    def published_tools(self) -> Sequence[MasterTool]: ...
    def call(self, name: str, raw: JsonValue) -> str: ...


@dataclass(slots=True, kw_only=True)
class Turn:
    engine: AnyEngine
    draft: AnyGame
    rng: Random
    facts: list[Fact] = field(default_factory=list)
    words: str = ""
    # What the master reads as PLAYER ACTION: the words, or the marker for a chosen option.
    player_action: str = ""
    notes: list[str] = field(default_factory=list)
    # Whether the master plays: an answer that re-suspended leaves every tool refused.
    played: bool = True

    @classmethod
    def begin(cls, engine: AnyEngine, state: AnyGame, answer: Answer, rng: Random) -> Self:
        turn = cls(engine=engine, draft=state.draft(), rng=deepcopy(rng))
        turn._consume(answer)
        turn.played = turn.draft.pending is None
        # Notes are read once; a note a tool writes after this steers the next turn.
        if turn.played:
            turn.notes, turn.draft.notes = turn.draft.notes, []
        return turn

    def _consume(self, answer: Answer) -> None:
        engine, draft = self.engine, self.draft
        if (ended := engine.ending(draft)) is not None:
            raise Refusal(f"{ended} {RESTART}")
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
            self.words = self.player_action = answer.text
            return
        if consumed is None:
            raise Refusal(f"no decision is open, so option {chosen!r} answers nothing")
        option = option_of(consumed.options, chosen)
        if option is None:
            raise Refusal(f"the {consumed.kind!r} decision offers no option {chosen!r}")
        # A refusal raises: the engine enumerated the option, so it is never model error.
        facts = self.apply(lambda copy, dice: engine.play_option(copy, option, dice))
        traces = traced(facts)
        # An answer that re-suspended has no tool answer to carry the wait, so the note says it.
        if self.draft.pending is not None:
            traces += f"\n- {RULES_WAIT}"
        self.draft.note(
            PAUSED_TO_ASK.format(prompt=consumed.prompt)
            + f"They chose: {option.name}. Already resolved:\n{traces}"
        )
        self.words, self.player_action = option.name, ANSWERED_BY_OPTION

    @property
    def narrates(self) -> bool:
        """A hand-over that moved no fiction gets no prose."""
        waiting = self.draft.pending is not None or self.draft.commission is not None
        return any(fact.told for fact in self.facts) or not waiting

    @property
    def landed(self) -> bool:
        return bool(self.facts) or self.draft.pending is not None

    def master_prompt(self) -> str:
        return render_master(
            self.engine.instructions,
            self.engine.master_sections(self.draft),
            self.draft,
            self.player_action,
            notes=self.notes,
        )

    def call(self, name: str, raw: JsonValue) -> str:
        """The one gate every published tool passes; returns what changed as the master reads it."""
        if (ended := self.engine.ending(self.draft)) is not None:
            raise Refusal(f"{ended} {GAME_OVER}")
        found = self.engine.require_tool(name)
        pending = self.draft.pending
        if pending is not None:
            # A plain answer, not a refusal: a retry prompt would tell the model to try again.
            return (
                f"the rules are waiting on the player: {pending.prompt}\n"
                "Stop here and exit; the player's answer opens the next turn."
            )
        if self.draft.commission is not None:
            return COMMISSION_WAIT
        notes_before = len(self.draft.notes)
        facts = self.apply(lambda draft, rng: found.call(draft, raw, rng))
        lines = [f"- {fact.trace}" for fact in facts]
        lines.extend(f"- {note}" for note in self.draft.notes[notes_before:])
        if self.draft.pending is not None:
            lines.append(f"- {RULES_WAIT}")
        return "\n".join(lines) or NOTHING

    def published_tools(self) -> tuple[MasterTool, ...]:
        return tuple(self.engine.tools.values())

    def finish(self, lines: tuple[SpokenLine, ...], *, enabled: bool) -> AnyGame:
        self.engine.tick(self.draft, counted=enabled and self.played and bool(self.facts))
        return self.engine.close(self.draft, lines, tuple(self.facts), words=self.words)

    def apply(self, play: Callable[[AnyGame, Random], tuple[Fact, ...]]) -> tuple[Fact, ...]:
        """One execution against a candidate; a refused call leaves the draft and the dice alone."""
        candidate, dice = self.draft.draft(), deepcopy(self.rng)
        facts = play(candidate, dice)
        self.draft = self.engine.accept(candidate)
        self.rng.setstate(dice.getstate())
        self.facts.extend(facts)
        return facts


def render_master(
    instructions: str,
    engine_sections: Sections,
    state: AnyGame,
    action: str,
    *,
    notes: Sequence[str] = (),
) -> str:
    played = sum(len(chapter.exchanges) for chapter in state.log)
    return sections(
        (
            ("YOUR ROLE", read_cached_text(MASTER_ROLE)),
            ("THE RULES OF THIS GAME", instructions),
            ("SCENARIO", f"{state.scenario.title}\n{state.scenario.premise}"),
            ("THE SCOPE OF PLAY", state.scenario.scope),
            (f"RECENT PLAY (this is turn {played + 1})", render_history(state.log)),
            *engine_sections,
            ("NOTES FROM THE RULES", lines_of(f"- {note}" for note in notes)),
            ("PLAYER ACTION", action),
        )
    )
