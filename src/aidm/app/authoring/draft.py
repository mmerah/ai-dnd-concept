from collections.abc import Iterable

from pydantic import Field

from aidm.content.authored import ScenarioWorld
from aidm.content.sources import ExpansionPolicy
from aidm.state.base import Entity, EntityId, Frozen, Mutable
from aidm.state.world import ScenarioMeta, Thread


def _index[T: Entity | Thread](kept: list[T], target: str) -> int | None:
    return next((index for index, held in enumerate(kept) if held.id == target), None)


def _upsert[T: Entity | Thread](kept: list[T], written: Iterable[T]) -> None:
    for one in written:
        found = _index(kept, one.id)
        if found is None:
            kept.append(one)
        else:
            kept[found] = one


def _drop[T: Entity | Thread](kept: list[T], target: str) -> bool:
    found = _index(kept, target)
    if found is None:
        return False
    del kept[found]
    return True


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
    """The scenario under authorship: mutated only by `apply`, judged only by `world()`."""

    expansion: ExpansionPolicy = "closed"
    art_style: str = ""
    meta: ScenarioMeta | None = None
    starting_location_id: EntityId | None = None
    starting_party: tuple[EntityId, ...] = ()
    entities: list[Entity] = Field(default_factory=list)
    threads: list[Thread] = Field(default_factory=list)

    def apply(self, patch: ScenarioPatch) -> str:
        wrote: list[str] = []
        if patch.meta is not None:
            self.meta = patch.meta
            wrote.append("meta")
        if patch.starting_location_id is not None:
            self.starting_location_id = patch.starting_location_id
            wrote.append("starting_location_id")
        if patch.starting_party is not None:
            self.starting_party = patch.starting_party
            wrote.append("starting_party")
        if patch.art_style is not None:
            self.art_style = patch.art_style
            wrote.append("art_style")
        _upsert(self.entities, patch.entities)
        _upsert(self.threads, patch.threads)
        wrote.extend(
            f"{len(group)} {what}"
            for what, group in (
                ("entities", patch.entities),
                ("threads", patch.threads),
            )
            if group
        )
        for target in patch.remove:
            self._remove(target)
        if patch.remove:
            wrote.append(f"removed {len(patch.remove)}")
        return f"wrote: {', '.join(wrote)}" if wrote else "nothing to change"

    def _remove(self, target: str) -> None:
        if _drop(self.entities, target) or _drop(self.threads, target):
            return
        raise ValueError(
            f"nothing in the draft has id {target!r}; read `scenario_so_far` and remove ids "
            "exactly as it spells them"
        )

    def as_json(self) -> str:
        """The draft as its author reads it back; `expansion` is the app's own policy, not canon
        they write."""
        return self.model_dump_json(indent=2, exclude={"expansion"})

    def world(self) -> ScenarioWorld:
        if self.meta is None:
            raise ValueError("the draft has no `meta` yet: write a title and premise first")
        if self.starting_location_id is None:
            raise ValueError("the draft has no `starting_location_id` yet")
        return ScenarioWorld(
            meta=self.meta,
            expansion=self.expansion,
            art_style=self.art_style,
            starting_location_id=self.starting_location_id,
            starting_party=self.starting_party,
            entities=tuple(self.entities),
            threads=tuple(self.threads),
        )
