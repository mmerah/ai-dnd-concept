from pydantic_ai import ModelRetry, RunContext

from ..domain.models.consequences import References, flatten
from ..domain.models.direction import Direction
from ..domain.models.entities import ActorEntity, Entity
from .context import Scene


def _elsewhere(entity: Entity, scene: Scene) -> bool:
    return isinstance(entity, ActorEntity) and not scene.is_here(entity)


def validate_ids(ctx: RunContext[Scene], direction: Direction) -> Direction:
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
