import json
from dataclasses import dataclass, field

from pydantic import Field, JsonValue

from aidm.content.authored import ScenarioWorld
from aidm.content.sources import ExpansionPolicy
from aidm.state.base import Entity, EntityId, Frozen, RelationId
from aidm.state.world import Hook, Memory, Relation, ScenarioMeta, Thread, WorldState


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
    relations: tuple[Relation, ...] = ()
    threads: tuple[Thread, ...] = ()
    memories: tuple[Memory, ...] = ()
    hooks: tuple[Hook, ...] = ()
    remove: tuple[str, ...] = ()


@dataclass
class WorldDraft:
    """The scenario under authorship: mutated only by `apply`, judged only by `world()`."""

    expansion: ExpansionPolicy = "closed"
    art_style: str = ""
    meta: ScenarioMeta | None = None
    starting_location_id: EntityId | None = None
    starting_party: tuple[EntityId, ...] = ()
    canon: WorldState = field(default_factory=WorldState)

    def apply(self, patch: ScenarioPatch) -> str:
        changed: list[str] = []
        if patch.meta is not None:
            self.meta = patch.meta
            changed.append("meta")
        if patch.starting_location_id is not None:
            self.starting_location_id = patch.starting_location_id
            changed.append("starting_location_id")
        if patch.starting_party is not None:
            self.starting_party = patch.starting_party
            changed.append("starting_party")
        if patch.art_style is not None:
            self.art_style = patch.art_style
            changed.append("art_style")
        for entity in patch.entities:
            self.canon.entities[entity.id] = entity
        for relation in patch.relations:
            self.canon.relations[relation.id] = relation
        for thread in patch.threads:
            self.canon.threads[thread.id] = thread
        for memory in patch.memories:
            self.canon.memories[memory.id] = memory
        for hook in patch.hooks:
            self.canon.hooks[hook.id] = hook
        counts = {
            "entities": len(patch.entities),
            "relations": len(patch.relations),
            "threads": len(patch.threads),
            "memories": len(patch.memories),
            "hooks": len(patch.hooks),
        }
        changed.extend(f"{count} {what}" for what, count in counts.items() if count)
        for target in patch.remove:
            self._remove(target)
        if patch.remove:
            changed.append(f"removed {len(patch.remove)}")
        return f"wrote: {', '.join(changed)}" if changed else "nothing to change"

    def _remove(self, target: str) -> None:
        if target in self.canon.entities:
            del self.canon.entities[EntityId(target)]
        elif target in self.canon.relations:
            del self.canon.relations[RelationId(target)]
        elif target in self.canon.threads:
            del self.canon.threads[target]
        elif target in self.canon.memories:
            del self.canon.memories[target]
        elif target in self.canon.hooks:
            del self.canon.hooks[target]
        else:
            raise ValueError(
                f"nothing in the draft has id {target!r}; read `scenario_so_far` and remove ids "
                "exactly as it spells them"
            )

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
            entities=tuple(self.canon.entities.values()),
            relations=tuple(self.canon.relations.values()),
            threads=tuple(self.canon.threads.values()),
            memories=tuple(self.canon.memories.values()),
            hooks=tuple(self.canon.hooks.values()),
        )

    def pretty(self) -> str:
        body: dict[str, JsonValue] = {
            "meta": None if self.meta is None else self.meta.model_dump(mode="json"),
            "art_style": self.art_style,
            "starting_location_id": self.starting_location_id,
            "starting_party": list(self.starting_party),
            **self.canon.model_dump(mode="json", exclude={"fired_hooks", "pending_notes"}),
        }
        return json.dumps(body, indent=2)
