from collections.abc import Iterator, Mapping
from typing import Literal

from pydantic import TypeAdapter, ValidationError

from aidm.content.authored import CharacterOverlay, CharacterProfile, CreatedCharacter
from aidm.engines.counters import Counter
from aidm.engines.loader import Creation
from aidm.state.base import Frozen, Slug
from aidm.state.creation import CreationOption, CreationStep, Picks, check_picks
from aidm.state.packs import CollectionName, Content, ContentRef, Record, is_int_fact

from .content import lookup
from .mechanics import Sheet

_COLLECTION_STEPS: tuple[tuple[Slug, CollectionName, str], ...] = (
    ("race", "races", "Choose a race"),
    ("class", "classes", "Choose a class"),
    ("background", "backgrounds", "Choose a background"),
)
_ARRAY = (15, 14, 13, 12, 10, 8)
_ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
_MIGHT = ("strength", "constitution", "dexterity", "wisdom", "intelligence", "charisma")
_GRACE = ("dexterity", "constitution", "wisdom", "intelligence", "strength", "charisma")
_FOCUS_REST = ("constitution", "dexterity", "wisdom", "intelligence", "charisma", "strength")
_ABILITY_STEP = CreationStep(
    id="abilities",
    prompt="Assign the standard array (15, 14, 13, 12, 10, 8)",
    options=(
        CreationOption(
            id="might", label="Might", detail="STR 15, CON 14, DEX 13, WIS 12, INT 10, CHA 8"
        ),
        CreationOption(
            id="grace", label="Grace", detail="DEX 15, CON 14, WIS 13, INT 12, STR 10, CHA 8"
        ),
        CreationOption(
            id="focus",
            label="Focus",
            detail="The class's casting ability leads at 15 (WIS when the class does not "
            "cast), CON 14 and DEX 13 follow",
        ),
    ),
)

# Skill grants and level-1 feature pools exist only as prose in the pack's class and feature
# texts; these tables transcribe that prose (bard's "any three" is every skill), and __init__
# refuses a skill the pack cannot back.
_SKILLS: tuple[Slug, ...] = (
    "acrobatics",
    "animal-handling",
    "arcana",
    "athletics",
    "deception",
    "history",
    "insight",
    "intimidation",
    "investigation",
    "medicine",
    "nature",
    "perception",
    "performance",
    "persuasion",
    "religion",
    "sleight-of-hand",
    "stealth",
    "survival",
)
_CLASS_SKILLS: Mapping[Slug, tuple[int, tuple[Slug, ...]]] = {
    "barbarian": (
        2,
        ("animal-handling", "athletics", "intimidation", "nature", "perception", "survival"),
    ),
    "bard": (3, _SKILLS),
    "cleric": (2, ("history", "insight", "medicine", "persuasion", "religion")),
    "druid": (
        2,
        (
            "arcana",
            "animal-handling",
            "insight",
            "medicine",
            "nature",
            "perception",
            "religion",
            "survival",
        ),
    ),
    "fighter": (
        2,
        (
            "acrobatics",
            "animal-handling",
            "athletics",
            "history",
            "insight",
            "intimidation",
            "perception",
            "survival",
        ),
    ),
    "monk": (2, ("acrobatics", "athletics", "history", "insight", "religion", "stealth")),
    "paladin": (2, ("athletics", "insight", "intimidation", "medicine", "persuasion", "religion")),
    "ranger": (
        3,
        (
            "animal-handling",
            "athletics",
            "insight",
            "investigation",
            "nature",
            "perception",
            "stealth",
            "survival",
        ),
    ),
    "rogue": (
        4,
        (
            "acrobatics",
            "athletics",
            "deception",
            "insight",
            "intimidation",
            "investigation",
            "perception",
            "performance",
            "persuasion",
            "sleight-of-hand",
            "stealth",
        ),
    ),
    "sorcerer": (2, ("arcana", "deception", "insight", "intimidation", "persuasion", "religion")),
    "warlock": (
        2,
        ("arcana", "deception", "history", "intimidation", "investigation", "nature", "religion"),
    ),
    "wizard": (2, ("arcana", "history", "insight", "investigation", "medicine", "religion")),
}
_BACKGROUND_SKILLS: Mapping[Slug, tuple[Slug, ...]] = {"acolyte": ("insight", "religion")}
# "Two languages of your choice": any language the character does not already speak.
_BACKGROUND_LANGUAGES: Mapping[Slug, int] = {"acolyte": 2}
# Race automatic languages exist only as prose in the pack's race texts; this table
# transcribes that prose, and __init__ refuses a language the pack cannot back.
_RACE_LANGUAGES: Mapping[Slug, tuple[Slug, ...]] = {
    "dwarf": ("common", "dwarvish"),
    "elf": ("common", "elvish"),
    "halfling": ("common", "halfling"),
    "human": ("common",),
    "dragonborn": ("common", "draconic"),
    "gnome": ("common", "gnomish"),
    "half-elf": ("common", "elvish"),
    "half-orc": ("common", "orc"),
    "tiefling": ("common", "infernal"),
}


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
            _ABILITY_STEP,
        )
        self._languages: tuple[tuple[ContentRef, Record], ...] = tuple(
            sorted(
                (
                    (ref, content.require(ref))
                    for ref in content.records
                    if ref.collection == "languages"
                ),
                key=lambda pair: pair[1].name,
            )
        )
        for race_ref in self._offered["race"].values():
            _ = _race_bonuses(content.require(race_ref))
            if race_ref.index not in _RACE_LANGUAGES:
                raise ValueError(f"{race_ref} has no authored language list")
            for language in _RACE_LANGUAGES[race_ref.index]:
                _ = content.require(race_ref.sibling("languages", language))
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
            if class_ref.index not in _CLASS_SKILLS:
                raise ValueError(f"{class_ref} has no authored skill list")
            for skill in _CLASS_SKILLS[class_ref.index][1]:
                _ = content.require(_skill_ref(class_ref, skill))
        for background_ref in self._offered["background"].values():
            for skill in _BACKGROUND_SKILLS.get(background_ref.index, ()):
                _ = content.require(_skill_ref(background_ref, skill))
            if background_ref.index in _BACKGROUND_LANGUAGES and not self._languages:
                raise ValueError(f"{background_ref} grants languages but the pack offers none")

    def steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        return (*self._static, *self._follow_ups(picks))

    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        check_picks(self.steps(picks), picks)
        race = self._offered["race"][picks["race"][0]]
        class_ref = self._offered["class"][picks["class"][0]]
        background = self._offered["background"][picks["background"][0]]
        class_record = self.content.require(class_ref)
        hit_die = class_record.facts.get("hit-die")
        if not is_int_fact(hit_die):
            raise ValueError(f"{class_ref} names no hit-die to size hp from")
        numbers: dict[Slug, int] = dict(
            zip(_order(picks["abilities"][0], class_record), _ARRAY, strict=True)
        )
        flat, choice = _race_bonuses(self.content.require(race))
        for entry in flat:
            numbers[entry.ability] += entry.bonus
        if choice is not None:
            for ability in picks[f"{race.index}-bonus"]:
                numbers[ability] += choice.bonus
        subraces = tuple(
            (ref, record)
            for ref, record in self._subraces.get(race.index, ())
            if ref.index in picks.get(f"{race.index}-subrace", ())
        )
        for _, subrace in subraces:
            for entry in _race_bonuses(subrace)[0]:
                numbers[entry.ability] += entry.bonus
        counters: dict[Slug, Counter] = {}
        for key, value in sorted(self.content.require(_level_one(class_ref)).facts.items()):
            if not is_int_fact(value):
                continue
            if key.startswith("slot-"):
                # Pact magic slots return on a short rest; every other class waits for a long one.
                recharge = "short-rest" if class_ref.index == "warlock" else "long-rest"
                counters[key] = Counter(current=value, maximum=value, recharge=recharge)
            else:
                numbers[key] = value
        numbers["armor-class"] = 10 + _modifier(numbers["dexterity"])
        hp = max(1, hit_die + _modifier(numbers["constitution"]))
        counters["hp"] = Counter(current=hp, maximum=hp)
        chosen = tuple(
            _option_ref(record, index)
            for record in self._chosen_records(picks)
            if record.choose is not None
            for index in picks.get(record.index, ())
        )
        for ref in chosen:
            pool = _feature_pool(ref.index, _modifier(numbers["charisma"]))
            if pool is not None:
                counters[ref.index] = pool
        granted = _BACKGROUND_SKILLS.get(background.index, ())
        skills = (
            *(_skill_ref(background, skill) for skill in granted),
            *(_skill_ref(class_ref, skill) for skill in picks[f"{class_ref.index}-skills"]),
        )
        languages = (
            *(race.sibling("languages", language) for language in _RACE_LANGUAGES[race.index]),
            *(
                background.sibling("languages", language)
                for language in picks.get(f"{background.index}-languages", ())
            ),
        )
        sheet = Sheet(
            numbers=numbers,
            counters=counters,
            # A race step and a background step may legally pick the same language.
            refs=tuple(
                dict.fromkeys(
                    (
                        race,
                        *(ref for ref, _ in subraces),
                        class_ref,
                        background,
                        *chosen,
                        *skills,
                        *languages,
                    )
                )
            ),
        )
        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief),
            overlay=CharacterOverlay(
                character=sheet.model_dump(mode="json", exclude_defaults=True)
            ),
        )

    def _follow_ups(self, picks: Picks) -> tuple[CreationStep, ...]:
        record_steps = tuple(
            CreationStep(
                id=record.index,
                prompt=_choice_prompt(record),
                options=tuple(
                    CreationOption(id=ref.index, label=self._label(ref)) for ref in record.options
                ),
                choose=record.choose,
            )
            for record in self._chosen_records(picks)
            if record.choose is not None
        )
        return (
            *record_steps,
            *self._subrace_steps(picks),
            *self._bonus_steps(picks),
            *self._skill_steps(picks),
            *self._language_steps(picks),
        )

    def _subrace_steps(self, picks: Picks) -> Iterator[CreationStep]:
        for index in picks.get("race", ()):
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
        for index in picks.get("race", ()):
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
                    for ability in _ABILITIES
                    if ability not in granted
                ),
                choose=choice.choose,
            )

    def _skill_steps(self, picks: Picks) -> Iterator[CreationStep]:
        # A skill the background already grants leaves the class's list, as the SRD has it.
        granted = {
            skill
            for index in picks.get("background", ())
            for skill in _BACKGROUND_SKILLS.get(index, ())
        }
        for index in picks.get("class", ()):
            ref = self._offered["class"].get(index)
            if ref is None:
                continue
            choose, skills = _CLASS_SKILLS[ref.index]
            yield CreationStep(
                id=f"{index}-skills",
                prompt=f"{self.content.require(ref).name}: choose {choose} skills",
                options=tuple(
                    CreationOption(id=skill, label=self._label(_skill_ref(ref, skill)))
                    for skill in skills
                    if skill not in granted
                ),
                choose=choose,
            )

    def _language_steps(self, picks: Picks) -> Iterator[CreationStep]:
        # Everyone speaks Common, and the picked race's automatic languages stay out too.
        known = {
            "common",
            *(
                language
                for index in picks.get("race", ())
                for language in _RACE_LANGUAGES.get(index, ())
            ),
        }
        for index in picks.get("background", ()):
            ref = self._offered["background"].get(index)
            choose = _BACKGROUND_LANGUAGES.get(index)
            if ref is None or choose is None:
                continue
            yield CreationStep(
                id=f"{index}-languages",
                prompt=f"{self.content.require(ref).name}: choose {choose} languages",
                options=tuple(
                    CreationOption(id=language.index, label=record.name)
                    for language, record in self._languages
                    if language.index not in known
                ),
                choose=choose,
            )

    def _chosen_records(self, picks: Picks) -> Iterator[Record]:
        """A picked record that carries a choice becomes one more step. A class also answers
        with its level-1 row, which is where 5e keeps the first level's choices."""
        for step_id, _, _ in _COLLECTION_STEPS:
            for index in picks.get(step_id, ()):
                ref = self._offered[step_id].get(index)
                if ref is None:
                    continue  # a stale pick spawns no step; `create` refuses it outright
                yield self.content.require(ref)
                if step_id == "class":
                    yield self.content.require(_level_one(ref))

    def _label(self, ref: ContentRef) -> str:
        record = lookup(self.content, ref)
        return ref.index if record is None else record.name


def _choice_prompt(record: Record) -> str:
    prompt = f"{record.name}: choose {record.choose}"
    collections = {ref.collection for ref in record.options}
    if len(collections) == 1:
        prompt += f" ({next(iter(collections))})"
    return prompt


def _level_one(class_ref: ContentRef) -> ContentRef:
    return class_ref.sibling("levels", f"{class_ref.index}-1")


def _order(priority: Slug, class_record: Record) -> tuple[Slug, ...]:
    if priority == "might":
        return _MIGHT
    if priority == "grace":
        return _GRACE
    cast = class_record.facts.get("spellcasting")
    lead = cast if isinstance(cast, str) and cast in _ABILITIES else "wisdom"
    return (lead, *(ability for ability in _FOCUS_REST if ability != lead))


def _modifier(score: int) -> int:
    return (score - 10) // 2


def _option_ref(record: Record, index: str) -> ContentRef:
    # check_picks already vouched the index is one of the record's options.
    return next(ref for ref in record.options if ref.index == index)


def _skill_ref(ref: ContentRef, skill: Slug) -> ContentRef:
    return ref.sibling("proficiencies", f"skill-{skill}")


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


def _feature_pool(index: Slug, charisma_mod: int) -> Counter | None:
    pools: Mapping[Slug, tuple[int, str]] = {
        "second-wind": (1, "short-rest"),
        "rage": (2, "long-rest"),
        "bardic-inspiration-d6": (max(1, charisma_mod), "long-rest"),
        "divine-sense": (max(0, 1 + charisma_mod), "long-rest"),
        "lay-on-hands": (5, "long-rest"),
        "arcane-recovery": (1, "long-rest"),
    }
    held = pools.get(index)
    if held is None:
        return None
    maximum, recharge = held
    return Counter(current=maximum, maximum=maximum, recharge=recharge)
