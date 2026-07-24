"""What each role is allowed to see. The CONTEXT table below is the whole policy — the source of
truth for what enters every role's prompt."""

from ..domain.models import Direction, GrowthRequest, Role
from .blocks import (
    CHARACTER,
    DIRECTOR_PLAN,
    DIRECTOR_TONE,
    ENTITY_CATALOGUE,
    GROWTH_REQUEST,
    KNOWN_ENTITIES,
    NARRATION,
    PLAYER_PROMPT,
    PREMISE,
    RECENT_PLAY,
    SPEAKER,
    UNREVEALED_CANON,
    WHAT_HAPPENED,
)
from .context import Block, DirectionBlock, RequestBlock, RolePolicy, TurnContext

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
