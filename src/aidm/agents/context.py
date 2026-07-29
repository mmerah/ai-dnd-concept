from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Self

from ..domain.models import (
    PLAYER_ID,
    Entity,
    EntityId,
    Event,
    Exchange,
    GameState,
    ItemEntity,
    LocationEntity,
)
from ..engine.ruleset import NarrativeRules


@dataclass(frozen=True, slots=True)
class Scene:
    """Keeps role visibility policy outside domain state."""

    state: GameState
    where: LocationEntity
    carried: tuple[ItemEntity, ...]
    here: tuple[Entity, ...]
    elsewhere: tuple[Entity, ...]
    unrevealed: tuple[Entity, ...]

    @classmethod
    def of(cls, state: GameState) -> Self:
        world = state.world
        where = world.require_kind(state.player.location_id, LocationEntity)
        shown = [e for e in world.entities.values() if e.id != PLAYER_ID]
        carried = tuple(
            e for e in shown if isinstance(e, ItemEntity) and e.container_id == PLAYER_ID
        )
        held = {e.id for e in carried}
        rest = [e for e in shown if e.id not in held and e.id != where.id]
        placed = {e.id: world.location_of(e) for e in rest}
        return cls(
            state=state,
            where=where,
            carried=carried,
            here=tuple(e for e in shown if e.known and placed.get(e.id) == where.id),
            elsewhere=tuple(
                e for e in shown if e.known and e.id in placed and placed[e.id] != where.id
            ),
            unrevealed=tuple(e for e in shown if not e.known),
        )

    @property
    def canon(self) -> Mapping[EntityId, Entity]:
        return self.state.world.entities

    @property
    def shown(self) -> list[Entity]:
        return [e for e in self.canon.values() if e.id != PLAYER_ID]

    def is_here(self, entity: Entity) -> bool:
        return self.state.world.location_of(entity) == self.where.id


@dataclass(frozen=True, slots=True)
class TurnContext:
    state: GameState
    prompt: str
    rules: NarrativeRules
    events: Sequence[Event] = ()
    narration: str = ""
    recent: Sequence[Exchange] = ()

    @property
    def scene(self) -> Scene:
        """Recompute because pipeline stages replace state."""
        return Scene.of(self.state)
