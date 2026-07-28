from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random

from ..content.records import (
    AbilityBonus,
    BonusOption,
    ChoiceEffect,
    ChoiceOption,
    ProgressionChoice,
    RecordOption,
    Slug,
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
from .ruleset import ProgressionRules

MAX_ABILITY_SCORE = 20


@dataclass(frozen=True, slots=True)
class Pick:
    choice: ProgressionChoice
    option: ChoiceOption


def pending(origin: Origin, level: int, ruleset: ProgressionRules) -> list[ProgressionChoice]:
    reached = ruleset.level(origin, level)
    choices = list(ruleset.character(origin).choices) if level == 1 else []
    if reached.subclass_choice is not None and origin.subclass_ref is None:
        choices.append(reached.subclass_choice)
    if reached.improvements > 0:
        choices.append(_ability_choice(level, reached.improvements))
    return [*choices, *reached.choices]


def first_level(sheet: CharacterSheet, ruleset: ProgressionRules) -> Advancement:
    """Use the full hit die at level 1 for deterministic starting HP."""
    origin = sheet.origin
    character = ruleset.character(origin)
    picks = _taken(pending(origin, 1, ruleset), sheet.decisions)
    attributes = _raised(sheet.starting_attributes, _bonuses(picks, character.ability_bonuses))
    reached = ruleset.level(origin, 1)
    progression = Progression(
        origin=_with_subclass(origin, picks),
        level=1,
        prof_bonus=reached.prof_bonus,
        saving_throws=character.saving_throws,
        proficiencies=_proficiencies(character.proficiencies, picks),
        spell_slots=reached.spell_slots,
        decisions=sheet.decisions,
    )
    return Advancement(
        progression=progression,
        attributes=attributes,
        hp_gain=_hp_gain(character.hit_die, attributes),
    )


def advance(
    actor: ActorEntity, decisions: Decisions, ruleset: ProgressionRules, rng: Random
) -> list[Event]:
    current = actor.progression
    if current is None:
        raise ValueError(f"{actor.id!r} has no progression to advance")
    if current.level >= MAX_LEVEL:
        raise ValueError(f"already at level {MAX_LEVEL}")
    level = current.level + 1
    origin = current.origin
    picks = _taken(pending(origin, level, ruleset), decisions)
    attributes = _raised(actor.stats.attributes, _bonuses(picks, {}))
    reached = ruleset.level(origin, level)
    hit_die = ruleset.character(origin).hit_die
    rolled, event = rules.roll_dice(f"1d{hit_die}", rng)
    progression = updated(
        current,
        origin=_with_subclass(origin, picks),
        level=level,
        prof_bonus=reached.prof_bonus,
        proficiencies=_proficiencies(current.proficiencies, picks),
        spell_slots=reached.spell_slots,
        decisions={**current.decisions, **decisions},
    )
    gained = Advancement(
        progression=progression, attributes=attributes, hp_gain=_hp_gain(rolled, attributes)
    )
    return [event, LeveledUp(advancement=gained)]


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


def _with_subclass(origin: Origin, picks: Sequence[Pick]) -> Origin:
    chosen = (p.option.ref for p in picks if isinstance(p.option, RecordOption))
    ref = next((r for r in chosen if r.collection == "subclasses"), None)
    return origin if ref is None else updated(origin, subclass_ref=ref)


def _raised(attributes: Attributes, bonuses: Mapping[Ability, int]) -> Attributes:
    """Reject rather than clamp so a permanent pick is not silently lost."""
    raised = {name: attributes[name] + bonus for name, bonus in bonuses.items()}
    over = sorted(f"{name} {score}" for name, score in raised.items() if score > MAX_ABILITY_SCORE)
    if over:
        raise ValueError(f"no ability may exceed {MAX_ABILITY_SCORE}: {', '.join(over)}")
    return updated(attributes, **raised)


def _hp_gain(rolled: int, attributes: Attributes) -> int:
    """Grant at least one HP per level."""
    return max(1, rolled + rules.modifier(attributes, "constitution"))
