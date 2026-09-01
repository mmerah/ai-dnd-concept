from collections.abc import Iterator, Sequence
from typing import Self

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import (
    DEAD,
    CheckedEntityId,
    EntityId,
    Frozen,
    Mutable,
    Slug,
    require_unique,
)
from aidm.core.facts import Fact
from aidm.core.play import Exchange
from aidm.kits.entities import Entity, Kind, Thread, check_filing, labeled
from aidm.kits.entities import carried_by as _carried_by
from aidm.kits.entities import require as _require
from aidm.kits.entities import require_kind as _require_kind
from aidm.kits.entities import reveal as _reveal


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
        check_filing(self.cast, self.threads)
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
        check_filing(self.cast, self.threads)
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
        return _require(self.cast, entity_id)

    def require_kind(self, entity_id: EntityId, kind: Kind) -> Entity[S]:
        return _require_kind(self.cast, entity_id, kind)

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
        return tuple(
            one if one.where else one.model_copy(update={"where": run.scene.title})
            for run in self.runs
            for one in run.exchanges
        )

    def here(self) -> Iterator[Entity[S]]:
        return (self.require(one) for one in self.run.present)

    def carried_by(self, holder_id: EntityId) -> Iterator[Entity[S]]:
        return _carried_by(self.cast, holder_id)

    def label(self, entity: Entity[S]) -> str:
        return labeled(entity, self.player_id)

    def reveal(self, entity: Entity[S]) -> list[Fact]:
        return _reveal(entity, self.player_id)

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
