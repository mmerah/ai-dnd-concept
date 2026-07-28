"""The per-turn context every role's prompt is built from, and the visibility partition under it."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Self

from ..content import Content
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


@dataclass(frozen=True, slots=True)
class Scene:
    """The world as the player stands in it: the buckets every list a role is shown is drawn from,
    computed once per prompt instead of re-derived per view. It lives in `agents/` rather than on
    `GameState` because visibility is context policy, not entity lookup."""

    state: GameState
    where: LocationEntity
    # Named on their own, so neither reads to a role as somewhere to go or something to find.
    carried: tuple[ItemEntity, ...]
    here: tuple[Entity, ...]  # known, at the player's location
    elsewhere: tuple[Entity, ...]  # known, neither here nor carried
    # Cuts across the three above: known and where are independent axes, and hidden canon is one
    # section of a prompt rather than a filter on every list.
    unrevealed: tuple[Entity, ...]

    @classmethod
    def of(cls, state: GameState) -> Self:
        """The player is in no bucket: they are canon, but never a role's target."""
        world = state.world
        where = world.require_kind(state.player.location_id, LocationEntity)
        shown = [e for e in world.entities.values() if e.id != PLAYER_ID]
        carried = tuple(
            e for e in shown if isinstance(e, ItemEntity) and e.container_id == PLAYER_ID
        )
        held = {e.id for e in carried}
        # Where each of the rest stands, resolved once: `location_of` walks containment per item.
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
        """Every entity by id, the player included: an id a role *names* is checked against all of
        canon, not only the parts it was shown."""
        return self.state.world.entities

    @property
    def shown(self) -> list[Entity]:
        """Canon less the player — including `where`, which is in no bucket."""
        return [e for e in self.canon.values() if e.id != PLAYER_ID]

    def is_here(self, entity: Entity) -> bool:
        """Whether an entity stands with the player — the co-location primitive the Director's
        validator and the Narrator's speaker view both need."""
        return self.state.world.location_of(entity) == self.where.id


@dataclass(frozen=True, slots=True)
class TurnContext:
    """What is always present by the time any role renders. Per-stage payloads (`Direction`,
    `GrowthRequest`) are arguments to the builder that needs them, so none is ever `None`."""

    state: GameState
    prompt: str
    content: Content  # the loaded packs, injected so a test can play against a synthetic one
    events: Sequence[Event] = ()
    narration: str = ""
    recent: Sequence[Exchange] = ()  # already windowed by the pipeline; the single history slice

    @property
    def scene(self) -> Scene:
        """Computed rather than stored: the pipeline swaps `state` between stages, and a stored
        one would be a stage behind."""
        return Scene.of(self.state)
