"""Compiling loaded packs into the ruleset the engine reads.

The one module that knows both shapes, so storage-shaped questions are answered here and nowhere
else: a level record is a cumulative total, a proficiency lists the equipment it covers, a monster
carries four action lists. `engine/` sees only the profiles that come out.

Derived, never authored. `scripts/srd/` stays the boundary that narrows upstream into records, and
this reads those records; a third representation only risks drift if something writes it by hand.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..content import (
    Collection,
    ContentMiss,
    ContentRef,
    Library,
    MonsterAttack,
    MonsterRecord,
    Pack,
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
    Slug,
    SubclassLevelRecord,
    SubclassRecord,
    SubraceRecord,
    TraitRecord,
    WeaponRecord,
)
from ..domain.models import MAX_LEVEL, Ability, Origin, StatBlock
from ..utils import dice
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
    """A `Ruleset` over loaded packs. Conformance is structural, checked at `compile_ruleset`'s
    return; nothing here is declared against the protocol twice."""

    library: Library
    # Precomputed because each replaced a per-turn scan: what a proficiency covers, and which
    # proficiencies restate a class's saving throws.
    covers: Mapping[ContentRef, frozenset[Slug]]
    saves: frozenset[ContentRef]

    def character(self, origin: Origin) -> CharacterProfile:
        klass = self.library.require(origin.class_ref, ClassRecord)
        traits = self._traits(origin)
        return CharacterProfile(
            hit_die=klass.hit_die,
            saving_throws=klass.saving_throws,
            proficiencies=self._granted(origin, klass, traits),
            ability_bonuses=self._racial(origin),
            choices=self._origin_choices(origin, klass, traits),
        )

    def level(self, origin: Origin, level: int) -> LevelProfile:
        """A level record is a running total, so what this level *adds* is the diff with the one
        before it — the subtraction that must happen exactly once, and happens here."""
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
        record = self.library.get(ref, MonsterRecord)
        if isinstance(record, ContentMiss):
            return None
        return ArchetypeProfile(stats=_stats(record), attacks=_attacks(record))

    def weapon(self, ref: ContentRef) -> WeaponProfile | None:
        record = self.library.get(ref, WeaponRecord)
        if isinstance(record, ContentMiss):
            return None
        return WeaponProfile(
            index=record.index,
            damage=None if record.damage is None else record.damage.dice,
            ranged=record.weapon_range == "Ranged",
            finesse="finesse" in record.properties,
        )

    def proficient(self, origin: Origin, held: Sequence[Slug], equipment: Slug) -> bool:
        refs = (origin.class_ref.sibling("proficiencies", index) for index in held)
        return any(equipment in self.covers.get(ref, COVERS_NOTHING) for ref in refs)

    def provides(self, ref: ContentRef) -> bool:
        return self.library.resolves(ref) is None

    def _origin_choices(
        self, origin: Origin, klass: ClassRecord, traits: Sequence[TraitRecord]
    ) -> tuple[ProgressionChoice, ...]:
        """A race's and a background's choices are made once, at level 1, along with the class's."""
        choices = list(klass.choices)
        if origin.race_ref is not None:
            choices += self.library.require(origin.race_ref, RaceRecord).choices
        if origin.background_ref is not None:
            choices += self.library.require(origin.background_ref, BackgroundRecord).choices
        return tuple(choices + [c for trait in traits for c in trait.choices])

    def _granted(
        self, origin: Origin, klass: ClassRecord, traits: Sequence[TraitRecord]
    ) -> tuple[Slug, ...]:
        """Proficiencies a character has without choosing: the class's, the background's, a trait's.
        Save proficiencies are dropped — a class states them twice upstream, and one fact in two
        fields is one that can disagree with itself."""
        granted = list(klass.proficiencies)
        if origin.background_ref is not None:
            background = self.library.require(origin.background_ref, BackgroundRecord)
            granted += background.starting_proficiencies
        granted += [p for trait in traits for p in trait.proficiencies]
        held = (origin.class_ref.sibling("proficiencies", index) for index in granted)
        return tuple(ref.index for ref in held if ref not in self.saves)

    def _traits(self, origin: Origin) -> tuple[TraitRecord, ...]:
        """Every trait a race and its subrace grant. A subrace's are additional, never a
        replacement."""
        granted: list[tuple[ContentRef, Slug]] = []
        if (race := origin.race_ref) is not None:
            granted += [(race, i) for i in self.library.require(race, RaceRecord).traits]
        if (subrace := origin.subrace_ref) is not None:
            granted += [(subrace, i) for i in self.library.require(subrace, SubraceRecord).traits]
        return tuple(
            self.library.require(owner.sibling("traits", i), TraitRecord) for owner, i in granted
        )

    def _racial(self, origin: Origin) -> dict[Ability, int]:
        """A race's fixed bonuses, applied once to the sheet's base scores."""
        fixed: list[AbilityBonus] = []
        if origin.race_ref is not None:
            fixed += self.library.require(origin.race_ref, RaceRecord).ability_bonuses
        if origin.subrace_ref is not None:
            fixed += self.library.require(origin.subrace_ref, SubraceRecord).ability_bonuses
        bonuses: dict[Ability, int] = {}
        for bonus in fixed:
            bonuses[bonus.ability] = bonuses.get(bonus.ability, 0) + bonus.bonus
        return bonuses

    def _subclass_choice(self, class_ref: ContentRef, level: int) -> ProgressionChoice | None:
        """Driven off the class: the feature announcing it (`martial-archetype`) carries only an
        English sentence, so `ClassRecord.subclass` is the one machine-readable option set."""
        klass = self.library.require(class_ref, ClassRecord)
        if klass.subclass is None or klass.subclass.level != level:
            return None
        refs = [class_ref.sibling("subclasses", index) for index in klass.subclass.options]
        records = [self.library.require(ref, SubclassRecord) for ref in refs]
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
        """A subclass grants features at a handful of levels only, so no record for this one is an
        answer, not a miss — but a record that is not a subclass level is a broken pack."""
        if origin.subclass_ref is None:
            return ()
        ref = _level_ref(origin.subclass_ref, level)
        if not self.provides(ref):
            return ()
        return self.library.require(ref, SubclassLevelRecord).features

    def _class_level(self, class_ref: ContentRef, level: int) -> ClassLevelRecord:
        return self.library.require(_level_ref(class_ref, level), ClassLevelRecord)

    def _feature(self, class_ref: ContentRef, index: Slug) -> FeatureRecord:
        return self.library.require(class_ref.sibling("features", index), FeatureRecord)


def compile_ruleset(library: Library) -> Ruleset:
    """Read the packs once, at load. Both indexes answer a question the engine asks every turn about
    data frozen until the next level-up, and every class ladder is walked here so an unplayable
    class is a startup failure rather than a dropped turn three levels into a campaign."""
    covers: dict[ContentRef, frozenset[Slug]] = {}
    saves: set[ContentRef] = set()
    for pack in library.packs:
        for record in pack.proficiencies.values():
            ref = _ref(pack, "proficiencies", record.index)
            if isinstance(record, EquipmentProficiency):
                covers[ref] = frozenset(record.equipment)
            elif isinstance(record, SaveProficiency):
                saves.add(ref)
    compiled = PackRuleset(library=library, covers=covers, saves=frozenset(saves))
    for pack in library.packs:
        for klass in pack.classes.values():
            origin = Origin(class_ref=_ref(pack, "classes", klass.index))
            for level in range(1, MAX_LEVEL + 1):
                compiled.level(origin, level)
    return compiled


def _ref(pack: Pack, collection: Collection, index: Slug) -> ContentRef:
    """A ref to a record read out of the pack holding it: a collection is keyed by index alone, and
    an index alone addresses nothing."""
    return ContentRef(pack=pack.manifest.id, collection=collection, index=index)


def _level_ref(owner: ContentRef, level: int) -> ContentRef:
    """A level record's index is its owner's plus the level, which is what makes reaching one a
    lookup rather than a scan of all 290."""
    return owner.sibling("levels", f"{owner.index}-{level}")


def _improvements(reached: ClassLevelRecord, held: int) -> int:
    """What this level adds to a cumulative total. A total that *falls* is a defective ladder, never
    a level that takes an improvement away — refused here, where the load-time walk of every class
    reaches it, rather than quietly offering the player nothing. `scripts/srd/corrections.py` is
    where a published defect is corrected; the SRD rogue was one."""
    gained = reached.ability_score_bonuses - held
    if gained < 0:
        raise ValueError(
            f"{reached.index}: ability score improvements fall from {held} to "
            f"{reached.ability_score_bonuses}"
        )
    return gained


def _stats(monster: MonsterRecord) -> StatBlock:
    """Fixed hit points, not `hit_points_roll`: a rolled value is unrecomputable, so the same
    scenario would load differently each time."""
    return StatBlock(
        attributes=monster.attributes,
        max_hp=monster.hit_points,
        hp=monster.hit_points,
        ac=monster.armor_class,
        condition_immunities=monster.condition_immunities,
        saving_throws=monster.saving_throws,
    )


def _attacks(monster: MonsterRecord) -> tuple[AttackProfile, ...]:
    """Every action carrying a to-hit, wherever in the economy it sits. A record's damage dice
    already include its own modifier — the goblin's scimitar is `1d6+2` — so nothing is added."""
    actions = (*monster.actions, *monster.legendary_actions, *monster.reactions)
    return tuple(
        AttackProfile(name=a.name, to_hit=a.attack_bonus, damage=_summed(a.damage))
        for a in actions
        if isinstance(a, MonsterAttack)
    )


def _summed(rolls: Sequence[DamageRoll]) -> dice.SelfContainedDice | None:
    """Summed across damage types: nothing resists one yet, so keeping them apart would be a
    distinction no rule could act on."""
    return " + ".join(roll.dice for roll in rolls) if rolls else None
