"""What each role is allowed to see. The CONTEXT table at the bottom is the whole policy."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..domain.events import Event, render
from ..domain.models import (
    Direction,
    GameState,
    GrowthRequest,
    Role,
    hidden,
    known,
)
from . import views


@dataclass(frozen=True, slots=True)
class TurnContext:
    """Everything any role could need. Fields fill in as the pipeline advances, hence the None."""

    state: GameState
    prompt: str
    direction: Direction | None = None
    events: Sequence[Event] = ()
    narration: str = ""
    request: GrowthRequest | None = None


def _required[T](value: T | None, block: str) -> T:
    if value is None:
        raise ValueError(f"context block {block!r} was rendered before its data existed")
    return value


Block = tuple[str, Callable[[TurnContext], str]]

PREMISE: Block = ("SCENARIO", lambda c: f"{c.state.scenario.title}\n{c.state.scenario.premise}")
CHARACTER: Block = ("CHARACTER", lambda c: views.character(c.state))
KNOWN_ENTITIES: Block = ("KNOWN TO THE PLAYER", lambda c: views.briefs(known(c.state.scenario)))
UNREVEALED_CANON_WITH_IDS: Block = (
    "EXISTS BUT THE PLAYER DOES NOT KNOW IT YET",
    lambda c: views.briefs_with_ids(hidden(c.state.scenario)),
)
UNREVEALED_CANON: Block = (
    "EXISTS BUT THE PLAYER DOES NOT KNOW IT YET — reveal only what you are told to",
    lambda c: views.briefs(hidden(c.state.scenario)),
)
ENTITY_CATALOGUE: Block = (
    "EVERYTHING THAT EXISTS",
    lambda c: views.briefs(c.state.scenario.entities),
)
RECENT_PLAY: Block = ("RECENT PLAY", lambda c: views.history(c.state))


def _guidance(c: TurnContext) -> str:
    return _required(c.direction, "director guidance").guidance


# The same text, labelled for its reader: the Actor executes it, the Narrator only interprets by it.
DIRECTOR_GUIDANCE: Block = ("THE DIRECTOR TELLS YOU", _guidance)
DIRECTOR_PLAN: Block = ("THE DIRECTOR'S PLAN — what was meant, not what happened", _guidance)
DIRECTOR_TONE: Block = (
    "THE DIRECTOR ASKS FOR THIS TONE",
    lambda c: _required(c.direction, "DIRECTOR_TONE").tone,
)
SPEAKER: Block = (
    "SPEAKER",
    lambda c: views.speaker(c.state, _required(c.direction, "SPEAKER")),
)
WHAT_HAPPENED: Block = ("WHAT HAPPENED", lambda c: render(c.events))
NARRATION: Block = ("NARRATION", lambda c: c.narration)
GROWTH_REQUEST: Block = ("CREATE", lambda c: views.request(_required(c.request, "GROWTH_REQUEST")))
PLAYER_PROMPT: Block = ("PLAYER", lambda c: c.prompt)

# The entire context policy of the application. Read a row to know what a role can and cannot see.
# Only one omission is a rule rather than a judgement: the Narrator, alone among the roles, writes
# text the player reads, so unrevealed canon never enters its context.
CONTEXT: dict[Role, tuple[Block, ...]] = {
    "director": (
        PREMISE,
        CHARACTER,
        KNOWN_ENTITIES,
        UNREVEALED_CANON_WITH_IDS,
        RECENT_PLAY,
        PLAYER_PROMPT,
    ),
    "actor": (
        PREMISE,
        CHARACTER,
        KNOWN_ENTITIES,
        UNREVEALED_CANON,
        RECENT_PLAY,
        DIRECTOR_GUIDANCE,
        PLAYER_PROMPT,
    ),
    "narrator": (
        PREMISE,
        CHARACTER,
        KNOWN_ENTITIES,
        RECENT_PLAY,
        DIRECTOR_PLAN,  # before WHAT HAPPENED, so the truth of the turn reads last
        DIRECTOR_TONE,
        SPEAKER,
        WHAT_HAPPENED,
        PLAYER_PROMPT,
    ),
    "maintainer": (
        PREMISE,
        ENTITY_CATALOGUE,
        RECENT_PLAY,
        PLAYER_PROMPT,
        WHAT_HAPPENED,
        NARRATION,
    ),
    "creator": (
        PREMISE,
        ENTITY_CATALOGUE,
        RECENT_PLAY,
        NARRATION,
        GROWTH_REQUEST,
    ),
}


def prompt_for(role: Role, context: TurnContext) -> str:
    return "\n\n".join(f"{label}:\n{block(context)}" for label, block in CONTEXT[role])
