from dataclasses import dataclass
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.domain.aggregate import EngineAggregate
from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.entities import ActorEntity, ItemEntity
from aidm.utils.models import Mutable

from .content.records.base import ContentRef
from .domain.models.progression import Decisions, Origin, Progression
from .domain.models.stats import StatBlock
from .utils.models import Attributes, Frozen

type Dnd5eContentRef = ContentRef


class Dnd5eActorState(Mutable):
    stats: StatBlock
    progression: Progression | None = None
    ref: Dnd5eContentRef | None = None


class Dnd5eItemState(Mutable):
    ref: Dnd5eContentRef | None = None


@dataclass(frozen=True, slots=True)
class Dnd5eActor:
    """Joins core identity and placement with 5e mechanics so a rule reads one object."""

    entity: ActorEntity
    state: Dnd5eActorState

    @property
    def id(self) -> EntityId:
        return self.entity.id

    @property
    def name(self) -> str:
        return self.entity.name

    @property
    def known(self) -> bool:
        return self.entity.known

    @property
    def location_id(self) -> EntityId:
        return self.entity.location_id

    @property
    def stats(self) -> StatBlock:
        return self.state.stats

    @property
    def progression(self) -> Progression | None:
        return self.state.progression

    @property
    def ref(self) -> Dnd5eContentRef | None:
        return self.state.ref


@dataclass(frozen=True, slots=True)
class Dnd5eItem:
    entity: ItemEntity
    state: Dnd5eItemState

    @property
    def id(self) -> EntityId:
        return self.entity.id

    @property
    def name(self) -> str:
        return self.entity.name

    @property
    def container_id(self) -> EntityId:
        return self.entity.container_id

    @property
    def ref(self) -> Dnd5eContentRef | None:
        return self.state.ref


class Dnd5eState(EngineAggregate[Dnd5eActorState, Dnd5eItemState]):
    engine: Literal["dnd5e"] = "dnd5e"

    @model_validator(mode="after")
    def _only_the_player_advances(self) -> Self:
        """`LeveledUp` names no target, so an NPC carrying progression would be ambiguous."""
        levelled = sorted(
            actor_id
            for actor_id, actor in self.actors.items()
            if actor.progression is not None and actor_id != PLAYER_ID
        )
        if levelled:
            raise ValueError(f"only the player may have progression: {levelled}")
        return self


class Dnd5eCharacterData(Frozen):
    engine: Literal["dnd5e"] = "dnd5e"
    origin: Origin
    starting_attributes: Attributes = Attributes()
    decisions: Decisions = Field(default_factory=dict)


class Dnd5eActorDefinition(Frozen):
    engine: Literal["dnd5e"] = "dnd5e"
    ref: Dnd5eContentRef | None = None
    stats: StatBlock | None = None


class Dnd5eItemDefinition(Frozen):
    engine: Literal["dnd5e"] = "dnd5e"
    ref: Dnd5eContentRef | None = None
