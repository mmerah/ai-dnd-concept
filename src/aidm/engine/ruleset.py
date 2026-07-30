from collections.abc import Sequence
from typing import Protocol

from pydantic import Field

from ..content.library import ContentMiss
from ..content.models import PackStamp
from ..content.records.base import ContentRef
from ..content.records.character import ClassRecord, FeatureMechanics, ProgressionChoice
from ..content.records.monsters import MonsterRecord
from ..content.records.spells import SpellLevel, SpellRecord
from ..content.vocabulary import RestType
from ..domain.models.progression import Origin
from ..domain.models.stats import StatBlock
from ..utils import dice
from ..utils.models import EMPTY_FROZEN_MAP, Ability, Frozen, FrozenMap, Slug


class SpellcastingProfile(Frozen):
    ability: Ability
    slot_recharge: RestType
    # A prepared caster chooses from the whole class list each long rest; a known caster's
    # repertoire is fixed at level-up, which is the only one this pack can record.
    prepares: bool


class CharacterProfile(Frozen):
    hit_die: int = Field(ge=1)
    saving_throws: tuple[Ability, ...]
    proficiencies: tuple[Slug, ...] = ()
    ability_bonuses: FrozenMap[Ability, int] = EMPTY_FROZEN_MAP
    choices: tuple[ProgressionChoice, ...] = ()
    spellcasting: SpellcastingProfile | None = None


class SpellProfile(Frozen):
    ref: ContentRef
    name: str
    level: SpellLevel


class FeatureProfile(Frozen):
    ref: ContentRef
    name: str
    desc: str
    mechanics: FeatureMechanics
    replaces: tuple[ContentRef, ...] = ()


class LevelProfile(Frozen):
    prof_bonus: int = Field(ge=2)
    improvements: int = Field(ge=0)
    spell_slots: FrozenMap[int, int] = EMPTY_FROZEN_MAP
    choices: tuple[ProgressionChoice, ...] = ()
    subclass_choice: ProgressionChoice | None = None
    features: tuple[FeatureProfile, ...] = ()


class AttackProfile(Frozen):
    name: str
    to_hit: int
    damage: dice.SelfContainedDice | None = None


class WeaponProfile(Frozen):
    index: Slug
    damage: dice.DiceExpr | None = None
    ranged: bool = False
    finesse: bool = False


class ArchetypeProfile(Frozen):
    stats: StatBlock
    attacks: tuple[AttackProfile, ...] = ()


class ArchetypeRules(Protocol):
    def archetype(self, ref: ContentRef) -> ArchetypeProfile | None: ...
    def provides(self, ref: ContentRef) -> bool: ...


class FeatureRules(Protocol):
    def feature(self, ref: ContentRef) -> FeatureProfile | ContentMiss: ...


class CombatRules(ArchetypeRules, FeatureRules, Protocol):
    def weapon(self, ref: ContentRef) -> WeaponProfile | None: ...

    def proficient(self, origin: Origin, held: Sequence[Slug], equipment: Slug) -> bool: ...


class CharacterRules(Protocol):
    def character(self, origin: Origin) -> CharacterProfile: ...


class ProgressionRules(CharacterRules, FeatureRules, Protocol):
    def level(self, origin: Origin, level: int) -> LevelProfile: ...


class SpellRules(Protocol):
    def spell(self, ref: ContentRef) -> SpellRecord | ContentMiss: ...

    def spell_list(self, origin: Origin) -> tuple[SpellProfile, ...]:
        """Every spell the class, plus any chosen subclass, may ever cast."""
        ...


class NarrativeRules(CharacterRules, FeatureRules, SpellRules, Protocol):
    """A miss is returned rather than dropped so a pack that lost a record shows in the prompt."""

    def monster(self, ref: ContentRef) -> MonsterRecord | ContentMiss: ...
    def klass(self, ref: ContentRef) -> ClassRecord | ContentMiss: ...


class Ruleset(ProgressionRules, CombatRules, NarrativeRules, Protocol):
    @property
    def stamps(self) -> Sequence[PackStamp]: ...
