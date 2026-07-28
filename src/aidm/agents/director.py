"""DIRECTOR — owns world direction and the turn's mechanics."""

from collections.abc import Sequence

from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.messages import ModelMessage

from ..domain.models import (
    CONSEQUENCE_TYPES,
    PLAYER_ID,
    ActorEntity,
    Attack,
    Consequence,
    Direction,
    Entity,
    GiveItem,
    References,
    flatten,
)
from .context import Scene
from .llm import build_agent
from .prompts.director import TEMPLATE


def consequence_menu(types: Sequence[type[Consequence]]) -> str:
    """Consequence reference assembled from each class's own docstring, `GUIDANCE`
    and field descriptions — so adding a consequence updates the prompt with no edit here."""
    lines: list[str] = []
    for consequence in types:
        action = consequence.model_fields["action"].default
        if not isinstance(action, str):  # a discriminator that is not a literal string is a bug
            raise TypeError(f"{consequence.__name__} has no literal action default")
        fields = "\n".join(
            f"  - `{name}`: {field.description}"
            for name, field in consequence.model_fields.items()
            if name != "action" and field.description
        )
        lines.append(f"### `{action}` — {consequence.__doc__}\n{consequence.GUIDANCE}\n{fields}")
    return "\n\n".join(lines)


INSTRUCTIONS = TEMPLATE.replace("{consequences}", consequence_menu(CONSEQUENCE_TYPES))


def _attacks_itself(attack: Attack) -> bool:
    return (attack.attacker_id or PLAYER_ID) == (attack.target_id or PLAYER_ID)


def _elsewhere(entity: Entity, scene: Scene) -> bool:
    """Only actors stand anywhere, and `present` marks actor fields alone — anything else has
    already failed the kind check."""
    return isinstance(entity, ActorEntity) and not scene.is_here(entity)


def _validate_ids(ctx: RunContext[Scene], direction: Direction) -> Direction:
    """Every id the Director chose must exist in the turn's canon, as the right kind, and stand
    where the field says it must; a speaker must also be one the player already knows. All faults
    are retries, not errors: the model can pick again from what it was shown."""
    refs = direction.canon_refs()
    if direction.speaker_id is not None:
        # A speaker is addressed, so the same rule as any acted-on actor: here, and known below.
        refs.append((direction.speaker_id, References("actor", present=True)))
    scene = ctx.deps
    canon = scene.canon

    # The player is an actor in canon now, so naming them where someone else is meant passes the
    # kind check below. Caught here as a retry rather than a dropped turn in the resolver.
    if direction.speaker_id == PLAYER_ID:
        raise ModelRetry("speaker_id must be an actor the player addresses, never the player")
    planned = flatten(direction.mechanics)  # branches included: a nested give is still a give
    if any(isinstance(c, GiveItem) and c.actor_id == PLAYER_ID for c in planned):
        raise ModelRetry("give_item must name another actor: the player already holds the item")
    # Both of an attack's ids default to the player, so naming one of them is what says "not you".
    if any(isinstance(c, Attack) and _attacks_itself(c) for c in planned):
        raise ModelRetry("attack must name at most one of attacker_id and target_id: they differ")

    if missing := sorted({i for i, _ in refs if i not in canon}):
        raise ModelRetry(f"unknown entity id(s): {missing}. Use only ids you were shown.")
    if mismatched := sorted(
        f"{i} is a {canon[i].kind}, not a {need.kind}"
        for i, need in refs
        if need.kind is not None and canon[i].kind != need.kind
    ):
        raise ModelRetry(f"wrong kind of entity: {'; '.join(mismatched)}.")
    # Acting on someone off-screen would narrate what the player never saw. A retry here, because
    # the resolver's own guard would cost the player the whole turn.
    if absent := sorted({i for i, need in refs if need.present and _elsewhere(canon[i], scene)}):
        raise ModelRetry(f"not here with the player: {absent}. Move them here first, or act here.")
    # A speaker the player has not met would put words in a stranger's mouth; catch it here rather
    # than letting views.speaker hard-fail the turn downstream.
    # `refs` carried the speaker through the `missing` check above, so it is in canon by here.
    if direction.speaker_id is not None and not canon[direction.speaker_id].known:
        raise ModelRetry(f"speaker {direction.speaker_id!r} exists but the player has not met them")
    return direction


agent = build_agent(
    "director",
    output_type=NativeOutput(Direction),
    instructions=INSTRUCTIONS,
    deps_type=Scene,
    output_validators=(_validate_ids,),
)


async def direct(
    prompt: str, scene: Scene, message_history: list[ModelMessage] | None = None
) -> Direction:
    """The `Scene` the prompt was built from is also what validates the ids it comes back with, so
    the Director cannot be told one thing and checked against another."""
    return (await agent().run(prompt, deps=scene, message_history=message_history)).output
