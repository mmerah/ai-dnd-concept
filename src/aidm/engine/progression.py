"""Level-up: what a level offers, and what taking it does.

The player decides, through the UI; no LLM role takes part. A subclass is permanent identity rather
than a turn outcome, and there is no "model proposes, Python decides" when the proposal *is* the
outcome. `ui/` renders `pending()` and submits decisions, this module validates them and returns
events, the reducer applies them — the same shape as `screen()` -> `create()` in `growth.py`.

Level records are cumulative snapshots, so the ability score improvements a level grants are the
**diff** of two records; `pending` is the one place that subtraction happens."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random

from ..content import ContentMiss, ContentRef, Library
from ..content.records import (
    AbilityBonus,
    BackgroundRecord,
    BonusOption,
    ChoiceEffect,
    ChoiceOption,
    ClassLevelRecord,
    ClassRecord,
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
)
from ..domain.models import (
    ABILITIES,
    MAX_LEVEL,
    Ability,
    ActorEntity,
    Advancement,
    Attributes,
    CharacterSheet,
    Decisions,
    Event,
    LeveledUp,
    Origin,
    Progression,
    updated,
)
from . import rules

# 5e caps a score at 20, and an improvement is the only thing here that raises one.
MAX_ABILITY_SCORE = 20


@dataclass(frozen=True, slots=True)
class Pick:
    """An option taken, carrying the choice that offered it: the choice is what says whether the
    pick grants a proficiency or only doubles one already held."""

    choice: ProgressionChoice
    option: ChoiceOption


def pending(origin: Origin, level: int, library: Library) -> list[ProgressionChoice]:
    """Every decision reaching `level` requires. Level 1 also carries what comes with a race, a
    subrace, a background and a class rather than with a level."""
    klass = library.require(origin.class_ref, ClassRecord)
    choices = list(_origin_choices(origin, library)) if level == 1 else []
    chosen_now = klass.subclass is not None and klass.subclass.level == level
    if chosen_now and origin.subclass_ref is None:
        choices.append(_subclass_choice(origin.class_ref, klass, library))
    reached = _class_level(origin.class_ref, level, library)
    before = _class_level(origin.class_ref, level - 1, library) if level > 1 else None
    improvements = reached.ability_score_bonuses - (before.ability_score_bonuses if before else 0)
    if improvements > 0:
        choices.append(_ability_choice(level, improvements))
    for index in (*reached.features, *_subclass_features(origin, level, library)):
        ref = origin.class_ref.sibling("features", index)
        choices.extend(library.require(ref, FeatureRecord).choices)
    return choices


def first_level(sheet: CharacterSheet, library: Library) -> Advancement:
    """A character at level 1. Hit points are the whole hit die, not a roll — the 5e rule, and what
    keeps a new game reproducible."""
    origin = sheet.origin
    klass = library.require(origin.class_ref, ClassRecord)
    picks = _taken(pending(origin, 1, library), sheet.decisions)
    attributes = _raised(sheet.starting_attributes, _bonuses(picks, _racial(origin, library)))
    reached = _class_level(origin.class_ref, 1, library)
    progression = Progression(
        origin=_with_subclass(origin, picks),
        level=1,
        prof_bonus=reached.prof_bonus,
        saving_throws=klass.saving_throws,
        proficiencies=_proficiencies(_granted(origin, library), picks),
        spell_slots=_slots(reached),
        decisions=sheet.decisions,
    )
    return Advancement(
        progression=progression, attributes=attributes, hp_gain=_hp_gain(klass.hit_die, attributes)
    )


def advance(actor: ActorEntity, decisions: Decisions, library: Library, rng: Random) -> list[Event]:
    """One level, never several: the diff a level-up applies is only defined a step at a time. The
    hit die is rolled where the trace can see it fall."""
    current = actor.progression
    if current is None:
        raise ValueError(f"{actor.id!r} has no progression to advance")
    if current.level >= MAX_LEVEL:
        raise ValueError(f"already at level {MAX_LEVEL}")
    level = current.level + 1
    picks = _taken(pending(current.origin, level, library), decisions)
    attributes = _raised(actor.stats.attributes, _bonuses(picks, {}))
    reached = _class_level(current.origin.class_ref, level, library)
    klass = library.require(current.origin.class_ref, ClassRecord)
    rolled, event = rules.roll_dice(f"1d{klass.hit_die}", rng)  # a well-formed term by construction
    progression = updated(
        current,
        origin=_with_subclass(current.origin, picks),
        level=level,
        prof_bonus=reached.prof_bonus,
        proficiencies=_proficiencies(current.proficiencies, picks),
        spell_slots=_slots(reached),
        decisions={**current.decisions, **decisions},
    )
    gained = Advancement(
        progression=progression, attributes=attributes, hp_gain=_hp_gain(rolled, attributes)
    )
    return [event, LeveledUp(advancement=gained)]


def _origin_choices(origin: Origin, library: Library) -> list[ProgressionChoice]:
    """A race's and a background's choices are made once, at level 1, along with the class's."""
    choices = list(library.require(origin.class_ref, ClassRecord).choices)
    if origin.race_ref is not None:
        choices += library.require(origin.race_ref, RaceRecord).choices
    if origin.background_ref is not None:
        choices += library.require(origin.background_ref, BackgroundRecord).choices
    return choices + [c for trait in _traits(origin, library) for c in trait.choices]


def _granted(origin: Origin, library: Library) -> tuple[Slug, ...]:
    """Proficiencies a character has without choosing: the class's, the background's, a trait's.

    Save proficiencies are dropped: a class states them twice upstream, and `Progression`'s
    `saving_throws` is the one `rules.save_bonus` reads."""
    granted = list(library.require(origin.class_ref, ClassRecord).proficiencies)
    if origin.background_ref is not None:
        background = library.require(origin.background_ref, BackgroundRecord)
        granted += background.starting_proficiencies
    granted += [p for t in _traits(origin, library) for p in t.proficiencies]
    return tuple(index for index in granted if not _is_save(origin.class_ref, index, library))


def _is_save(owner: ContentRef, index: Slug, library: Library) -> bool:
    ref = owner.sibling("proficiencies", index)  # the wrong_type miss is the test
    return not isinstance(library.get(ref, SaveProficiency), ContentMiss)


def _traits(origin: Origin, library: Library) -> list[TraitRecord]:
    """Every trait a race and its subrace grant. A subrace's are additional, never a replacement."""
    granted: list[tuple[ContentRef, Slug]] = []
    if (race := origin.race_ref) is not None:
        granted += [(race, index) for index in library.require(race, RaceRecord).traits]
    if (subrace := origin.subrace_ref) is not None:
        granted += [(subrace, index) for index in library.require(subrace, SubraceRecord).traits]
    return [library.require(o.sibling("traits", i), TraitRecord) for o, i in granted]


def _racial(origin: Origin, library: Library) -> dict[Ability, int]:
    """A race's fixed bonuses. Applied once, at level 1, to the sheet's base scores."""
    bonuses: dict[Ability, int] = {}
    fixed: list[AbilityBonus] = []
    if origin.race_ref is not None:
        fixed += library.require(origin.race_ref, RaceRecord).ability_bonuses
    if origin.subrace_ref is not None:
        fixed += library.require(origin.subrace_ref, SubraceRecord).ability_bonuses
    for bonus in fixed:
        bonuses[bonus.ability] = bonuses.get(bonus.ability, 0) + bonus.bonus
    return bonuses


def _subclass_choice(
    class_ref: ContentRef, klass: ClassRecord, library: Library
) -> ProgressionChoice:
    """Driven off the class, because the feature announcing it (`martial-archetype`) carries only an
    English sentence — `ClassRecord.subclass` is the pack's one machine-readable option set."""
    if klass.subclass is None:
        raise ValueError(f"class {klass.index!r} has no subclasses to choose from")
    refs = [class_ref.sibling("subclasses", index) for index in klass.subclass.options]
    records = [library.require(ref, SubclassRecord) for ref in refs]
    return ProgressionChoice(
        id=f"{klass.index}-subclass",
        prompt=f"choose your {records[0].flavor}",
        choose=1,
        options=tuple(
            RecordOption(label=record.name, ref=ref)
            for ref, record in zip(refs, records, strict=True)
        ),
    )


def _ability_choice(level: int, improvements: int) -> ProgressionChoice:
    """The one choice a pick may repeat: two +1s on one score is the "+2 to one ability" wording."""
    return ProgressionChoice(
        id=f"ability-scores-{level}",
        prompt="raise one ability score by 2, or two ability scores by 1",
        choose=2 * improvements,
        distinct=False,
        options=tuple(BonusOption(bonus=AbilityBonus(ability=n, bonus=1)) for n in ABILITIES),
    )


def _taken(choices: Sequence[ProgressionChoice], decisions: Decisions) -> list[Pick]:
    """The options the decisions name. A level half-decided is not a level, so the decisions must
    answer every pending choice exactly — no more, no fewer, and nothing outside the option list."""
    offered = {choice.id: choice for choice in choices}
    if sorted(decisions) != sorted(offered):
        raise ValueError(f"decisions {sorted(decisions)} do not answer {sorted(offered)}")
    picks: list[Pick] = []
    for id, keys in decisions.items():
        choice = offered[id]
        if len(keys) != choice.choose:
            raise ValueError(f"choice {id!r} needs {choice.choose} picks, got {len(keys)}")
        if choice.distinct and len(set(keys)) != len(keys):
            raise ValueError(f"choice {id!r} may not repeat a pick: {list(keys)}")
        for key in keys:
            option = choice.option(key)
            if option is None:
                raise ValueError(f"choice {id!r} does not offer {key!r}")
            picks.append(Pick(choice=choice, option=option))
    return picks


def _bonuses(picks: Sequence[Pick], base: Mapping[Ability, int]) -> dict[Ability, int]:
    bonuses = dict(base)
    for pick in picks:
        if isinstance(pick.option, BonusOption):
            bonus = pick.option.bonus
            bonuses[bonus.ability] = bonuses.get(bonus.ability, 0) + bonus.bonus
    return bonuses


def _proficiencies(held: Sequence[Slug], picks: Sequence[Pick]) -> tuple[Slug, ...]:
    """Deduplicated, and a doubling pick must name something already held: expertise offers all 18
    skills whether the character has them or not, so treating it as a grant would hand out a
    proficiency the pack never gave them. Doubling itself is not modelled — the pick lives on in
    `decisions` alone."""
    granted = tuple(dict.fromkeys([*held, *_proficiency_picks(picks, "grant")]))
    unheld = sorted(set(_proficiency_picks(picks, "double")) - set(granted))
    if unheld:
        raise ValueError(f"cannot double a proficiency the character does not hold: {unheld}")
    return granted


def _proficiency_picks(picks: Sequence[Pick], effect: ChoiceEffect) -> list[Slug]:
    return [
        p.option.ref.index
        for p in picks
        if p.choice.effect == effect
        and isinstance(p.option, RecordOption)
        and p.option.ref.collection == "proficiencies"
    ]


def _with_subclass(origin: Origin, picks: Sequence[Pick]) -> Origin:
    """A subclass is chosen once and never unchosen, so a level that offered none keeps the one the
    character already has."""
    chosen = (p.option.ref for p in picks if isinstance(p.option, RecordOption))
    ref = next((r for r in chosen if r.collection == "subclasses"), None)
    return origin if ref is None else updated(origin, subclass_ref=ref)


def _slots(reached: ClassLevelRecord) -> Mapping[int, int]:
    return reached.spellcasting.spell_slots if reached.spellcasting else {}


def _raised(attributes: Attributes, bonuses: Mapping[Ability, int]) -> Attributes:
    """Raising past 20 is refused, not clamped: an improvement is permanent and a pick the engine
    silently swallowed would cost the player a choice they can never make again."""
    raised = {name: attributes[name] + bonus for name, bonus in bonuses.items()}
    over = sorted(f"{name} {score}" for name, score in raised.items() if score > MAX_ABILITY_SCORE)
    if over:
        raise ValueError(f"no ability may exceed {MAX_ABILITY_SCORE}: {', '.join(over)}")
    return updated(attributes, **raised)


def _hp_gain(rolled: int, attributes: Attributes) -> int:
    """At least 1: a d6 class with a poor constitution would otherwise gain nothing for a level."""
    return max(1, rolled + rules.modifier(attributes, "constitution"))


def _subclass_features(origin: Origin, level: int, library: Library) -> tuple[Slug, ...]:
    """A subclass grants features at a handful of levels only, so no record for this one is an
    answer, not a miss — but a record that is not a subclass level is a broken pack."""
    if origin.subclass_ref is None:
        return ()
    ref = _level_ref(origin.subclass_ref, level)
    if library.resolves(ref) is not None:
        return ()
    return library.require(ref, SubclassLevelRecord).features


def _class_level(class_ref: ContentRef, level: int, library: Library) -> ClassLevelRecord:
    return library.require(_level_ref(class_ref, level), ClassLevelRecord)


def _level_ref(owner: ContentRef, level: int) -> ContentRef:
    """A level record's index is its owner's plus the level, which is what makes a level a lookup
    rather than a scan of all 290."""
    return owner.sibling("levels", f"{owner.index}-{level}")
