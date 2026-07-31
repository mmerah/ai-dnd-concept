from collections.abc import Callable, Iterable

from ..domain.base import PLAYER_ID, EntityId
from ..domain.entities import ActorEntity, Entity, ItemEntity, LocationEntity
from ..domain.state import GameState, WorldState
from ..utils.models import Frozen

type EntityRenderer = Callable[[Entity], str]


class BaseScene(Frozen):
    player: ActorEntity
    location: LocationEntity
    inventory: tuple[ItemEntity, ...]
    here: tuple[Entity, ...]
    known_elsewhere: tuple[Entity, ...]
    placements: dict[EntityId, str]

    def placement_of(self, entity: Entity) -> str:
        return self.placements[entity.id]


class SceneSnapshot(BaseScene):
    hidden: tuple[Entity, ...]
    canon: WorldState

    @classmethod
    def of(cls, state: GameState) -> "SceneSnapshot":
        world = state.world
        player = state.player
        location = world.require_kind(player.location_id, LocationEntity)
        shown = [entity for entity in world.entities.values() if entity.id != PLAYER_ID]
        inventory = world.carried_by(PLAYER_ID)
        carried_ids = {item.id for item in inventory}
        placed = [
            entity for entity in shown if entity.id not in carried_ids and entity.id != location.id
        ]
        locations = {entity.id: world.location_of(entity) for entity in placed}
        return cls(
            player=player,
            location=location,
            inventory=inventory,
            here=tuple(
                entity
                for entity in shown
                if entity.known and locations.get(entity.id) == location.id
            ),
            known_elsewhere=tuple(
                entity
                for entity in shown
                if entity.known and entity.id in locations and locations[entity.id] != location.id
            ),
            hidden=tuple(entity for entity in shown if not entity.known),
            canon=world,
            placements=_placements(world, world.entities.values(), frozenset(world.entities)),
        )

    def catalogue(self) -> tuple[Entity, ...]:
        return tuple(entity for entity in self.canon.entities.values() if entity.id != PLAYER_ID)


class VisibleScene(BaseScene):
    """The Narrator's view: it holds no unrevealed entity and names none, by construction."""

    @classmethod
    def of(cls, snapshot: SceneSnapshot) -> "VisibleScene":
        canon = snapshot.canon
        shown = (
            snapshot.player,
            snapshot.location,
            *snapshot.inventory,
            *snapshot.here,
            *snapshot.known_elsewhere,
        )
        met = frozenset(entity.id for entity in canon.entities.values() if entity.known)
        return cls(
            player=_undetailed(snapshot.player),
            location=_undetailed(snapshot.location),
            inventory=tuple(_undetailed(item) for item in snapshot.inventory),
            here=tuple(_undetailed(entity) for entity in snapshot.here),
            known_elsewhere=tuple(_undetailed(entity) for entity in snapshot.known_elsewhere),
            placements=_placements(canon, shown, met),
        )


def _placements(
    world: WorldState,
    entities: Iterable[Entity],
    nameable: frozenset[EntityId],
) -> dict[EntityId, str]:
    return {entity.id: _placement(entity, world, nameable) for entity in entities}


def _placement(entity: Entity, world: WorldState, nameable: frozenset[EntityId]) -> str:
    """A placement names its holder only where the reader may be told that holder exists."""
    match entity:
        case LocationEntity():
            return ""
        case ActorEntity():
            location = world.entities.get(entity.location_id)
            if location is None or location.id not in nameable:
                return ""
            return f"at {location.name}"
        case ItemEntity():
            container = world.container_of(entity)
            if container.id not in nameable:
                return ""
            if isinstance(container, LocationEntity):
                return f"at {container.name}"
            return "carried" if container.id == PLAYER_ID else f"held by {container.name}"


def _undetailed[T: Entity](entity: T) -> T:
    """`detail.hook` is authored as canon the player has not reached, so the Narrator gets none."""
    return entity.model_copy(update={"detail": None})
