from collections.abc import Mapping, Sequence

from pydantic import Field, JsonValue

from aidm.state.entities import PLAYER_ID, Entity, Frozen, kind_word

NOTHING_MECHANICAL = "- (nothing mechanical happened)"


class Chip(Frozen):
    """A small player-facing card a fact earns, phrased where its own values were in scope."""

    title: str
    icon: str = "casino"


class Fact(Frozen):
    """One thing that occurred, rendered where its values were in scope."""

    kind: str
    trace: str
    narrator: str | None = None
    # The structured values behind the prose, so a test or a richer trace reads them untyped.
    data: dict[str, JsonValue] = Field(default_factory=dict)
    chip: Chip | None = None


def labeled(entity: Entity) -> str:
    """A trace names an entity by kind, name, and exact id, so the Director can reuse the id."""
    word = "player" if entity.id == PLAYER_ID else kind_word(entity.kind)
    return f"the {word} {entity.name}[{entity.id}]"


def entity_fact(
    entity: Entity,
    kind: str,
    trace: str,
    data: Mapping[str, JsonValue],
    *,
    narrate: bool = True,
    chip: Chip | None = None,
) -> Fact:
    """An entity the player has not learned of narrates nothing, so no unknown name leaks."""
    return Fact(
        kind=kind,
        trace=trace,
        narrator=trace if narrate and entity.known else None,
        data={"entity_id": entity.id, **data},
        chip=chip,
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
