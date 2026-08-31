from collections.abc import Iterator, Sequence
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import (
    DEAD,
    CheckedEntityId,
    EntityId,
    Frozen,
    Mutable,
    Slug,
    Trait,
    require_unique,
)
from aidm.core.facts import DiceEvent, Fact
from aidm.core.play import Exchange

Kind = Literal["actor", "item", "prop"]
ThreadStatus = Literal["active", "resolved", "dormant"]


class Entity[S: BaseModel](Mutable):
    """Someone or something the story holds; it persists across scenes, the scene does not."""

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


class Scene(Frozen):
    # Names the art cache entry, so returning to a place reuses its picture.
    place: Slug
    title: str
    # Public: the player reads it; settling it ends the scene.
    question: str = Field(min_length=10)
    situation: str = Field(min_length=40)
    # What `question` does not say: never narrated, never in a view.
    secret: str = ""


class SceneRun(Mutable):
    scene: Scene
    present: list[CheckedEntityId] = Field(default_factory=list)
    hidden: list[CheckedEntityId] = Field(default_factory=list)
    exchanges: list[Exchange] = Field(default_factory=list)
    # The game master has called the question answered; the player may move on, or play on.
    settled: bool = False
    # Why the scene looks finished already, written by the rule that settled it.
    spent: str = ""


class Thread(Mutable):
    """A storyline the scenario tracks; the note is public, and the player reads it."""

    id: Slug
    title: str
    status: ThreadStatus = "active"
    note: str = ""


class SceneCanon[S: BaseModel](Mutable):
    """A scenario as authored: its opening scene and cast, with no player in it yet."""

    cast: dict[EntityId, Entity[S]] = Field(default_factory=dict)
    opening: Scene
    present: list[CheckedEntityId] = Field(default_factory=list)
    hidden: list[CheckedEntityId] = Field(default_factory=list)
    threads: dict[Slug, Thread] = Field(default_factory=dict)
    source: str = ""

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
        _check_filing(self.cast, self.threads)
        _check_named(self.present, self.hidden, self.cast)
        return self


class SceneState[S: BaseModel](Mutable):
    """The world as a sequence of scenes: the cast persists, the scene is what is happening."""

    cast: dict[EntityId, Entity[S]] = Field(default_factory=dict)
    runs: list[SceneRun] = Field(min_length=1)
    threads: dict[Slug, Thread] = Field(default_factory=dict)
    companions: list[EntityId] = Field(default_factory=list)
    player_id: EntityId
    source: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        _check_filing(self.cast, self.threads)
        _check_named(self.run.present, self.run.hidden, self.cast)
        if self.player_id not in self.cast:
            raise ValueError("the player is not in the cast")
        if not self.player.known:
            raise ValueError("the player is unknown to themselves")
        if self.player_id not in self.run.present:
            raise ValueError("the player is not in their own scene")
        if self.player_id in self.companions:
            raise ValueError("the player cannot travel with themselves")
        require_unique("companions", self.companions)
        for member_id in self.companions:
            if self.require(member_id).trait(DEAD) is not None:
                raise ValueError(f"{member_id!r} is dead and cannot travel with the player")
        return self

    def require(self, entity_id: EntityId) -> Entity[S]:
        one = self.cast.get(entity_id)
        if one is None:
            raise ValueError(f"unknown id {entity_id!r}. Use only ids you were shown.")
        return one

    def require_kind(self, entity_id: EntityId, kind: Kind) -> Entity[S]:
        one = self.require(entity_id)
        if one.kind != kind:
            raise ValueError(
                f"{entity_id!r} is a {one.kind}, not a {kind}. "
                "Use an id of the kind this field asks for."
            )
        return one

    @property
    def run(self) -> SceneRun:
        return self.runs[-1]

    @property
    def current(self) -> Scene:
        return self.run.scene

    @property
    def player(self) -> Entity[S]:
        return self.require(self.player_id)

    def exchanges(self) -> tuple[Exchange, ...]:
        return tuple(one for run in self.runs for one in run.exchanges)

    def here(self) -> Iterator[Entity[S]]:
        return (self.require(one) for one in self.run.present)

    def carried_by(self, holder_id: EntityId) -> Iterator[Entity[S]]:
        return (one for one in self.cast.values() if one.carried_by == holder_id)

    def label(self, entity: Entity[S]) -> str:
        return labeled(entity, self.player_id)

    def reveal(self, entity: Entity[S]) -> list[Fact]:
        """Leave cards to the containing action or the standalone reveal arm."""
        if entity.known:
            return []
        entity.known = True
        return [entity_fact(entity, "entity_discovered", f"learned of {self.label(entity)}")]

    def require_actor_here(self, actor_id: EntityId) -> Entity[S]:
        actor = self.require_kind(actor_id, "actor")
        if actor.trait(DEAD) is not None:
            raise ValueError(f"{actor.name} is dead; they take no further part.")
        if actor.id not in self.run.present:
            raise ValueError(
                f"{actor_id!r} is not here with the player. "
                "Bring them here first, or act on who is here."
            )
        return actor

    def last_seen(self, entity_id: EntityId) -> str:
        """Scan backwards for the scene that held them, so nothing the story dropped is lost."""
        for run in reversed(self.runs):
            if entity_id in (*run.present, *run.hidden):
                return run.scene.title
        return ""


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


def _kind_word(kind: Kind) -> str:
    """Prompts and traces say 'npc', because 'actor' reads as the player too."""
    return "npc" if kind == "actor" else kind


def _check_filing[S: BaseModel](
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


def _check_named[S: BaseModel](
    present: Sequence[EntityId], hidden: Sequence[EntityId], cast: dict[EntityId, Entity[S]]
) -> None:
    require_unique("ids in the scene", (*present, *hidden))
    for who in (*present, *hidden):
        if who not in cast:
            raise ValueError(f"scene names {who!r}, who is not in the cast")
    for who in hidden:
        if cast[who].known:
            raise ValueError(f"{who!r} is hidden here but the player has already met them")
