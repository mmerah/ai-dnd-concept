"""Monsters: one wide record covering a whole action economy."""

from aidm_5e.content.records.base import CreatureSize
from aidm_5e.content.records.monsters import AttackType, MonsterType, SaveOutcome
from aidm_5e.content.vocabulary import RestType
from pydantic import Field

from .base import ApiRef, ConditionRef, Damage, Upstream


class ActionDc(Upstream):
    dc_type: ApiRef
    dc_value: int
    success_type: SaveOutcome


class UpstreamUsage(Upstream):
    type: str
    dice: str | None = None
    min_value: int | None = None
    times: int | None = None
    rest_types: list[RestType] = Field(default_factory=list)


class MultiattackEntry(Upstream):
    action_name: str
    count: int | str
    type: AttackType


class ActionOption(Upstream):
    """One arm of a multiattack choice: either a single action, or several taken together."""

    option_type: str
    action_name: str | None = None
    count: int | None = None
    type: AttackType | None = None
    items: list["ActionOption"] = Field(default_factory=list)


ActionOption.model_rebuild()


class BreathOption(Upstream):
    name: str
    dc: ActionDc
    damage: list[Damage] = Field(default_factory=list)


class OptionSet[T](Upstream):
    options: list[T]


class MonsterChoice[T](Upstream):
    choose: int
    options: OptionSet[T] = Field(alias="from")


class Action(Upstream):
    name: str
    desc: str
    attack_bonus: int | None = None
    dc: ActionDc | None = None
    damage: list[Damage] = Field(default_factory=list)
    usage: UpstreamUsage | None = None
    actions: list[MultiattackEntry] = Field(default_factory=list)
    action_options: MonsterChoice[ActionOption] | None = None
    options: MonsterChoice[BreathOption] | None = None


class SpellSlot(Upstream):
    name: str
    level: int
    url: str
    usage: UpstreamUsage | None = None
    notes: str | None = None


class Spellcasting(Upstream):
    ability: ApiRef
    dc: int | None = None
    modifier: int | None = None
    level: int | None = None
    slots: dict[int, int] = Field(default_factory=dict)
    spells: list[SpellSlot] = Field(default_factory=list)


class SpecialAbility(Action):
    spellcasting: Spellcasting | None = None


class ArmorClass(Upstream):
    value: int


class Proficiency(Upstream):
    value: int
    proficiency: ApiRef


class Monster(Upstream):
    index: str
    name: str
    size: CreatureSize
    type: MonsterType
    challenge_rating: float
    armor_class: list[ArmorClass]
    hit_points: int
    hit_points_roll: str
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int
    speed: dict[str, str | bool]
    senses: dict[str, int | str]
    proficiencies: list[Proficiency] = Field(default_factory=list)
    damage_resistances: list[str] = Field(default_factory=list)
    damage_immunities: list[str] = Field(default_factory=list)
    damage_vulnerabilities: list[str] = Field(default_factory=list)
    condition_immunities: list[ConditionRef] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    legendary_actions: list[Action] = Field(default_factory=list)
    reactions: list[Action] = Field(default_factory=list)
    special_abilities: list[SpecialAbility] = Field(default_factory=list)
