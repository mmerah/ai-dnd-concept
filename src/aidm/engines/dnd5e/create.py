from collections.abc import Container, Iterator, Mapping, Sequence
from random import Random
from typing import Literal

from pydantic import TypeAdapter, ValidationError

from aidm.content.authored import CharacterOverlay, CharacterProfile, CreatedCharacter
from aidm.engines.counters import Counter
from aidm.engines.loader import Creation
from aidm.state.base import Frozen, Slug
from aidm.state.creation import (
    AllocationStep,
    CreationOption,
    CreationStep,
    Picks,
    Step,
    allocated,
    check_picks,
    picked,
)
from aidm.state.packs import CollectionName, Content, ContentRef, Record, is_int_fact

from . import equipment, pools, spells
from .content import SUBCLASSES, lookup
from .mechanics import ABILITIES, Sheet, modifier

_COLLECTION_STEPS: tuple[tuple[Slug, CollectionName, str], ...] = (
    ("race", "races", "Choose a race"),
    ("class", "classes", "Choose a class"),
    ("background", "backgrounds", "Choose a background"),
)
# The three generation methods, authored because 5e-database ships no such table: it has no
# standard array, no point-buy ladder, and nothing that says a score starts at 8.
_ARRAY = (15, 14, 13, 12, 10, 8)
# SRD point buy: every score starts at 8, and the last two points cost double.
_POINT_COST: Mapping[int, int] = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
_POINTS = 27
_BOUGHT = (min(_POINT_COST), max(_POINT_COST))
_METHOD_STEP = CreationStep(
    id="ability-method",
    prompt="How are the ability scores rolled up?",
    options=(
        CreationOption(id="roll", label="Roll", detail="4d6 drop the lowest, six times"),
        CreationOption(
            id="point-buy", label="Point buy", detail=f"{_POINTS} points, every score 8 to 15"
        ),
        CreationOption(
            id="standard-array",
            label="Standard array",
            detail=", ".join(str(score) for score in _ARRAY),
        ),
    ),
)
# A rolled spread is not a pick, and `create` is pure: the seed travels instead, and the same seed
# always rebuilds the same six scores. Typing another number is the reroll.
_SEED_STEP = AllocationStep(
    id="ability-seed",
    prompt="Roll with any number; change it to roll again",
    entries=(CreationOption(id="seed", label="Seed"),),
    minimum=1,
    maximum=999_999,
)
_ABILITY_ENTRIES = tuple(
    CreationOption(id=ability, label=ability.capitalize()) for ability in ABILITIES
)

# Index is the spell level a step picks from: cantrips, then the level-1 spells.
_SPELL_KINDS = ("cantrips", "level 1 spells")


class _AbilityBonus(Frozen):
    """One entry of a race's `ability-bonuses` fact; `choice` entries let the player pick."""

    ability: Literal[
        "strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma", "choice"
    ]
    bonus: int
    choose: int = 0


_ABILITY_BONUSES: TypeAdapter[tuple[_AbilityBonus, ...]] = TypeAdapter(tuple[_AbilityBonus, ...])


class Dnd5eCreation(Creation):
    def __init__(self, content: Content) -> None:
        self.content = content
        self._offered: dict[Slug, dict[str, ContentRef]] = {
            step_id: {ref.index: ref for ref in content.records if ref.collection == collection}
            for step_id, collection, _ in _COLLECTION_STEPS
        }
        self._static = (
            *(
                CreationStep(
                    id=step_id,
                    prompt=prompt,
                    options=tuple(
                        CreationOption(id=ref.index, label=record.name)
                        for ref, record in sorted(
                            (
                                (ref, self.content.require(ref))
                                for ref in self._offered[step_id].values()
                            ),
                            key=lambda pair: pair[1].name,
                        )
                    ),
                )
                for step_id, _, prompt in _COLLECTION_STEPS
            ),
            _METHOD_STEP,
        )
        for race_ref in self._offered["race"].values():
            _ = _race_bonuses(content.require(race_ref))
        subraces: dict[Slug, list[tuple[ContentRef, Record]]] = {}
        for ref in content.records:
            if ref.collection != "subraces":
                continue
            record = content.require(ref)
            base = record.facts.get("race")
            if not isinstance(base, str) or base not in self._offered["race"]:
                raise ValueError(f"{ref} names no offered race: {base!r}")
            if _race_bonuses(record)[1] is not None:
                raise ValueError(f"{ref} carries an ability-bonus choice; subraces grant flat only")
            subraces.setdefault(base, []).append((ref, record))
        self._subraces: dict[Slug, tuple[tuple[ContentRef, Record], ...]] = {
            base: tuple(sorted(pairs, key=lambda pair: pair[1].name))
            for base, pairs in subraces.items()
        }
        for class_ref in self._offered["class"].values():
            spells.verify(
                content,
                class_ref,
                content.require(class_ref).name,
                content.require(_level_one(class_ref)),
            )
        equipment.verify(content, self._offered["class"].values())

    def steps(self, picks: Picks) -> tuple[Step, ...]:
        return (*self._static, *self._follow_ups(picks))

    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        check_picks(self.steps(picks), picks)
        race = self._offered["race"][picked(picks, "race")[0]]
        class_ref = self._offered["class"][picked(picks, "class")[0]]
        background = self._offered["background"][picked(picks, "background")[0]]
        class_record = self.content.require(class_ref)
        hit_die = class_record.facts.get("hit-die")
        if not is_int_fact(hit_die):
            raise ValueError(f"{class_ref} names no hit-die to size hp from")
        numbers = _ability_numbers(picks)
        flat, choice = _race_bonuses(self.content.require(race))
        for entry in flat:
            numbers[entry.ability] += entry.bonus
        if choice is not None:
            for ability in picked(picks, f"{race.index}-bonus"):
                numbers[ability] += choice.bonus
        subraces = self._picked_subraces(race.index, picks)
        for _, subrace in subraces:
            for entry in _race_bonuses(subrace)[0]:
                numbers[entry.ability] += entry.bonus
        rows = tuple(self._level_rows(class_ref, picks))
        for row in rows:
            numbers.update(_level_one_numbers(row))
        # Slots come off the class row alone: what refills them is a fact of the class.
        counters = _slot_counters(rows[0], class_ref.index)
        chosen = self._features(picks)
        modifiers = {ability: modifier(numbers[ability]) for ability in ABILITIES}
        gear = equipment.starting_gear(self.content, class_ref, picks)
        # Unarmored Defense reads the features picked at level 1, so gear and features both land
        worn = tuple(item.ref for item in gear)
        numbers["armor-class"] = equipment.armor_class(self.content, worn, modifiers, chosen)
        hp = max(1, hit_die + modifiers["constitution"])
        counters["hp"] = Counter(current=hp, maximum=hp)
        for ref in chosen:
            found = pools.feature_pool(ref.index, numbers["level"], modifiers)
            if found is not None:
                counters[found[0]] = found[1]
        known_spells = tuple(
            class_ref.sibling("spells", index)
            for level in range(len(_SPELL_KINDS))
            for index in picked(picks, _spell_step(class_ref.index, level))
        )
        taken = (
            race,
            *(ref for ref, _ in subraces),
            class_ref,
            background,
            *chosen,
            *known_spells,
        )
        # Two steps can offer one record — a high elf's cantrip list overlaps its class's, a
        # background's languages overlap a race's extra one — and a ref lands once, so the second
        # pick would vanish instead of being spent.
        if twice := sorted({self._label(ref) for ref in taken if taken.count(ref) > 1}):
            raise ValueError(
                f"{', '.join(twice)} is picked twice: choose a different option for one step"
            )
        sheet = Sheet(numbers=numbers, counters=counters, refs=taken)
        return CreatedCharacter(
            profile=CharacterProfile(
                name=name, brief=brief, items=tuple(item.entity for item in gear)
            ),
            overlay=CharacterOverlay(
                character=sheet.model_dump(mode="json", exclude_defaults=True),
                entities={
                    item.entity.id: Sheet(refs=(item.ref,)).model_dump(
                        mode="json", exclude_defaults=True
                    )
                    for item in gear
                },
            ),
        )

    def _features(self, picks: Picks) -> tuple[ContentRef, ...]:
        """What the picked records hand over unasked, then what the player picked from them: a
        fighter is given Second Wind and chooses one fighting style."""
        found: list[ContentRef] = []
        for record in self._chosen_records(picks):
            found.extend((*record.granted, *_picked_options(record, picks)))
        return tuple(found)

    def _follow_ups(self, picks: Picks) -> tuple[Step, ...]:
        # A skill the background grants leaves the class's list and a language the race speaks
        # leaves the background's, as the SRD has it: what is handed over is never also offered.
        chosen = tuple(self._chosen_records(picks))
        held = tuple(ref for record in chosen for ref in record.granted)
        return (
            *_ability_steps(picks),
            *(self._record_step(record, held) for record in chosen if record.choose is not None),
            *self._subrace_steps(picks),
            *self._bonus_steps(picks),
            *self._equipment_steps(picks),
            *self._spell_steps(picks),
        )

    def _record_step(self, record: Record, held: Container[ContentRef]) -> CreationStep:
        offered = tuple(ref for ref in record.options if ref not in held)
        return CreationStep(
            id=record.index,
            prompt=_choice_prompt(record),
            options=tuple(CreationOption(id=ref.index, label=self._label(ref)) for ref in offered),
            choose=record.choose or 1,
        )

    def _spell_steps(self, picks: Picks) -> Iterator[CreationStep]:
        for index in picked(picks, "class"):
            ref = self._offered["class"].get(index)
            if ref is None:
                continue
            record = self.content.require(ref)
            counts = spells.known_at_level_one(index, self.content.require(_level_one(ref)))
            for level, choose in enumerate(counts):
                if choose == 0:
                    continue
                yield CreationStep(
                    id=_spell_step(index, level),
                    prompt=f"{record.name}: choose {choose} {_SPELL_KINDS[level]}",
                    options=tuple(
                        CreationOption(id=option.index, label=self._label(option))
                        for option in spells.castable(self.content, record.name, level)
                    ),
                    choose=choose,
                )

    def _equipment_steps(self, picks: Picks) -> Iterator[CreationStep]:
        """An equipment group is one more record carrying a choice, and an option that leaves a
        category open is one more after that; nothing here filters, since a class hands over gear
        it also offers only where the SRD means the character to hold two."""
        for index in picked(picks, "class"):
            ref = self._offered["class"].get(index)
            if ref is None:
                continue
            for record in equipment.chosen_records(self.content, ref, picks):
                if record.choose is not None:
                    yield self._record_step(record, ())

    def _subrace_steps(self, picks: Picks) -> Iterator[CreationStep]:
        for index in picked(picks, "race"):
            offered = self._subraces.get(index)
            if offered is None:
                continue
            yield CreationStep(
                id=f"{index}-subrace",
                prompt="Choose a subrace",
                options=tuple(
                    CreationOption(id=ref.index, label=record.name) for ref, record in offered
                ),
            )

    def _bonus_steps(self, picks: Picks) -> Iterator[CreationStep]:
        # "Choose two other abilities": the flat-bonus abilities stay out of the choice.
        for index in picked(picks, "race"):
            ref = self._offered["race"].get(index)
            if ref is None:
                continue
            record = self.content.require(ref)
            flat, choice = _race_bonuses(record)
            if choice is None:
                continue
            granted = {entry.ability for entry in flat}
            yield CreationStep(
                id=f"{index}-bonus",
                prompt=f"{record.name}: choose {choice.choose} abilities for +{choice.bonus}",
                options=tuple(
                    CreationOption(id=ability, label=ability.capitalize())
                    for ability in ABILITIES
                    if ability not in granted
                ),
                choose=choice.choose,
            )

    def _level_rows(self, class_ref: ContentRef, picks: Picks) -> Iterator[Record]:
        """A class answers with its level-1 row, which is where 5e keeps the first level's
        choices — and a subclass picked from that row answers with its own, the way cleric,
        sorcerer and warlock decide at level 1."""
        row = self.content.require(_level_one(class_ref))
        yield row
        for ref in _picked_options(row, picks):
            if ref.collection != SUBCLASSES:
                continue
            found = lookup(self.content, _level_one(ref))
            if found is not None:
                yield found

    def _chosen_records(self, picks: Picks) -> Iterator[Record]:
        """A picked record that carries a choice becomes one more step. A class also answers
        with its level-1 rows, where 5e keeps the first level's choices, and a subrace
        with the trait records that carry its own."""
        for step_id, _, _ in _COLLECTION_STEPS:
            for index in picked(picks, step_id):
                ref = self._offered[step_id].get(index)
                if ref is None:
                    continue  # a stale pick spawns no step; `create` refuses it outright
                yield self.content.require(ref)
                if step_id == "class":
                    yield from self._level_rows(ref, picks)
                if step_id == "race":
                    for _, subrace in self._picked_subraces(index, picks):
                        yield subrace
                        for trait in subrace.granted:
                            yield self.content.require(trait)

    def _picked_subraces(self, race: Slug, picks: Picks) -> tuple[tuple[ContentRef, Record], ...]:
        chosen = picked(picks, f"{race}-subrace")
        return tuple(
            (ref, record) for ref, record in self._subraces.get(race, ()) if ref.index in chosen
        )

    def _label(self, ref: ContentRef) -> str:
        record = lookup(self.content, ref)
        return ref.index if record is None else record.name


def _choice_prompt(record: Record) -> str:
    prompt = f"{record.name}: choose {record.choose}"
    collections = {ref.collection for ref in record.options}
    # An equipment group mixing items with option records is not "a choice of armor".
    if len(collections) == 1 and equipment.COLLECTION not in collections:
        prompt += f" ({next(iter(collections))})"
    return prompt


def _level_one(class_ref: ContentRef) -> ContentRef:
    return class_ref.sibling("levels", f"{class_ref.index}-1")


def _spell_step(class_index: Slug, level: int) -> Slug:
    return f"{class_index}-{'cantrips' if level == 0 else 'spells'}"


def _ability_steps(picks: Picks) -> Iterator[Step]:
    """One method step, then what that method needs: a seed to roll from, and the numbers the
    player puts on the six abilities."""
    method = picked(picks, _METHOD_STEP.id)
    if not method:
        return
    if method[0] == "standard-array":
        yield _assignment(method[0], f"Assign the standard array: {_spread(_ARRAY)}", *_BOUGHT)
    elif method[0] == "point-buy":
        prompt = f"Spend {_POINTS} points, every score {_BOUGHT[0]} to {_BOUGHT[1]}"
        yield _assignment(method[0], prompt, *_BOUGHT)
    else:
        yield _SEED_STEP
        rolled = _rolled(picks)
        if rolled is not None:
            prompt = f"Assign the roll: {_spread(rolled)}"
            yield _assignment(method[0], prompt, min(rolled), max(rolled))


def _assignment(method: Slug, prompt: str, minimum: int, maximum: int) -> AllocationStep:
    """One step id per method, so switching method prunes the scores the old one held."""
    return AllocationStep(
        id=f"abilities-{method}",
        prompt=prompt,
        entries=_ABILITY_ENTRIES,
        minimum=minimum,
        maximum=maximum,
    )


def _rolled(picks: Picks) -> tuple[int, ...] | None:
    """4d6 drop the lowest, six times, from the seed the player is holding."""
    seed = allocated(picks, _SEED_STEP.id).get("seed")
    # `steps` runs before `check_picks` has vouched anything: an unusable seed is simply no seed,
    # and the missing assignment step is what refuses.
    if type(seed) is not int:
        return None
    dice = Random(seed)
    rolls = (sorted(dice.randint(1, 6) for _ in range(4)) for _ in range(len(ABILITIES)))
    return tuple(sorted((sum(roll[-3:]) for roll in rolls), reverse=True))


def _ability_numbers(picks: Picks) -> dict[Slug, int]:
    """`check_picks` vouched that all six abilities carry a value inside the step's bounds; what
    the values must add up to is 5e's own rule, and only this knows it."""
    method = picked(picks, _METHOD_STEP.id)[0]
    amounts = allocated(picks, f"abilities-{method}")
    numbers = {ability: amounts[ability] for ability in ABILITIES}
    held = sorted(numbers.values(), reverse=True)
    if method == "point-buy":
        spent = sum(_POINT_COST[score] for score in held)
        if spent > _POINTS:
            raise ValueError(f"point buy spends {spent} of {_POINTS} points")
        return numbers
    wanted = sorted(_ARRAY if method == "standard-array" else _rolled(picks) or (), reverse=True)
    if held != wanted:
        raise ValueError(f"the scores to assign are {_spread(wanted)}, not {_spread(held)}")
    return numbers


def _spread(scores: Sequence[int]) -> str:
    return ", ".join(str(score) for score in scores)


def _level_one_numbers(level_one: Record) -> dict[Slug, int]:
    return {
        key: value
        for key, value in sorted(level_one.facts.items())
        if is_int_fact(value) and not key.startswith("slot-")
    }


def _slot_counters(level_one: Record, class_index: Slug) -> dict[Slug, Counter]:
    recharge = spells.slot_recharge(class_index)
    return {
        key: Counter(current=value, maximum=value, recharge=recharge)
        for key, value in sorted(level_one.facts.items())
        if key.startswith("slot-") and is_int_fact(value)
    }


def _picked_options(record: Record, picks: Picks) -> tuple[ContentRef, ...]:
    """`steps` runs before `check_picks` has vouched anything, so a pick naming no option of this
    record is simply no pick."""
    chosen = set(picked(picks, record.index))
    return tuple(ref for ref in record.options if ref.index in chosen)


def _race_bonuses(record: Record) -> tuple[tuple[_AbilityBonus, ...], _AbilityBonus | None]:
    try:
        entries = _ABILITY_BONUSES.validate_python(record.facts.get("ability-bonuses", ()))
    except ValidationError as invalid:
        message = invalid.errors()[0]["msg"]
        raise ValueError(f"{record.index} ability-bonuses cannot be read: {message}") from invalid
    flat = tuple(entry for entry in entries if entry.ability != "choice")
    choices = tuple(entry for entry in entries if entry.ability == "choice")
    if len(choices) > 1:
        raise ValueError(f"{record.index} carries more than one ability-bonus choice")
    if choices and choices[0].choose < 1:
        raise ValueError(f"{record.index} offers an ability-bonus choice that picks nothing")
    return flat, choices[0] if choices else None
