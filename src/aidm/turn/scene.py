from collections.abc import Iterable, Mapping

from aidm.state.base import PLAYER_ID, Entity, EntityId, Exit, Frozen
from aidm.state.world import Game, Thread, WorldState


class BaseScene(Frozen):
    player: Entity
    location: Entity
    inventory: tuple[Entity, ...]
    here: tuple[Entity, ...]
    known_elsewhere: tuple[Entity, ...]
    placements: dict[EntityId, str]
    exits: tuple[Exit, ...] = ()
    exit_names: dict[EntityId, str] = {}

    def placement_of(self, entity: Entity) -> str:
        return self.placements[entity.id]

    def exit_name(self, way: Exit) -> str:
        return self.exit_names[way.to]


class SceneSnapshot(BaseScene):
    hidden: tuple[Entity, ...]
    canon: tuple[Entity, ...]
    party: tuple[EntityId, ...]
    threads: tuple[Thread, ...] = ()
    notes: tuple[str, ...] = ()

    @classmethod
    def of(cls, state: Game) -> "SceneSnapshot":
        world = state.world
        player = state.player
        location = world.require_kind(state.player_location, "location")
        canon = tuple(world.entities)
        by_id = {entity.id: entity for entity in canon}
        shown = [entity for entity in canon if entity.id != PLAYER_ID]
        inventory = world.children(PLAYER_ID, "item")
        carried_ids = {item.id for item in inventory}
        placed = [
            entity for entity in shown if entity.id not in carried_ids and entity.id != location.id
        ]
        locations = {entity.id: world.location_of(entity) for entity in placed}
        party = tuple(world.party)
        exit_names = {way.to: world.require(way.to).name for way in location.exits}
        exits = tuple(sorted(location.exits, key=lambda way: exit_names[way.to]))
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
            hidden=_reachable_hidden(world, location),
            canon=canon,
            placements=_placements(by_id, canon, frozenset(by_id), party),
            exits=exits,
            exit_names=exit_names,
            party=party,
            threads=tuple(
                sorted(
                    (thread for thread in world.threads if thread.status != "resolved"),
                    key=lambda thread: thread.title,
                )
            ),
            notes=world.pending_notes,
        )

    def catalogue(self) -> tuple[Entity, ...]:
        return tuple(entity for entity in self.canon if entity.id != PLAYER_ID)


def _reachable_hidden(world: WorldState, here: Entity) -> tuple[Entity, ...]:
    """Unknown canon a turn could touch: here, one exit away, or a signposted location."""
    near = {here.id, *(way.to for way in here.exits)}
    signposted = {way.to for entity in world.entities if entity.known for way in entity.exits}
    return tuple(
        entity
        for entity in world.entities
        if not entity.known and (world.location_of(entity) in near or entity.id in signposted)
    )


class VisibleScene(BaseScene):
    """The Narrator's view: it holds no unrevealed entity and names none, by construction."""

    @classmethod
    def of(cls, snapshot: SceneSnapshot) -> "VisibleScene":
        by_id = {entity.id: entity for entity in snapshot.canon}
        shown = (
            snapshot.player,
            snapshot.location,
            *snapshot.inventory,
            *snapshot.here,
            *snapshot.known_elsewhere,
        )
        met = frozenset(entity.id for entity in snapshot.canon if entity.known)
        known_exits = tuple(way for way in snapshot.exits if way.known)
        return cls(
            player=_undetailed(snapshot.player),
            location=_undetailed(snapshot.location),
            inventory=tuple(_undetailed(item) for item in snapshot.inventory),
            here=tuple(_undetailed(entity) for entity in snapshot.here),
            known_elsewhere=tuple(_undetailed(entity) for entity in snapshot.known_elsewhere),
            placements=_placements(by_id, shown, met, snapshot.party),
            exits=known_exits,
            exit_names={way.to: snapshot.exit_name(way) for way in known_exits},
        )


def _placements(
    by_id: Mapping[EntityId, Entity],
    entities: Iterable[Entity],
    nameable: frozenset[EntityId],
    party: tuple[EntityId, ...],
) -> dict[EntityId, str]:
    return {entity.id: _placement(entity, by_id, nameable, party) for entity in entities}


def _placement(
    entity: Entity,
    by_id: Mapping[EntityId, Entity],
    nameable: frozenset[EntityId],
    party: tuple[EntityId, ...],
) -> str:
    """A placement names its holder only where the reader may be told that holder exists."""
    if entity.id in party:
        return "travelling with the player"
    holder = None if entity.parent_id is None else by_id[entity.parent_id]
    if holder is None or holder.id not in nameable:
        return ""
    if holder.kind == "location":
        return f"at {holder.name}"
    return "carried" if holder.id == PLAYER_ID else f"held by {holder.name}"


def _undetailed(entity: Entity) -> Entity:
    """`detail.when_reached` is canon authored before it is reached, so the Narrator gets none."""
    return entity.model_copy(update={"detail": None})
