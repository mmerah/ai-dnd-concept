from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from random import Random
from typing import Literal, Self

from pydantic import JsonValue

from aidm.engines.core import Engine
from aidm.kernel.views import NarratorView
from aidm.kits.scenes.boundary import SCENE_SETTLED, SPENT_NOTE, scene_spent
from aidm.state.facts import NOTHING, Fact, cards, traced
from aidm.state.model import Game, draft_refusal
from aidm.state.play import Answer, Line, SpokenLine
from aidm.state.tools import Play, apply_to_draft

from . import context

RULES_WAIT = "the rules now wait on the player's decision"

type TurnStep = Literal["master", "narrator", "worldsmith"]


@dataclass(slots=True, kw_only=True)
class Turn:
    """One player input to the next hand-back; the draft is the only state that moves."""

    engine: Engine
    draft: Game
    rng: Random
    on_fact: Callable[[Fact], None] | None = None
    facts: list[Fact] = field(default_factory=list)
    # The game master has called `start_turn`; nothing may change the world before it does.
    started: bool = False
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
        on_fact: Callable[[Fact], None] | None = None,
    ) -> Self:
        turn = cls(engine=engine, draft=state.draft(), rng=rng, on_fact=on_fact)
        turn.prompt, turn.resumed = consume_answer(turn, player_input)
        turn.notes = turn.draft.take_notes()
        turn.suspended_at_start = turn.draft.pending is not None
        return turn

    def landed(self, facts: tuple[Fact, ...]) -> None:
        self.facts.extend(facts)
        self.draft.turn_facts = cards(tuple(self.facts))
        if self.on_fact is not None:
            for fact in facts:
                self.on_fact(fact)

    def offer_the_way_on(self) -> None:
        """An offer, not a decision: the player may take it or keep playing here, so this must
        not block the turn the way a pending decision does."""
        if self.draft.world.settled:
            raise ValueError("this scene is already settled; the player has the way on")
        self.draft.world.settled = True
        # Told, so the narrator closes the scene and asks: a silent ending is no ending.
        self.landed((SCENE_SETTLED,))

    def picture(self, recent: int) -> str:
        draft = self.draft
        return context.render_picture(
            self.engine.views(draft).master.sections,
            draft,
            self.prompt,
            resumed=self.resumed,
            notes=(*self.notes, *draft.notes),
            recent=recent,
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
                "Stop here and exit; the player's answer opens the next turn."
            )
        return self.apply(lambda draft, rng: found.call(draft, raw, rng))

    def apply(self, play: Play) -> str:
        """What the call changed, as the game master reads it back."""
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
    draft.record(draft.world.current.title, prompt, spoken(view, lines), facts)
    draft.turn += 1
    # Directive text at the decision point is what fixed trigger reliability when it was measured.
    # Not once the master has settled the scene, and never on the turn one opened: that note would
    # be about the scene the player has just left.
    if draft.world.settled or draft.world.opened_at >= draft.turn - 1:
        return draft.committed()
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
