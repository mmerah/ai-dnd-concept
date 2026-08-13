from collections.abc import Iterable, Mapping

from aidm.state.base import PLAYER_ID, Entity, EntityId, Frozen
from aidm.state.world import LOCKED_TAG, GameState, Memory, Thread


class Exit(Frozen):
    location_id: EntityId
    name: str
    known: bool
    locked: bool


class BaseScene(Frozen):
    player: Entity
    location: Entity
    inventory: tuple[Entity, ...]
    here: tuple[Entity, ...]
    known_elsewhere: tuple[Entity, ...]
    placements: dict[EntityId, str]
    exits: tuple[Exit, ...] = ()

    def placement_of(self, entity: Entity) -> str:
        return self.placements[entity.id]

    def voice(self, speaker_id: EntityId | None) -> Entity | None:
        """The one answer to who the Narrator may speak as: an actor this scene holds as here."""
        return next(
            (held for held in self.here if held.id == speaker_id and held.kind == "actor"), None
        )


class SceneSnapshot(BaseScene):
    hidden: tuple[Entity, ...]
    canon: tuple[Entity, ...]
    party: tuple[EntityId, ...]
    threads: tuple[Thread, ...] = ()
    memories: tuple[Memory, ...] = ()
    notes: tuple[str, ...] = ()

    @classmethod
    def of(cls, state: GameState) -> "SceneSnapshot":
        world = state.world
        player = state.player
        location = world.require_kind(state.player_location, "location")
        canon = tuple(world.entities.values())
        by_id = {entity.id: entity for entity in canon}
        shown = [entity for entity in canon if entity.id != PLAYER_ID]
        inventory = world.children(PLAYER_ID, "item")
        carried_ids = {item.id for item in inventory}
        placed = [
            entity for entity in shown if entity.id not in carried_ids and entity.id != location.id
        ]
        locations = {entity.id: world.location_of(entity) for entity in placed}
        party = world.party()
        present = {
            PLAYER_ID,
            location.id,
            *(held for held, place in locations.items() if place == location.id),
        }
        exits = tuple(
            sorted(
                (
                    Exit(
                        location_id=relation.far_end(location.id),
                        name=world.require(relation.far_end(location.id)).name,
                        known=relation.known,
                        locked=LOCKED_TAG in relation.tags,
                    )
                    for relation in world.connections(location.id)
                ),
                key=lambda exit: exit.name,
            )
        )
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
            canon=canon,
            placements=_placements(by_id, canon, frozenset(by_id), party),
            exits=exits,
            party=party,
            threads=tuple(
                sorted(
                    (thread for thread in world.threads.values() if thread.status != "resolved"),
                    key=lambda thread: thread.title,
                )
            ),
            memories=tuple(
                memory
                for memory in world.memories.values()
                if memory.owner is None or memory.owner in present
            ),
            notes=world.pending_notes,
        )

    def catalogue(self) -> tuple[Entity, ...]:
        return tuple(entity for entity in self.canon if entity.id != PLAYER_ID)


def check_speaker(scene: SceneSnapshot, speaker_id: EntityId | None) -> str | None:
    """The player is addressed, never the speaker: losing this lets the Director voice them."""
    if speaker_id is None:
        return None
    if speaker_id == PLAYER_ID:
        return "speaker_id names another actor the player addresses, never the player."
    if not any(entity.id == speaker_id for entity in scene.canon):
        return f"unknown speaker id {speaker_id!r}. Use only ids you were shown, or null."
    if scene.voice(speaker_id) is None:
        return (
            f"speaker {speaker_id!r} must be an NPC the player has met and who is here with them. "
            "Use null if nobody is being addressed."
        )
    return None


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
        return cls(
            player=_undetailed(snapshot.player),
            location=_undetailed(snapshot.location),
            inventory=tuple(_undetailed(item) for item in snapshot.inventory),
            here=tuple(_undetailed(entity) for entity in snapshot.here),
            known_elsewhere=tuple(_undetailed(entity) for entity in snapshot.known_elsewhere),
            placements=_placements(by_id, shown, met, snapshot.party),
            exits=tuple(exit for exit in snapshot.exits if exit.known),
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
    """`detail.hook` is authored as canon the player has not reached, so the Narrator gets none."""
    return entity.model_copy(update={"detail": None})
