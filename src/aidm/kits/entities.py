from collections.abc import Iterator
from typing import Literal, Protocol, Self

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Mutable, Slug, Trait, require_unique
from aidm.core.facts import DiceEvent, Fact

Kind = Literal["actor", "item", "prop", "place"]
ThreadStatus = Literal["active", "resolved", "dormant"]


class Entity[S: BaseModel](Mutable):
    """Someone or something the world holds, with an engine-owned sheet."""

    id: CheckedEntityId
    kind: Kind
    name: str
    brief: str
    description: str = ""
    known: bool = False
    traits: list[Trait] = Field(default_factory=list)
    sheet: S | None = None
    carried_by: EntityId | None = None

    def trait(self, trait_id: str) -> Trait | None:
        return next((held for held in self.traits if held.id == trait_id), None)

    @model_validator(mode="after")
    def _traits_are_unambiguous(self) -> Self:
        require_unique(f"trait ids on {self.id!r}", (held.id for held in self.traits))
        return self


class Thread(Mutable):
    """A storyline the world tracks; the note is public, and the player reads it."""

    id: Slug
    title: str
    status: ThreadStatus = "active"
    note: str = ""


class World[S: BaseModel](Protocol):
    """What both kits give a shared verb: the cast, the party, and the player's reach into them."""

    cast: dict[EntityId, Entity[S]]
    threads: dict[Slug, Thread]
    companions: list[EntityId]
    player_id: EntityId

    def require(self, entity_id: EntityId) -> Entity[S]: ...

    def require_kind(self, entity_id: EntityId, kind: Kind) -> Entity[S]: ...

    def require_actor_here(self, actor_id: EntityId) -> Entity[S]: ...

    def here(self) -> Iterator[Entity[S]]: ...

    def label(self, entity: Entity[S]) -> str: ...

    def reveal(self, entity: Entity[S]) -> list[Fact]: ...


def labeled[S: BaseModel](entity: Entity[S], player_id: EntityId) -> str:
    """A trace names an entity by kind, name, and exact id, so the model can reuse the id."""
    word = "player" if entity.id == player_id else _kind_word(entity.kind)
    return f"the {word} {entity.name}[{entity.id}]"


def entity_fact[S: BaseModel](
    entity: Entity[S],
    kind: str,
    trace: str,
    *,
    narrate: bool = True,
    card: str = "",
    dice: tuple[DiceEvent, ...] = (),
) -> Fact:
    """An entity the player has not learned of narrates nothing, so no unknown name leaks."""
    return Fact(
        kind=kind,
        trace=trace,
        told=narrate and entity.known,
        entity_id=entity.id,
        card=card,
        dice=dice,
    )


def require[S: BaseModel](cast: dict[EntityId, Entity[S]], entity_id: EntityId) -> Entity[S]:
    one = cast.get(entity_id)
    if one is None:
        raise ValueError(f"unknown id {entity_id!r}. Use only ids you were shown.")
    return one


def require_kind[S: BaseModel](
    cast: dict[EntityId, Entity[S]], entity_id: EntityId, kind: Kind
) -> Entity[S]:
    one = require(cast, entity_id)
    if one.kind != kind:
        raise ValueError(
            f"{entity_id!r} is a {one.kind}, not a {kind}. "
            "Use an id of the kind this field asks for."
        )
    return one


def carried_by[S: BaseModel](
    cast: dict[EntityId, Entity[S]], holder_id: EntityId
) -> Iterator[Entity[S]]:
    return (one for one in cast.values() if one.carried_by == holder_id)


def reveal[S: BaseModel](entity: Entity[S], player_id: EntityId) -> list[Fact]:
    """Leave cards to the containing action or the standalone reveal arm."""
    if entity.known:
        return []
    entity.known = True
    return [entity_fact(entity, "entity_discovered", f"learned of {labeled(entity, player_id)}")]


def check_filing[S: BaseModel](
    cast: dict[EntityId, Entity[S]], threads: dict[Slug, Thread]
) -> None:
    for key, one in cast.items():
        if key != one.id:
            raise ValueError(f"entity {one.id!r} is filed under {key!r}")
        if one.carried_by is not None and one.carried_by not in cast:
            raise ValueError(f"{one.id!r} is carried by {one.carried_by!r}, who is not in the cast")
    for key, thread in threads.items():
        if key != thread.id:
            raise ValueError(f"thread {thread.id!r} is filed under {key!r}")


def entity_known[S: BaseModel](world: World[S], entity_id: EntityId) -> bool | None:
    entity = world.cast.get(entity_id)
    return None if entity is None else entity.known


def _kind_word(kind: Kind) -> str:
    """Prompts and traces say 'npc', because 'actor' reads as the player too."""
    return "npc" if kind == "actor" else kind
