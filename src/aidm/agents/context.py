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
    """What is always present by the time any role renders. Per-stage payloads (`Direction`,
    `GrowthRequest`) are passed to `prompt_for` instead, so no renderer must None-guard."""

    state: GameState
    prompt: str
    events: Sequence[Event] = ()
    narration: str = ""


# Three block shapes: a plain block reads only the context; a direction/request block also takes
# its stage payload, non-optional — which is what keeps the payload types free of `| None`.
@dataclass(frozen=True, slots=True)
class Block:
    label: str
    render: Callable[[TurnContext], str]


@dataclass(frozen=True, slots=True)
class DirectionBlock:
    label: str
    render: Callable[[TurnContext, Direction], str]


@dataclass(frozen=True, slots=True)
class RequestBlock:
    label: str
    render: Callable[[TurnContext, GrowthRequest], str]


AnyBlock = Block | DirectionBlock | RequestBlock

PREMISE = Block("SCENARIO", lambda c: f"{c.state.scenario.title}\n{c.state.scenario.premise}")
CHARACTER = Block("CHARACTER", lambda c: views.character(c.state))
KNOWN_ENTITIES = Block("KNOWN TO THE PLAYER", lambda c: views.briefs(known(c.state.world.entities)))
UNREVEALED_CANON = Block(
    "EXISTS BUT THE PLAYER DOES NOT KNOW IT YET",
    lambda c: views.briefs(hidden(c.state.world.entities)),
)
ENTITY_CATALOGUE = Block("EVERYTHING THAT EXISTS", lambda c: views.briefs(c.state.world.entities))
RECENT_PLAY = Block("RECENT PLAY", lambda c: views.history(c.state))

DIRECTOR_PLAN = DirectionBlock(
    "THE DIRECTOR'S PLAN — what was meant, not what happened", lambda c, d: d.intent
)
DIRECTOR_TONE = DirectionBlock("THE DIRECTOR ASKS FOR THIS TONE", lambda c, d: d.tone)
SPEAKER = DirectionBlock("SPEAKER", lambda c, d: views.speaker(c.state, d))
WHAT_HAPPENED = Block("WHAT HAPPENED", lambda c: render(c.events))
NARRATION = Block("NARRATION", lambda c: c.narration)
GROWTH_REQUEST = RequestBlock("CREATE", lambda c, r: views.request(r))
PLAYER_PROMPT = Block("PLAYER", lambda c: c.prompt)


@dataclass(frozen=True, slots=True)
class RolePolicy:
    """A role's whole view: the blocks its prompt is built from, and whether it also receives play
    history as native messages (the Creator alone reads it as the RECENT_PLAY text instead)."""

    blocks: tuple[AnyBlock, ...]
    native_history: bool = False


# The entire context policy of the application. Read a row to know what a role can and cannot see.
# Only one omission is a rule rather than a judgement: the Narrator, alone among the roles, writes
# text the player reads, so unrevealed canon never enters its context.
CONTEXT: dict[Role, RolePolicy] = {
    "director": RolePolicy(
        (PREMISE, CHARACTER, KNOWN_ENTITIES, UNREVEALED_CANON, PLAYER_PROMPT),
        native_history=True,
    ),
    "narrator": RolePolicy(
        (
            PREMISE,
            CHARACTER,
            KNOWN_ENTITIES,
            DIRECTOR_PLAN,  # before WHAT HAPPENED, so the truth of the turn reads last
            DIRECTOR_TONE,
            SPEAKER,
            WHAT_HAPPENED,
            PLAYER_PROMPT,
        ),
        native_history=True,
    ),
    "maintainer": RolePolicy(
        (PREMISE, ENTITY_CATALOGUE, PLAYER_PROMPT, WHAT_HAPPENED, NARRATION),
        native_history=True,
    ),
    "creator": RolePolicy((PREMISE, ENTITY_CATALOGUE, RECENT_PLAY, NARRATION, GROWTH_REQUEST)),
}


def reads_history(role: Role) -> bool:
    return CONTEXT[role].native_history


def prompt_for(
    role: Role,
    context: TurnContext,
    *,
    direction: Direction | None = None,
    request: GrowthRequest | None = None,
) -> str:
    """A direction/request block appears only in a role whose stage has that payload, so the
    pipeline always supplies it; a missing one is a broken invariant."""
    lines: list[str] = []
    for block in CONTEXT[role].blocks:
        match block:
            case Block(label=label, render=render):
                body = render(context)
            case DirectionBlock(label=label, render=render):
                if direction is None:
                    raise ValueError(f"{label!r} rendered without a direction")
                body = render(context, direction)
            case RequestBlock(label=label, render=render):
                if request is None:
                    raise ValueError(f"{label!r} rendered without a request")
                body = render(context, request)
        lines.append(f"{label}:\n{body}")
    return "\n\n".join(lines)
