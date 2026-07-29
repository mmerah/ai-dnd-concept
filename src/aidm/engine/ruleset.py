from collections.abc import Sequence
from typing import Protocol

from pydantic import Field

from ..content import ContentMiss, ContentRef, MonsterRecord, PackStamp
from ..content.records import ClassRecord, ProgressionChoice
from ..domain.models import Ability, Origin, StatBlock
from ..utils import dice
from ..utils.models import EMPTY_FROZEN_MAP, Frozen, FrozenMap, Slug


class CharacterProfile(Frozen):
    hit_die: int = Field(ge=1)
    saving_throws: tuple[Ability, ...]
    proficiencies: tuple[Slug, ...] = ()
    ability_bonuses: FrozenMap[Ability, int] = EMPTY_FROZEN_MAP
    choices: tuple[ProgressionChoice, ...] = ()


class LevelProfile(Frozen):
    prof_bonus: int = Field(ge=2)
    improvements: int = Field(ge=0)
    spell_slots: FrozenMap[int, int] = EMPTY_FROZEN_MAP
    choices: tuple[ProgressionChoice, ...] = ()
    subclass_choice: ProgressionChoice | None = None


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


class CombatRules(ArchetypeRules, Protocol):
    def weapon(self, ref: ContentRef) -> WeaponProfile | None: ...

    def proficient(self, origin: Origin, held: Sequence[Slug], equipment: Slug) -> bool: ...


class ProgressionRules(Protocol):
    def character(self, origin: Origin) -> CharacterProfile: ...
    def level(self, origin: Origin, level: int) -> LevelProfile: ...


class NarrativeRules(Protocol):
    """A miss is returned rather than dropped so a pack that lost a record shows in the prompt."""

    def monster(self, ref: ContentRef) -> MonsterRecord | ContentMiss: ...
    def klass(self, ref: ContentRef) -> ClassRecord | ContentMiss: ...


class Ruleset(ProgressionRules, CombatRules, NarrativeRules, Protocol):
    @property
    def stamps(self) -> Sequence[PackStamp]: ...
