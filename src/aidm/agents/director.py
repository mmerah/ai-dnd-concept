from collections.abc import Sequence

from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.messages import ModelMessage

from ..domain.models import (
    CONSEQUENCE_TYPES,
    ActorEntity,
    Consequence,
    Direction,
    Entity,
    References,
    flatten,
)
from .context import Scene
from .llm import build_agent
from .prompts.director import TEMPLATE


def consequence_menu(types: Sequence[type[Consequence]]) -> str:
    """Build prompt guidance from structured action metadata."""
    lines: list[str] = []
    for consequence in types:
        action = consequence.model_fields["action"].default
        if not isinstance(action, str):
            raise TypeError(f"{consequence.__name__} has no literal action default")
        fields = "\n".join(
            f"  - `{name}`: {field.description}"
            for name, field in consequence.model_fields.items()
            if name != "action" and field.description
        )
        lines.append(f"### `{action}` — {consequence.__doc__}\n{consequence.GUIDANCE}\n{fields}")
    return "\n\n".join(lines)


INSTRUCTIONS = TEMPLATE.replace("{consequences}", consequence_menu(CONSEQUENCE_TYPES))


def _elsewhere(entity: Entity, scene: Scene) -> bool:
    return isinstance(entity, ActorEntity) and not scene.is_here(entity)


def _validate_ids(ctx: RunContext[Scene], direction: Direction) -> Direction:
    """Retry invalid IDs before resolution can drop the turn."""
    refs = direction.canon_refs()
    if direction.speaker_id is not None:
        refs.append((direction.speaker_id, References("actor", present=True)))
    scene = ctx.deps
    canon = scene.canon

    for fault in (direction.check(), *(c.check() for c in flatten(direction.mechanics))):
        if fault is not None:
            raise ModelRetry(fault)

    if missing := sorted({i for i, _ in refs if i not in canon}):
        raise ModelRetry(f"unknown entity id(s): {missing}. Use only ids you were shown.")
    if mismatched := sorted(
        f"{i} is a {canon[i].kind}, not a {need.kind}"
        for i, need in refs
        if need.kind is not None and canon[i].kind != need.kind
    ):
        raise ModelRetry(f"wrong kind of entity: {'; '.join(mismatched)}.")
    if absent := sorted({i for i, need in refs if need.present and _elsewhere(canon[i], scene)}):
        raise ModelRetry(f"not here with the player: {absent}. Move them here first, or act here.")
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
    return (await agent().run(prompt, deps=scene, message_history=message_history)).output
