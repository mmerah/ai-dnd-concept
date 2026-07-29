from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..content import (
    Content,
    ContentMiss,
    ContentRef,
    MonsterAttack,
    MonsterRecord,
    PackStamp,
)
from ..content.records import (
    AbilityBonus,
    BackgroundRecord,
    ClassLevelRecord,
    ClassRecord,
    DamageRoll,
    EquipmentProficiency,
    FeatureRecord,
    ProgressionChoice,
    RaceRecord,
    RecordOption,
    SaveProficiency,
    SubclassLevelRecord,
    SubclassRecord,
    SubraceRecord,
    TraitRecord,
    WeaponRecord,
)
from ..domain.models import MAX_LEVEL, Ability, Origin, StatBlock
from ..utils import dice
from ..utils.models import Slug
from .ruleset import (
    ArchetypeProfile,
    AttackProfile,
    CharacterProfile,
    LevelProfile,
    Ruleset,
    WeaponProfile,
)

COVERS_NOTHING: frozenset[Slug] = frozenset()


@dataclass(frozen=True, slots=True)
class PackRuleset:
    content: Content
    # Precomputed to avoid per-turn content scans.
    covers: Mapping[ContentRef, frozenset[Slug]]
    saves: frozenset[ContentRef]

    @property
    def stamps(self) -> Sequence[PackStamp]:
        return self.content.stamps

    def character(self, origin: Origin) -> CharacterProfile:
        klass = self.content.require(origin.class_ref, ClassRecord)
        traits = self._traits(origin)
        return CharacterProfile(
            hit_die=klass.hit_die,
            saving_throws=klass.saving_throws,
            proficiencies=self._granted(origin, klass, traits),
            ability_bonuses=self._racial(origin),
            choices=self._origin_choices(origin, klass, traits),
        )

    def level(self, origin: Origin, level: int) -> LevelProfile:
        """Convert cumulative level records into per-level deltas."""
        reached = self._class_level(origin.class_ref, level)
        before = self._class_level(origin.class_ref, level - 1) if level > 1 else None
        features = (*reached.features, *self._subclass_features(origin, level))
        held = before.ability_score_bonuses if before else 0
        return LevelProfile(
            prof_bonus=reached.prof_bonus,
            improvements=_improvements(reached, held),
            spell_slots=reached.spellcasting.spell_slots if reached.spellcasting else {},
            choices=tuple(c for i in features for c in self._feature(origin.class_ref, i).choices),
            subclass_choice=self._subclass_choice(origin.class_ref, level),
        )

    def archetype(self, ref: ContentRef) -> ArchetypeProfile | None:
        record = self.content.get(ref, MonsterRecord)
        if isinstance(record, ContentMiss):
            return None
        return ArchetypeProfile(stats=_stats(record), attacks=_attacks(record))

    def weapon(self, ref: ContentRef) -> WeaponProfile | None:
        record = self.content.get(ref, WeaponRecord)
        if isinstance(record, ContentMiss):
            return None
        return WeaponProfile(
            index=record.index,
            damage=None if record.damage is None else record.damage.dice,
            ranged=record.weapon_range == "Ranged",
            finesse="finesse" in record.properties,
        )

    def monster(self, ref: ContentRef) -> MonsterRecord | ContentMiss:
        return self.content.get(ref, MonsterRecord)

    def klass(self, ref: ContentRef) -> ClassRecord | ContentMiss:
        return self.content.get(ref, ClassRecord)

    def proficient(self, origin: Origin, held: Sequence[Slug], equipment: Slug) -> bool:
        refs = (origin.class_ref.sibling("proficiencies", index) for index in held)
        return any(equipment in self.covers.get(ref, COVERS_NOTHING) for ref in refs)

    def provides(self, ref: ContentRef) -> bool:
        return self.content.resolves(ref) is None

    def _origin_choices(
        self, origin: Origin, klass: ClassRecord, traits: Sequence[TraitRecord]
    ) -> tuple[ProgressionChoice, ...]:
        choices = list(klass.choices)
        if origin.race_ref is not None:
            choices += self.content.require(origin.race_ref, RaceRecord).choices
        if origin.background_ref is not None:
            choices += self.content.require(origin.background_ref, BackgroundRecord).choices
        return tuple(choices + [c for trait in traits for c in trait.choices])

    def _granted(
        self, origin: Origin, klass: ClassRecord, traits: Sequence[TraitRecord]
    ) -> tuple[Slug, ...]:
        """Drop duplicate save records because the class already declares saving throws."""
        granted = list(klass.proficiencies)
        if origin.background_ref is not None:
            background = self.content.require(origin.background_ref, BackgroundRecord)
            granted += background.starting_proficiencies
        granted += [p for trait in traits for p in trait.proficiencies]
        held = (origin.class_ref.sibling("proficiencies", index) for index in granted)
        return tuple(ref.index for ref in held if ref not in self.saves)

    def _traits(self, origin: Origin) -> tuple[TraitRecord, ...]:
        granted: list[tuple[ContentRef, Slug]] = []
        if (race := origin.race_ref) is not None:
            granted += [(race, i) for i in self.content.require(race, RaceRecord).traits]
        if (subrace := origin.subrace_ref) is not None:
            granted += [(subrace, i) for i in self.content.require(subrace, SubraceRecord).traits]
        return tuple(
            self.content.require(owner.sibling("traits", i), TraitRecord) for owner, i in granted
        )

    def _racial(self, origin: Origin) -> dict[Ability, int]:
        fixed: list[AbilityBonus] = []
        if origin.race_ref is not None:
            fixed += self.content.require(origin.race_ref, RaceRecord).ability_bonuses
        if origin.subrace_ref is not None:
            fixed += self.content.require(origin.subrace_ref, SubraceRecord).ability_bonuses
        bonuses: dict[Ability, int] = {}
        for bonus in fixed:
            bonuses[bonus.ability] = bonuses.get(bonus.ability, 0) + bonus.bonus
        return bonuses

    def _subclass_choice(self, class_ref: ContentRef, level: int) -> ProgressionChoice | None:
        """Read subclass options from the class because its feature contains only prose."""
        klass = self.content.require(class_ref, ClassRecord)
        if klass.subclass is None or klass.subclass.level != level:
            return None
        refs = [class_ref.sibling("subclasses", index) for index in klass.subclass.options]
        records = [self.content.require(ref, SubclassRecord) for ref in refs]
        return ProgressionChoice(
            id=f"{klass.index}-subclass",
            prompt=f"choose your {records[0].flavor}",
            choose=1,
            options=tuple(
                RecordOption(label=record.name, ref=ref)
                for ref, record in zip(refs, records, strict=True)
            ),
        )

    def _subclass_features(self, origin: Origin, level: int) -> tuple[Slug, ...]:
        if origin.subclass_ref is None:
            return ()
        ref = _level_ref(origin.subclass_ref, level)
        if not self.provides(ref):
            return ()
        return self.content.require(ref, SubclassLevelRecord).features

    def _class_level(self, class_ref: ContentRef, level: int) -> ClassLevelRecord:
        return self.content.require(_level_ref(class_ref, level), ClassLevelRecord)

    def _feature(self, class_ref: ContentRef, index: Slug) -> FeatureRecord:
        return self.content.require(class_ref.sibling("features", index), FeatureRecord)


def compile_ruleset(content: Content) -> Ruleset:
    """Precompute lookups and validate every class ladder at startup."""
    covers: dict[ContentRef, frozenset[Slug]] = {}
    saves: set[ContentRef] = set()
    classes: list[ContentRef] = []
    for ref, record in content.records.items():
        if isinstance(record, EquipmentProficiency):
            covers[ref] = frozenset(record.equipment)
        elif isinstance(record, SaveProficiency):
            saves.add(ref)
        elif isinstance(record, ClassRecord):
            classes.append(ref)
    compiled = PackRuleset(content=content, covers=covers, saves=frozenset(saves))
    for ref in classes:
        for level in range(1, MAX_LEVEL + 1):
            compiled.level(Origin(class_ref=ref), level)
    return compiled


def _level_ref(owner: ContentRef, level: int) -> ContentRef:
    return owner.sibling("levels", f"{owner.index}-{level}")


def _improvements(reached: ClassLevelRecord, held: int) -> int:
    """Reject decreasing cumulative totals as defective content."""
    gained = reached.ability_score_bonuses - held
    if gained < 0:
        raise ValueError(
            f"{reached.index}: ability score improvements fall from {held} to "
            f"{reached.ability_score_bonuses}"
        )
    return gained


def _stats(monster: MonsterRecord) -> StatBlock:
    """Use fixed HP so composing the same scenario is deterministic."""
    return StatBlock(
        attributes=monster.attributes,
        max_hp=monster.hit_points,
        hp=monster.hit_points,
        ac=monster.armor_class,
        condition_immunities=monster.condition_immunities,
        saving_throws=monster.saving_throws,
    )


def _attacks(monster: MonsterRecord) -> tuple[AttackProfile, ...]:
    """Preserve damage modifiers already embedded in monster dice."""
    actions = (*monster.actions, *monster.legendary_actions, *monster.reactions)
    return tuple(
        AttackProfile(name=a.name, to_hit=a.attack_bonus, damage=_summed(a.damage))
        for a in actions
        if isinstance(a, MonsterAttack)
    )


def _summed(rolls: Sequence[DamageRoll]) -> dice.SelfContainedDice | None:
    """Combine damage types until a rule can distinguish them."""
    return " + ".join(roll.dice for roll in rolls) if rolls else None
