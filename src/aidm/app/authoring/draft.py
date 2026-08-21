from collections.abc import Iterable

from pydantic import Field

from aidm.content.model import Scenario
from aidm.state.model import (
    PLAYER_ID,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    Game,
    Mutable,
    ScenarioMeta,
    Thread,
    WorldState,
)


def _index[T: Entity | Thread](kept: list[T], target: str) -> int | None:
    return next((index for index, held in enumerate(kept) if held.id == target), None)


def _describe(item: Entity | Thread, verb: str) -> str:
    if isinstance(item, Entity):
        return f"{verb} {item.kind} {item.name}[{item.id}]"
    return f"{verb} thread {item.title}[{item.id}]"


def _upsert[T: Entity | Thread](kept: list[T], written: Iterable[T]) -> list[str]:
    lines: list[str] = []
    for one in written:
        found = _index(kept, one.id)
        if found is None:
            kept.append(one)
            lines.append(_describe(one, "created"))
        else:
            kept[found] = one
            lines.append(_describe(one, "modified"))
    return lines


def _drop[T: Entity | Thread](kept: list[T], target: str) -> T | None:
    found = _index(kept, target)
    if found is None:
        return None
    return kept.pop(found)


class ScenarioPatch(Frozen):
    """One pass over the draft. A set field replaces its value; an element whose id the draft
    already holds is replaced whole; `remove` drops ids from whichever collection holds them."""

    meta: ScenarioMeta | None = None
    starting_location_id: EntityId | None = None
    starting_party: tuple[EntityId, ...] | None = None
    art_style: str | None = Field(
        default=None,
        description=(
            "One line of visual direction for this scenario's illustrations — palette, medium "
            "and mood, written from the tone of the source or premise. Left unset, the app's "
            "default style is used."
        ),
    )
    entities: tuple[Entity, ...] = ()
    threads: tuple[Thread, ...] = ()
    remove: tuple[str, ...] = ()


class WorldDraft(Mutable):
    """The scenario under authorship, flat in `ScenarioPatch` vocabulary until `scenario()`."""

    grows: bool = False
    art_style: str = ""
    meta: ScenarioMeta | None = None
    starting_location_id: EntityId | None = None
    starting_party: tuple[EntityId, ...] = ()
    entities: list[Entity] = Field(default_factory=list)
    threads: list[Thread] = Field(default_factory=list)

    @classmethod
    def of(cls, scenario: Scenario) -> "WorldDraft":
        return cls(
            grows=scenario.grows,
            art_style=scenario.art_style,
            meta=scenario.meta,
            starting_location_id=scenario.starting_location_id,
            starting_party=tuple(scenario.world.party),
            entities=[entity.model_copy(deep=True) for entity in scenario.world.entities],
            threads=[thread.model_copy(deep=True) for thread in scenario.world.threads],
        )

    @classmethod
    def of_game(cls, state: Game) -> "WorldDraft":
        """The live world as a draft, minus the player, what they carry, and any party member
        play has sent away from their side — all things a `Scenario` refuses."""
        world = state.world
        return cls(
            meta=state.scenario,
            starting_location_id=state.player_location,
            starting_party=tuple(
                member
                for member in world.party
                if world.require(member).parent_id == state.player_location
            ),
            entities=[
                entity.model_copy(deep=True)
                for entity in world.entities
                if PLAYER_ID not in (entity.id, entity.parent_id)
            ],
            threads=[thread.model_copy(deep=True) for thread in world.threads],
        )

    def apply(self, patch: ScenarioPatch) -> str:
        changed: list[str] = []
        if patch.meta is not None:
            self.meta = patch.meta
            changed.append("set meta")
        if patch.starting_location_id is not None:
            self.starting_location_id = patch.starting_location_id
            changed.append("set starting_location_id")
        if patch.starting_party is not None:
            self.starting_party = patch.starting_party
            changed.append("set starting_party")
        if patch.art_style is not None:
            self.art_style = patch.art_style
            changed.append("set art_style")
        changed.extend(_upsert(self.entities, patch.entities))
        changed.extend(_upsert(self.threads, patch.threads))
        changed.extend(self._remove(target) for target in patch.remove)
        return "\n".join(changed) if changed else "nothing to change"

    def _remove(self, target: str) -> str:
        removed = _drop(self.entities, target)
        if removed is None:
            removed = _drop(self.threads, target)
        if removed is None:
            raise ValueError(
                f"nothing in the draft has id {target!r}; read `scenario_so_far` and remove ids "
                "exactly as it spells them"
            )
        return _describe(removed, "deleted")

    def as_json(self) -> str:
        return self.model_dump_json(indent=2, exclude={"grows"})

    def scenario(self, engines: tuple[EngineId, ...]) -> Scenario:
        if self.meta is None:
            raise ValueError("the draft has no `meta` yet: write a title and premise first")
        if self.starting_location_id is None:
            raise ValueError("the draft has no `starting_location_id` yet")
        return Scenario(
            meta=self.meta,
            grows=self.grows,
            engines=engines,
            art_style=self.art_style,
            starting_location_id=self.starting_location_id,
            world=WorldState(
                entities=list(self.entities),
                threads=list(self.threads),
                party=list(self.starting_party),
            ),
        )
