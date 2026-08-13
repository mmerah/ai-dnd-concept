from collections.abc import Mapping, Sequence

from pydantic import Field, JsonValue

from .base import Entity, Frozen

CORE = "core"
NOTHING_MECHANICAL = "- (nothing mechanical happened)"


class Fact(Frozen):
    """One thing that occurred, rendered where its values were in scope."""

    source: str
    kind: str
    trace: str
    narrator: str | None = None
    # The structured values behind the prose, so a test or a richer trace reads them untyped.
    data: dict[str, JsonValue] = Field(default_factory=dict)


def explained(trace: str, why: str) -> str:
    return f"{trace} ({why})" if why else trace


def entity_fact(
    entity: Entity, kind: str, trace: str, data: Mapping[str, JsonValue], *, narrate: bool = True
) -> Fact:
    """An entity the player has not learned of narrates nothing, so no unknown name leaks."""
    return Fact(
        source=CORE,
        kind=kind,
        trace=trace,
        narrator=trace if narrate and entity.known else None,
        data={"entity_id": entity.id, **data},
    )


def explained_fact(
    entity: Entity,
    kind: str,
    trace: str,
    data: Mapping[str, JsonValue],
    why: str,
    *,
    narrate: bool = True,
) -> Fact:
    """The `why` is what the advancement panel shows the player before they confirm."""
    return entity_fact(entity, kind, explained(trace, why), data, narrate=narrate)


def narrator_evidence(facts: Sequence[Fact]) -> str:
    lines = [f"- {rendered}" for fact in facts if (rendered := fact.narrator) is not None]
    return "\n".join(lines) or NOTHING_MECHANICAL
