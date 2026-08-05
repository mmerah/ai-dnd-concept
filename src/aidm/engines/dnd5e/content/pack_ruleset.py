from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from aidm.core import dice
from aidm.core.packs import Content, ContentMiss, ContentRef, ContentSlug, Record

from ..ruleset import (
    ArchetypeProfile,
    AttackProfile,
    CharacterProfile,
    FeatureProfile,
    LevelProfile,
    Ruleset,
    SpellcastingProfile,
    SpellProfile,
    WeaponProfile,
)
from ..state import MAX_LEVEL, Origin, StatBlock
from ..values import Ability
from .records.base import DamageRoll
from .records.character import (
    AbilityBonus,
    AgentActiveFeatureMechanics,
    BackgroundRecord,
    ClassLevelRecord,
    ClassRecord,
    ClassSpellcasting,
    EngineActiveFeatureMechanics,
    EnginePassiveFeatureMechanics,
    EquipmentProficiency,
    FeatureMechanics,
    FeatureRecord,
    ProgressionChoice,
    ProgressionOnlyFeatureMechanics,
    RaceRecord,
    RecordOption,
    ResourceFeatureMechanics,
    SaveProficiency,
    SubclassLevelRecord,
    SubclassRecord,
    SubraceRecord,
    TraitRecord,
)
from .records.equipment import WeaponRecord
from .records.monsters import MonsterAttack, MonsterRecord
from .records.spells import SpellRecord

COVERS_NOTHING: frozenset[ContentSlug] = frozenset()


@dataclass(frozen=True, slots=True)
class PackRuleset:
    content: Content
    covers: Mapping[ContentRef, frozenset[ContentSlug]]
    saves: frozenset[ContentRef]
    casts: Mapping[ContentRef, tuple[SpellProfile, ...]]

    def character(self, origin: Origin) -> CharacterProfile:
        klass = self.content.require(origin.class_ref, ClassRecord)
        if origin.subclass_ref is not None:
            self._subclass(origin.class_ref, origin.subclass_ref)
        traits = self._traits(origin)
        return CharacterProfile(
            hit_die=klass.hit_die,
            saving_throws=klass.saving_throws,
            proficiencies=self._granted(origin, klass, traits),
            ability_bonuses=self._racial(origin),
            choices=self._origin_choices(origin, klass, traits),
            spellcasting=self._spellcasting(origin.class_ref, klass.spellcasting),
        )

    def level(self, origin: Origin, level: int) -> LevelProfile:
        reached = self._class_level(origin.class_ref, level)
        before = self._class_level(origin.class_ref, level - 1) if level > 1 else None
        indexes = (*reached.features, *self._subclass_features(origin, level))
        refs = tuple(origin.class_ref.sibling("features", index) for index in indexes)
        records = tuple(self._feature_record(ref) for ref in refs)
        for ref, record in zip(refs, records, strict=True):
            if record.class_index != origin.class_ref.index:
                raise ValueError(
                    f"{ref}: feature belongs to class {record.class_index!r}, "
                    f"not {origin.class_ref.index!r}"
                )
        features = tuple(
            self._profile(ref, record)
            for ref, record in zip(refs, records, strict=True)
            if not isinstance(record.mechanics, ProgressionOnlyFeatureMechanics)
        )
        held = before.ability_score_bonuses if before else 0
        return LevelProfile(
            prof_bonus=reached.prof_bonus,
            improvements=_improvements(reached, held),
            spell_slots=reached.spellcasting.spell_slots if reached.spellcasting else {},
            choices=(
                *(choice for record in records for choice in record.choices),
                *self._spell_choices(origin, reached, before),
            ),
            subclass_choice=self._subclass_choice(origin.class_ref, level),
            features=features,
        )

    def feature(self, ref: ContentRef) -> FeatureProfile | ContentMiss:
        record = self.content.get(ref, FeatureRecord)
        if isinstance(record, ContentMiss):
            return record
        return self._profile(ref, record)

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

    def spell(self, ref: ContentRef) -> SpellRecord | ContentMiss:
        return self.content.get(ref, SpellRecord)

    def spell_list(self, origin: Origin) -> tuple[SpellProfile, ...]:
        listed = [*self.casts.get(origin.class_ref, ())]
        if origin.subclass_ref is not None:
            listed += self.casts.get(origin.subclass_ref, ())
        return tuple(sorted(dict.fromkeys(listed), key=lambda s: (s.level, s.name)))

    def klass(self, ref: ContentRef) -> ClassRecord | ContentMiss:
        return self.content.get(ref, ClassRecord)

    def record(self, ref: ContentRef) -> Record | ContentMiss:
        return self.content.record(ref)

    def proficient(
        self, origin: Origin, held: Sequence[ContentSlug], equipment: ContentSlug
    ) -> bool:
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
    ) -> tuple[ContentSlug, ...]:
        granted = list(klass.proficiencies)
        if origin.background_ref is not None:
            background = self.content.require(origin.background_ref, BackgroundRecord)
            granted += background.starting_proficiencies
        granted += [p for trait in traits for p in trait.proficiencies]
        held = (origin.class_ref.sibling("proficiencies", index) for index in granted)
        return tuple(ref.index for ref in held if ref not in self.saves)

    def _traits(self, origin: Origin) -> tuple[TraitRecord, ...]:
        granted: list[tuple[ContentRef, ContentSlug]] = []
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

    def _spellcasting(
        self, class_ref: ContentRef, casting: ClassSpellcasting | None
    ) -> SpellcastingProfile | None:
        if casting is None:
            return None
        first = self._class_level(class_ref, 1).spellcasting
        if first is None:
            raise ValueError(f"{class_ref.index}: a casting class states no level 1 spellcasting")
        return SpellcastingProfile(
            ability=casting.ability,
            slot_recharge=casting.slot_recharge,
            prepares=first.spells_known is None,
        )

    def _spell_choices(
        self, origin: Origin, reached: ClassLevelRecord, before: ClassLevelRecord | None
    ) -> tuple[ProgressionChoice, ...]:
        casting = reached.spellcasting
        if casting is None:
            return ()
        previous = before.spellcasting if before is not None else None
        cantrips_before = None if previous is None else previous.cantrips_known
        spells_before = None if previous is None else previous.spells_known
        top = max(casting.spell_slots, default=0)
        return (
            *self._spell_choice(
                origin,
                reached.level,
                noun="cantrip",
                learned=_learned(reached.index, "cantrip", casting.cantrips_known, cantrips_before),
                levels=range(1),
            ),
            *self._spell_choice(
                origin,
                reached.level,
                noun="spell",
                learned=_learned(reached.index, "spell", casting.spells_known, spells_before),
                levels=range(1, top + 1),
            ),
        )

    def _spell_choice(
        self, origin: Origin, level: int, *, noun: str, learned: int, levels: range
    ) -> tuple[ProgressionChoice, ...]:
        if learned == 0:
            return ()
        return (
            ProgressionChoice(
                id=f"{origin.class_ref.index}-{noun}s-{level}",
                prompt=f"learn {learned} new {noun}{'s' if learned > 1 else ''}",
                choose=learned,
                options=tuple(
                    RecordOption(label=spell.name, ref=spell.ref)
                    for spell in self.spell_list(origin)
                    if spell.level in levels
                ),
            ),
        )

    def _subclass_choice(self, class_ref: ContentRef, level: int) -> ProgressionChoice | None:
        klass = self.content.require(class_ref, ClassRecord)
        if klass.subclass is None or klass.subclass.level != level:
            return None
        refs = [class_ref.sibling("subclasses", index) for index in klass.subclass.options]
        records = [self._subclass(class_ref, ref) for ref in refs]
        return ProgressionChoice(
            id=f"{klass.index}-subclass",
            prompt=f"choose your {records[0].flavor}",
            choose=1,
            options=tuple(
                RecordOption(label=record.name, ref=ref)
                for ref, record in zip(refs, records, strict=True)
            ),
        )

    def _subclass_features(self, origin: Origin, level: int) -> tuple[ContentSlug, ...]:
        if origin.subclass_ref is None:
            return ()
        ref = _level_ref(origin.subclass_ref, level)
        if not self.provides(ref):
            return ()
        reached = self.content.require(ref, SubclassLevelRecord)
        if (
            reached.class_index != origin.class_ref.index
            or reached.subclass_index != origin.subclass_ref.index
            or reached.level != level
        ):
            raise ValueError(f"{ref}: level record does not match its class, subclass, and level")
        return reached.features

    def _class_level(self, class_ref: ContentRef, level: int) -> ClassLevelRecord:
        ref = _level_ref(class_ref, level)
        reached = self.content.require(ref, ClassLevelRecord)
        if reached.class_index != class_ref.index or reached.level != level:
            raise ValueError(f"{ref}: level record does not match its class and level")
        return reached

    def _feature_record(self, ref: ContentRef) -> FeatureRecord:
        return self.content.require(ref, FeatureRecord)

    def _subclass(self, class_ref: ContentRef, subclass_ref: ContentRef) -> SubclassRecord:
        klass = self.content.require(class_ref, ClassRecord)
        subclass = self.content.require(subclass_ref, SubclassRecord)
        offered = () if klass.subclass is None else klass.subclass.options
        if subclass.class_index != class_ref.index or subclass_ref.index not in offered:
            raise ValueError(
                f"{subclass_ref}: subclass is not offered by class {class_ref.index!r}"
            )
        return subclass

    def _profile(self, ref: ContentRef, record: FeatureRecord) -> FeatureProfile:
        self._validate_feature_resource(ref, record)
        for choice in record.choices:
            for option in choice.options:
                if not isinstance(option, RecordOption) or option.ref.collection != "features":
                    continue
                granted = self._feature_record(option.ref)
                if granted.class_index != record.class_index:
                    raise ValueError(
                        f"{record.index}: choice grants {granted.index} from "
                        f"class {granted.class_index}"
                    )
        return FeatureProfile(
            ref=ref,
            name=record.name,
            desc=record.desc,
            mechanics=record.mechanics,
            replaces=self._replacement_refs(ref, record),
        )

    def _validate_feature_resource(self, ref: ContentRef, record: FeatureRecord) -> None:
        mechanics = record.mechanics
        if isinstance(mechanics, ResourceFeatureMechanics):
            if mechanics.resource.pool is not None:
                raise ValueError(f"{record.index}: a resource feature cannot alias another pool")
            return
        if not isinstance(mechanics, AgentActiveFeatureMechanics | EngineActiveFeatureMechanics):
            return
        resource = mechanics.resource
        if resource is None or resource.pool is None:
            return
        owner = self._feature_record(ref.sibling("features", resource.pool))
        if owner.class_index != record.class_index:
            raise ValueError(
                f"{record.index}: resource pool {owner.index} belongs to {owner.class_index}"
            )
        if not isinstance(owner.mechanics, ResourceFeatureMechanics):
            raise ValueError(f"{record.index}: {owner.index} is not a resource feature")
        pool = owner.mechanics.resource
        if (pool.maximum, pool.recharge) != (resource.maximum, resource.recharge):
            raise ValueError(f"{record.index}: resource pool {owner.index} has different rules")

    def _replacement_refs(self, ref: ContentRef, record: FeatureRecord) -> tuple[ContentRef, ...]:
        replacements = tuple(ref.sibling("features", index) for index in record.replaces)
        for replacement in replacements:
            before = self._feature_record(replacement)
            if before.class_index != record.class_index:
                raise ValueError(
                    f"{record.index}: replacement {before.index} belongs to {before.class_index}"
                )
            if before.level >= record.level:
                raise ValueError(
                    f"{record.index}: replacement {before.index} is not from an earlier level"
                )
            if not _same_mechanics_family(record.mechanics, before.mechanics):
                raise ValueError(
                    f"{record.index}: replacement {before.index} has different mechanics"
                )
        return replacements


def _index_spell(
    casts: dict[ContentRef, list[SpellProfile]], ref: ContentRef, record: SpellRecord
) -> None:
    profile = SpellProfile(ref=ref, name=record.name, level=record.level)
    owners = [ref.sibling("classes", index) for index in record.classes]
    owners += [ref.sibling("subclasses", index) for index in record.subclasses]
    for owner in owners:
        casts.setdefault(owner, []).append(profile)


def _learned(index: ContentSlug, noun: str, total: int | None, before: int | None) -> int:
    """Treat a missing known-spell total as prepared casting."""
    if total is None:
        return 0
    learned = total - (before or 0)
    if learned < 0:
        raise ValueError(f"{index}: {noun}s known fall from {before} to {total}")
    return learned


def _same_mechanics_family(current: FeatureMechanics, replaced: FeatureMechanics) -> bool:
    match current, replaced:
        case (
            EngineActiveFeatureMechanics(effect=gained),
            EngineActiveFeatureMechanics(effect=lost),
        ) | (
            EnginePassiveFeatureMechanics(effect=gained),
            EnginePassiveFeatureMechanics(effect=lost),
        ):
            return gained.kind == lost.kind
        case _:
            return current.kind == replaced.kind


def compile_ruleset(content: Content) -> Ruleset:
    covers: dict[ContentRef, frozenset[ContentSlug]] = {}
    saves: set[ContentRef] = set()
    casts: dict[ContentRef, list[SpellProfile]] = {}
    classes: list[ContentRef] = []
    subclasses: list[tuple[ContentRef, SubclassRecord]] = []
    features: list[ContentRef] = []
    for ref, record in content.records.items():
        for choice in _record_choices(record):
            for option in choice.options:
                if isinstance(option, RecordOption) and (miss := content.resolves(option.ref)):
                    raise ValueError(f"{choice.id}: {miss.summary}")
        if isinstance(record, EquipmentProficiency):
            covers[ref] = frozenset(record.equipment)
        elif isinstance(record, SaveProficiency):
            saves.add(ref)
        elif isinstance(record, ClassRecord):
            classes.append(ref)
        elif isinstance(record, SubclassRecord):
            subclasses.append((ref, record))
        elif isinstance(record, FeatureRecord):
            features.append(ref)
        elif isinstance(record, SpellRecord):
            _index_spell(casts, ref, record)
    compiled = PackRuleset(
        content=content,
        covers=covers,
        saves=frozenset(saves),
        casts={owner: tuple(listed) for owner, listed in casts.items()},
    )
    for ref in features:
        if isinstance(miss := compiled.feature(ref), ContentMiss):
            raise ValueError(miss.summary)
    for ref in classes:
        _validate_career(compiled, Origin(class_ref=ref))
    for ref, record in subclasses:
        _validate_career(
            compiled, Origin(class_ref=ref.sibling("classes", record.class_index), subclass_ref=ref)
        )
    return compiled


def _validate_career(compiled: PackRuleset, origin: Origin) -> None:
    """Reject choice IDs that would overwrite a persisted earlier decision."""
    offered = [choice.id for choice in compiled.character(origin).choices]
    for level in range(1, MAX_LEVEL + 1):
        reached = compiled.level(origin, level)
        offered += [choice.id for choice in reached.choices]
        if reached.subclass_choice is not None:
            offered.append(reached.subclass_choice.id)
    if repeated := sorted(id for id, count in Counter(offered).items() if count > 1):
        raise ValueError(f"{origin.class_ref.index}: choice ids offered more than once: {repeated}")


def _record_choices(record: Record) -> tuple[ProgressionChoice, ...]:
    if isinstance(
        record,
        ClassRecord | FeatureRecord | RaceRecord | TraitRecord | BackgroundRecord,
    ):
        return record.choices
    return ()


def _level_ref(owner: ContentRef, level: int) -> ContentRef:
    return owner.sibling("levels", f"{owner.index}-{level}")


def _improvements(reached: ClassLevelRecord, held: int) -> int:
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
        saving_throws=dict(monster.saving_throws),
    )


def _attacks(monster: MonsterRecord) -> tuple[AttackProfile, ...]:
    actions = (*monster.actions, *monster.legendary_actions, *monster.reactions)
    return tuple(
        AttackProfile(name=a.name, to_hit=a.attack_bonus, damage=_summed(a.damage))
        for a in actions
        if isinstance(a, MonsterAttack)
    )


def _summed(rolls: Sequence[DamageRoll]) -> dice.SelfContainedDice | None:
    return " + ".join(roll.dice for roll in rolls) if rolls else None
