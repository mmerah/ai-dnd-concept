from collections.abc import Mapping, Sequence

from pydantic import Field, JsonValue

from .base import Entity, Frozen

NOTHING_MECHANICAL = "- (nothing mechanical happened)"


class Fact(Frozen):
    """One thing that occurred, rendered where its values were in scope."""

    kind: str
    trace: str
    narrator: str | None = None
    # The structured values behind the prose, so a test or a richer trace reads them untyped.
    data: dict[str, JsonValue] = Field(default_factory=dict)


def entity_fact(
    entity: Entity, kind: str, trace: str, data: Mapping[str, JsonValue], *, narrate: bool = True
) -> Fact:
    """An entity the player has not learned of narrates nothing, so no unknown name leaks."""
    return Fact(
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
    rendered = f"{trace} ({why})" if why else trace
    return entity_fact(entity, kind, rendered, data, narrate=narrate)


def narrator_lines(facts: Sequence[Fact]) -> tuple[str, ...]:
    return tuple(told for fact in facts if (told := fact.narrator) is not None)


def narrator_evidence(facts: Sequence[Fact]) -> str:
    return "\n".join(f"- {told}" for told in narrator_lines(facts)) or NOTHING_MECHANICAL
