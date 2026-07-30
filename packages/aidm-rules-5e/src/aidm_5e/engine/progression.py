from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random

from ..content.records.base import Collection, ContentRef
from ..content.records.character import (
    AbilityBonus,
    BonusOption,
    ChoiceEffect,
    ChoiceOption,
    ProgressionChoice,
    RecordOption,
)
from ..domain.models.entities import ActorEntity
from ..domain.models.events import Event, LeveledUp, LevelUpAvailable
from ..domain.models.progression import MAX_LEVEL, Advancement, Decisions, Origin, Progression
from ..domain.models.state import CharacterSheet
from ..utils.models import ABILITIES, Ability, Attributes, Frozen, Slug, updated
from . import features as class_features
from . import rules, spells
from .ruleset import CharacterProfile, FeatureProfile, LevelProfile, ProgressionRules

MAX_ABILITY_SCORE = 20


@dataclass(frozen=True, slots=True)
class Pick:
    choice: ProgressionChoice
    option: ChoiceOption


@dataclass(frozen=True, slots=True)
class SpellSlotChange:
    slot_level: int
    before: int
    after: int


@dataclass(frozen=True, slots=True)
class LevelBenefits:
    level: int
    hit_die: int
    retroactive_hp_gain: int
    prof_bonus_before: int
    prof_bonus_after: int
    spell_slot_changes: tuple[SpellSlotChange, ...]
    features: tuple[FeatureProfile, ...]


class LevelUpPreview(Frozen):
    benefits: LevelBenefits
    choices: tuple[ProgressionChoice, ...]


@dataclass(frozen=True, slots=True)
class ChoiceSelection:
    prompt: str
    labels: tuple[str, ...]


class AdvancementPlan(Frozen):
    benefits: LevelBenefits
    selections: tuple[ChoiceSelection, ...]
    progression: Progression
    attributes: Attributes


def _advancing(actor: ActorEntity) -> tuple[Progression, int]:
    current = actor.progression
    if current is None:
        raise ValueError(f"{actor.id!r} has no progression to advance")
    if current.level >= MAX_LEVEL:
        raise ValueError(f"already at level {MAX_LEVEL}")
    return current, current.level + 1


def offer(actor: ActorEntity) -> list[Event]:
    current, _ = _advancing(actor)
    return [] if current.level_up_available else [LevelUpAvailable()]


def pending(origin: Origin, level: int, ruleset: ProgressionRules) -> list[ProgressionChoice]:
    reached = ruleset.level(origin, level)
    choices = list(ruleset.character(origin).choices) if level == 1 else []
    if reached.subclass_choice is not None and origin.subclass_ref is None:
        choices.append(reached.subclass_choice)
    if reached.improvements > 0:
        choices.append(_ability_choice(level, reached.improvements))
    return [*choices, *reached.choices]


def preview(actor: ActorEntity, ruleset: ProgressionRules) -> LevelUpPreview:
    """Show the level before any choice is made, so no ability score has risen yet."""
    current, level = _advancing(actor)
    reached = ruleset.level(current.origin, level)
    return LevelUpPreview(
        benefits=_benefits(
            current,
            ruleset.character(current.origin),
            reached,
            reached.features,
            retroactive_hp_gain=0,
        ),
        choices=_available(
            current, actor.stats.attributes, pending(current.origin, level, ruleset)
        ),
    )


def first_level(sheet: CharacterSheet, ruleset: ProgressionRules) -> Advancement:
    """Use the full hit die at level 1 for deterministic starting HP."""
    origin = sheet.origin
    character = ruleset.character(origin)
    picks = _taken(pending(origin, 1, ruleset), sheet.decisions)
    attributes = _raised(sheet.starting_attributes, _bonuses(picks, character.ability_bonuses))
    origin = _with_subclass(origin, picks)
    reached = ruleset.level(origin, 1)
    features, feature_resources = class_features.acquire(
        (),
        {},
        (*reached.features, *_picked_features(picks, ruleset)),
        ruleset=ruleset,
        class_level=1,
        attributes=attributes,
    )
    progression = Progression(
        origin=origin,
        level=1,
        prof_bonus=reached.prof_bonus,
        saving_throws=character.saving_throws,
        proficiencies=_proficiencies(character.proficiencies, picks),
        spell_slots=spells.slots({}, reached.spell_slots, character.spellcasting),
        chosen_spells=tuple(_picked(picks, "spells")),
        decisions=sheet.decisions,
        features=features,
        feature_resources=feature_resources,
    )
    return Advancement(
        progression=progression,
        attributes=attributes,
        hp_gain=_hp_gain(character.hit_die, attributes),
    )


def advance(
    actor: ActorEntity, decisions: Decisions, ruleset: ProgressionRules, rng: Random
) -> list[Event]:
    planned = plan(actor, decisions, ruleset)
    rolled, event = rules.roll_dice(f"1d{planned.benefits.hit_die}", rng)
    gained = Advancement(
        progression=planned.progression,
        attributes=planned.attributes,
        hp_gain=_hp_gain(rolled, planned.attributes) + planned.benefits.retroactive_hp_gain,
    )
    return [event, LeveledUp(advancement=gained)]


def plan(actor: ActorEntity, decisions: Decisions, ruleset: ProgressionRules) -> AdvancementPlan:
    current, level = _advancing(actor)
    origin = current.origin
    choices = _available(current, actor.stats.attributes, pending(origin, level, ruleset))
    picks = _taken(choices, decisions)
    attributes = _raised(actor.stats.attributes, _bonuses(picks, {}))
    origin = _with_subclass(origin, picks)
    reached = ruleset.level(origin, level)
    character = ruleset.character(origin)
    grants = (*reached.features, *_picked_features(picks, ruleset))
    features, feature_resources = class_features.acquire(
        current.features,
        current.feature_resources,
        grants,
        ruleset=ruleset,
        class_level=level,
        attributes=attributes,
    )
    return AdvancementPlan(
        benefits=_benefits(
            current,
            character,
            reached,
            grants,
            retroactive_hp_gain=_retroactive_hp_gain(
                current.level, actor.stats.attributes, attributes
            ),
        ),
        selections=_selections(choices, picks),
        progression=updated(
            current,
            origin=origin,
            level=level,
            level_up_available=False,
            prof_bonus=reached.prof_bonus,
            proficiencies=_proficiencies(current.proficiencies, picks),
            spell_slots=spells.slots(
                current.spell_slots, reached.spell_slots, character.spellcasting
            ),
            chosen_spells=tuple(dict.fromkeys([*current.chosen_spells, *_picked(picks, "spells")])),
            decisions={**current.decisions, **decisions},
            features=features,
            feature_resources=feature_resources,
        ),
        attributes=attributes,
    )


def _ability_choice(level: int, improvements: int) -> ProgressionChoice:
    return ProgressionChoice(
        id=f"ability-scores-{level}",
        prompt="raise one ability score by 2, or two ability scores by 1",
        choose=2 * improvements,
        distinct=False,
        options=tuple(BonusOption(bonus=AbilityBonus(ability=n, bonus=1)) for n in ABILITIES),
    )


def _taken(choices: Sequence[ProgressionChoice], decisions: Decisions) -> list[Pick]:
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


def _available(
    current: Progression,
    attributes: Attributes,
    choices: Sequence[ProgressionChoice],
) -> tuple[ProgressionChoice, ...]:
    available: list[ProgressionChoice] = []
    held_records = set(current.features) | set(current.chosen_spells)
    held_proficiencies = set(current.proficiencies)
    for choice in choices:
        options = tuple(
            option
            for option in choice.options
            if _option_available(choice, option, attributes, held_records, held_proficiencies)
        )
        enough = len(options) >= choice.choose if choice.distinct else bool(options)
        if choice.choose > 0 and not enough:
            raise ValueError(f"choice {choice.id!r} has too few legal options")
        available.append(updated(choice, options=options))
    return tuple(available)


def _option_available(
    choice: ProgressionChoice,
    option: ChoiceOption,
    attributes: Attributes,
    held_records: set[ContentRef],
    held_proficiencies: set[Slug],
) -> bool:
    if isinstance(option, BonusOption):
        return attributes[option.bonus.ability] < MAX_ABILITY_SCORE
    if option.ref.collection in ("features", "spells"):
        return option.ref not in held_records
    if choice.effect == "double" and option.ref.collection == "proficiencies":
        return option.ref.index in held_proficiencies
    return True


def _bonuses(picks: Sequence[Pick], base: Mapping[Ability, int]) -> dict[Ability, int]:
    bonuses = dict(base)
    for pick in picks:
        if isinstance(pick.option, BonusOption):
            bonus = pick.option.bonus
            bonuses[bonus.ability] = bonuses.get(bonus.ability, 0) + bonus.bonus
    return bonuses


def _proficiencies(held: Sequence[Slug], picks: Sequence[Pick]) -> tuple[Slug, ...]:
    """Reject expertise in an unheld proficiency; doubling remains in decisions."""
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


def _picked(picks: Sequence[Pick], collection: Collection) -> list[ContentRef]:
    return [
        pick.option.ref
        for pick in picks
        if pick.choice.effect == "grant"
        and isinstance(pick.option, RecordOption)
        and pick.option.ref.collection == collection
    ]


def _with_subclass(origin: Origin, picks: Sequence[Pick]) -> Origin:
    ref = next(iter(_picked(picks, "subclasses")), None)
    return origin if ref is None else updated(origin, subclass_ref=ref)


def _picked_features(
    picks: Sequence[Pick], ruleset: ProgressionRules
) -> tuple[FeatureProfile, ...]:
    return tuple(class_features.profile_of(ref, ruleset) for ref in _picked(picks, "features"))


def _raised(attributes: Attributes, bonuses: Mapping[Ability, int]) -> Attributes:
    """Reject rather than clamp so a permanent pick is not silently lost."""
    raised = {name: attributes[name] + bonus for name, bonus in bonuses.items()}
    over = sorted(f"{name} {score}" for name, score in raised.items() if score > MAX_ABILITY_SCORE)
    if over:
        raise ValueError(f"no ability may exceed {MAX_ABILITY_SCORE}: {', '.join(over)}")
    return updated(attributes, **raised)


def _hp_gain(rolled: int, attributes: Attributes) -> int:
    return max(1, rolled + rules.modifier(attributes, "constitution"))


def _retroactive_hp_gain(levels: int, before: Attributes, after: Attributes) -> int:
    gained_modifier = rules.modifier(after, "constitution") - rules.modifier(before, "constitution")
    if gained_modifier < 0:
        raise ValueError("a level-up cannot reduce the constitution modifier")
    return levels * gained_modifier


def _spell_slot_changes(
    current: Progression, after: Mapping[int, int]
) -> tuple[SpellSlotChange, ...]:
    before = {level: state.maximum for level, state in current.spell_slots.items()}
    return tuple(
        SpellSlotChange(
            slot_level=level,
            before=before.get(level, 0),
            after=after.get(level, 0),
        )
        for level in sorted(set(before) | set(after))
        if before.get(level, 0) != after.get(level, 0)
    )


def _benefits(
    current: Progression,
    character: CharacterProfile,
    reached: LevelProfile,
    features: Sequence[FeatureProfile],
    *,
    retroactive_hp_gain: int,
) -> LevelBenefits:
    return LevelBenefits(
        level=current.level + 1,
        hit_die=character.hit_die,
        retroactive_hp_gain=retroactive_hp_gain,
        prof_bonus_before=current.prof_bonus,
        prof_bonus_after=reached.prof_bonus,
        spell_slot_changes=_spell_slot_changes(current, reached.spell_slots),
        features=tuple(features),
    )


def _selections(
    choices: Sequence[ProgressionChoice], picks: Sequence[Pick]
) -> tuple[ChoiceSelection, ...]:
    return tuple(
        ChoiceSelection(
            prompt=choice.prompt,
            labels=tuple(pick.option.label for pick in picks if pick.choice.id == choice.id),
        )
        for choice in choices
    )
