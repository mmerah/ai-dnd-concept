from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from aidm.core.base import Entity, EntityId, Mutable
from aidm.core.packs import CONTENT_SLUG_MAX_LENGTH, ContentRef, ContentSlug, Value
from aidm.core.world import BareLocation, EngineRules, GameState, WorldState

from .content.records.base import Collection
from .content.records.spells import SlotLevel
from .content.vocabulary import ConditionName, RestType
from .values import Ability, Attributes

MAX_LEVEL = 20

type Decisions = dict[ContentSlug, tuple[ContentSlug, ...]]


# A ContentRef flattened to a string, because a map key must survive a JSON round trip.
type FeatureKey = Annotated[
    str,
    Field(
        pattern=r"^[a-z0-9-]+/features/[a-z0-9-]+$",
        max_length=2 * CONTENT_SLUG_MAX_LENGTH + len("/features/"),
    ),
]
type SpellKey = Annotated[
    str,
    Field(
        pattern=r"^[a-z0-9-]+/spells/[a-z0-9-]+$",
        max_length=2 * CONTENT_SLUG_MAX_LENGTH + len("/spells/"),
    ),
]


def _key(ref: ContentRef, collection: Collection) -> str:
    if ref.collection != collection:
        raise ValueError(f"{ref} is not a {collection} record")
    return str(ref)


def feature_key(ref: ContentRef) -> FeatureKey:
    return _key(ref, "features")


def spell_key(ref: ContentRef) -> SpellKey:
    return _key(ref, "spells")


def spell_ref(key: SpellKey) -> ContentRef:
    """The inverse of `spell_key`; the key's pattern guarantees the three parts."""
    pack, _, index = key.split("/")
    return ContentRef(pack=pack, collection="spells", index=index)


class ResourceState(Mutable):
    """A pool of uses that a rest refills: a feature's counter, or one level of spell slots."""

    remaining: int = Field(ge=0)
    maximum: int = Field(ge=1)
    recharge: RestType

    @model_validator(mode="after")
    def _within_maximum(self) -> Self:
        if self.remaining > self.maximum:
            raise ValueError(f"resource has {self.remaining} uses, maximum {self.maximum}")
        return self

    @property
    def spent(self) -> int:
        return self.maximum - self.remaining

    def refills(self, completed: RestType) -> bool:
        return self.spent > 0 and (self.recharge == "short" or completed == "long")


type FeatureResources = dict[FeatureKey, ResourceState]
type SpellSlots = dict[SlotLevel, ResourceState]


class Origin(Value):
    class_ref: ContentRef
    race_ref: ContentRef | None = None
    subrace_ref: ContentRef | None = None
    background_ref: ContentRef | None = None
    subclass_ref: ContentRef | None = None

    @property
    def refs(self) -> tuple[ContentRef, ...]:
        chosen = (self.race_ref, self.subrace_ref, self.background_ref, self.subclass_ref)
        return (self.class_ref, *(ref for ref in chosen if ref is not None))


class Progression(Mutable):
    origin: Origin
    level: int = Field(ge=1, le=MAX_LEVEL)
    level_up_available: bool = False
    prof_bonus: int = Field(ge=2)
    saving_throws: tuple[Ability, ...]
    proficiencies: tuple[ContentSlug, ...]
    spell_slots: SpellSlots
    chosen_spells: tuple[ContentRef, ...]
    decisions: Decisions
    features: tuple[ContentRef, ...]
    feature_resources: FeatureResources

    @model_validator(mode="after")
    def _no_repeated_proficiency(self) -> Self:
        if len(set(self.proficiencies)) != len(self.proficiencies):
            raise ValueError(f"proficiency held twice: {sorted(self.proficiencies)}")
        if len(set(self.features)) != len(self.features):
            raise ValueError(f"feature held twice: {sorted(str(ref) for ref in self.features)}")
        chosen = [spell_key(ref) for ref in self.chosen_spells]
        if len(set(chosen)) != len(chosen):
            raise ValueError(f"spell chosen twice: {sorted(chosen)}")
        keys = {feature_key(ref) for ref in self.features}
        if unknown := sorted(set(self.feature_resources) - keys):
            raise ValueError(f"feature resources recorded for unheld features: {unknown}")
        if self.level_up_available and self.level >= MAX_LEVEL:
            raise ValueError(f"level {MAX_LEVEL} cannot have another level-up available")
        return self


class Advancement(Value):
    progression: Progression
    attributes: Attributes
    hp_gain: int = Field(ge=1)


Wounds = Literal["unharmed", "hurt", "badly hurt", "down"]


class StatBlock(Mutable):
    attributes: Attributes = Attributes()
    max_hp: int = Field(default=4, ge=1)
    hp: int = Field(default=4, ge=0)
    ac: int = Field(default=10, ge=0)
    conditions: tuple[ConditionName, ...] = ()
    # Keep monster bonuses absolute because player bonuses are derived from progression.
    saving_throws: dict[Ability, int] = Field(default_factory=dict)
    condition_immunities: tuple[ConditionName, ...] = ()

    @model_validator(mode="after")
    def _consistent_stats(self) -> Self:
        if self.hp > self.max_hp:
            raise ValueError(f"hp {self.hp} exceeds max_hp {self.max_hp}")
        if held := sorted(set(self.conditions) & set(self.condition_immunities)):
            raise ValueError(f"immune to conditions it suffers: {held}")
        return self

    def apply_hp_delta(self, delta: int) -> int:
        """Clamp to the survivable range and report the change that actually landed."""
        before = self.hp
        self.hp = max(0, min(self.max_hp, before + delta))
        return self.hp - before

    def apply_condition(self, condition: ConditionName, *, active: bool) -> bool:
        if active and condition in self.condition_immunities:
            return False
        held: set[ConditionName] = set(self.conditions)
        if active:
            held.add(condition)
        else:
            held.discard(condition)
        changed = tuple(sorted(held))
        if changed == self.conditions:
            return False
        self.conditions = changed
        return True

    @property
    def wounds(self) -> Wounds:
        if self.hp == 0:
            return "down"
        if self.hp * 2 <= self.max_hp:
            return "badly hurt"
        return "hurt" if self.hp < self.max_hp else "unharmed"


class Dnd5eActorState(EngineRules):
    kind: Literal["actor"] = "actor"  # pyright: ignore[reportIncompatibleVariableOverride]
    stats: StatBlock
    progression: Progression | None = None
    ref: ContentRef | None = None


class Dnd5eItemState(EngineRules):
    kind: Literal["item"] = "item"  # pyright: ignore[reportIncompatibleVariableOverride]
    ref: ContentRef | None = None


type Dnd5eRules = Annotated[
    Dnd5eActorState | Dnd5eItemState | BareLocation, Field(discriminator="kind")
]
Dnd5eState = GameState[Dnd5eRules]
Dnd5eWorldState = WorldState[Dnd5eRules]


@dataclass(frozen=True, slots=True)
class Dnd5eActor:
    """A record narrowed to 5e: the same mutable halves, read as one object by every rule."""

    entity: Entity
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
    def stats(self) -> StatBlock:
        return self.state.stats

    @property
    def progression(self) -> Progression | None:
        return self.state.progression

    @property
    def ref(self) -> ContentRef | None:
        return self.state.ref


@dataclass(frozen=True, slots=True)
class Dnd5eItem:
    entity: Entity
    state: Dnd5eItemState

    @property
    def id(self) -> EntityId:
        return self.entity.id

    @property
    def name(self) -> str:
        return self.entity.name

    @property
    def ref(self) -> ContentRef | None:
        return self.state.ref


class Dnd5eCharacterData(Value):
    origin: Origin
    starting_attributes: Attributes = Attributes()
    decisions: Decisions = Field(default_factory=dict)


class Dnd5eActorDefinition(Value):
    ref: ContentRef | None = None
    stats: StatBlock | None = None


class Dnd5eItemDefinition(Value):
    ref: ContentRef | None = None
