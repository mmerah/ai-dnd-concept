"""Level-up: what a level offers, and what taking it does.

The player decides, through the UI; no LLM role takes part. A subclass is permanent identity rather
than a turn outcome, and there is no "model proposes, Python decides" when the proposal *is* the
outcome. `ui/` renders `pending()` and submits decisions, this module validates them and returns
events, the reducer applies them — the same shape as `screen()` -> `create()` in `growth.py`.

Progression *rules* only: which choices a level asks for, what a pick may and may not do, and the
arithmetic of a raised score. Where those facts live in a pack is `ruleset.py`'s question."""

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

# 5e caps a score at 20, and an improvement is the only thing here that raises one.
MAX_ABILITY_SCORE = 20


@dataclass(frozen=True, slots=True)
class Pick:
    """An option taken, carrying the choice that offered it: the choice is what says whether the
    pick grants a proficiency or only doubles one already held."""

    choice: ProgressionChoice
    option: ChoiceOption


def pending(origin: Origin, level: int, ruleset: ProgressionRules) -> list[ProgressionChoice]:
    """Every decision reaching `level` requires. Level 1 also carries what comes with a race, a
    subrace, a background and a class rather than with a level."""
    reached = ruleset.level(origin, level)
    choices = list(ruleset.character(origin).choices) if level == 1 else []
    # Chosen once and never unchosen, so a level that offers one again offers nothing.
    if reached.subclass_choice is not None and origin.subclass_ref is None:
        choices.append(reached.subclass_choice)
    if reached.improvements > 0:
        choices.append(_ability_choice(level, reached.improvements))
    return [*choices, *reached.choices]


def first_level(sheet: CharacterSheet, ruleset: ProgressionRules) -> Advancement:
    """A character at level 1. Hit points are the whole hit die, not a roll — the 5e rule, and what
    keeps a new game reproducible."""
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
    """One level, never several: the diff a level-up applies is only defined a step at a time. The
    hit die is rolled where the trace can see it fall."""
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
    rolled, event = rules.roll_dice(f"1d{hit_die}", rng)  # a well-formed term by construction
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
