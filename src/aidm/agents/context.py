from collections.abc import Callable

from ..domain.base import PLAYER_ID, EntityId, Kind
from ..domain.entities import ActorEntity, Entity, ItemEntity, LocationEntity
from ..domain.state import EngineState, Exchange, GameState, WorldState
from ..utils.models import Frozen

type EntityRenderer = Callable[[Entity], str]


class DirectorScene(Frozen):
    engine: EngineState
    player: ActorEntity
    where: LocationEntity
    carried: tuple[ItemEntity, ...]
    here: tuple[Entity, ...]
    elsewhere: tuple[Entity, ...]
    unrevealed: tuple[Entity, ...]
    canon: WorldState

    def is_here(self, entity: Entity) -> bool:
        return self.canon.location_of(entity) == self.where.id


class NarratorEntityView(Frozen):
    id: EntityId
    kind: Kind
    name: str
    brief: str
    state: str = ""


class NarratorScene(Frozen):
    player: NarratorEntityView
    where: NarratorEntityView
    carried: tuple[NarratorEntityView, ...]
    here: tuple[NarratorEntityView, ...]
    elsewhere: tuple[NarratorEntityView, ...]


class CatalogueEntityView(Frozen):
    id: EntityId
    kind: Kind
    name: str
    brief: str
    placement: str = ""
    description: str = ""
    hook: str = ""
    state: str = ""


class CatalogueScene(Frozen):
    catalogue: tuple[CatalogueEntityView, ...]


class DirectorContext(Frozen):
    scene: DirectorScene
    scenario_title: str
    scenario_premise: str
    prompt: str
    recent: tuple[Exchange, ...] = ()


class NarratorContext(Frozen):
    scene: NarratorScene
    scenario_title: str
    scenario_premise: str
    intent: str
    tone: str
    speaker_id: EntityId | None
    evidence: str
    prompt: str
    recent: tuple[Exchange, ...] = ()


class MaintainerContext(Frozen):
    scene: CatalogueScene
    scenario_title: str
    scenario_premise: str
    prompt: str
    evidence: str
    narration: str
    recent: tuple[Exchange, ...] = ()


class CreatorContext(Frozen):
    scene: CatalogueScene
    scenario_title: str
    scenario_premise: str
    narration: str
    recent: tuple[Exchange, ...] = ()


def build_director_scene(state: GameState) -> DirectorScene:
    world = state.world
    player = state.player
    where = world.require_kind(player.location_id, LocationEntity)
    shown = [entity for entity in world.entities.values() if entity.id != PLAYER_ID]
    carried = tuple(
        entity
        for entity in shown
        if isinstance(entity, ItemEntity) and entity.container_id == PLAYER_ID
    )
    carried_ids = {entity.id for entity in carried}
    placed = [entity for entity in shown if entity.id not in carried_ids and entity.id != where.id]
    locations = {entity.id: world.location_of(entity) for entity in placed}
    return DirectorScene(
        engine=state.engine,
        player=player,
        where=where,
        carried=carried,
        here=tuple(
            entity for entity in shown if entity.known and locations.get(entity.id) == where.id
        ),
        elsewhere=tuple(
            entity
            for entity in shown
            if entity.known and entity.id in locations and locations[entity.id] != where.id
        ),
        unrevealed=tuple(entity for entity in shown if not entity.known),
        canon=world,
    )


def build_narrator_scene(
    state: GameState,
    entity_state: EntityRenderer,
) -> NarratorScene:
    director = build_director_scene(state)
    return NarratorScene(
        player=_narrator_view(director.player, entity_state),
        where=_narrator_view(director.where, entity_state),
        carried=tuple(_narrator_view(entity, entity_state) for entity in director.carried),
        here=tuple(_narrator_view(entity, entity_state) for entity in director.here),
        elsewhere=tuple(_narrator_view(entity, entity_state) for entity in director.elsewhere),
    )


def build_catalogue_scene(
    state: GameState,
    entity_state: EntityRenderer,
) -> CatalogueScene:
    return CatalogueScene(catalogue=_catalogue(state, entity_state))


def _narrator_view(
    entity: Entity,
    entity_state: EntityRenderer,
) -> NarratorEntityView:
    return NarratorEntityView(
        id=entity.id,
        kind=entity.kind,
        name=entity.name,
        brief=entity.brief,
        state=entity_state(entity),
    )


def _catalogue(
    state: GameState,
    entity_state: EntityRenderer,
) -> tuple[CatalogueEntityView, ...]:
    return tuple(
        CatalogueEntityView(
            id=entity.id,
            kind=entity.kind,
            name=entity.name,
            brief=entity.brief,
            placement=entity_placement(entity, state.world),
            description="" if entity.detail is None else entity.detail.description,
            hook="" if entity.detail is None else entity.detail.hook,
            state=entity_state(entity),
        )
        for entity in state.world.entities.values()
        if entity.id != PLAYER_ID
    )


def entity_placement(entity: Entity, world: WorldState) -> str:
    match entity:
        case LocationEntity():
            return ""
        case ActorEntity():
            location = world.entities.get(entity.location_id)
            return "" if location is None else f"at {location.name}"
        case ItemEntity():
            container = world.container_of(entity)
            if isinstance(container, LocationEntity):
                return f"at {container.name}"
            return "carried" if container.id == PLAYER_ID else f"held by {container.name}"
