"""Monsters: the whole action economy, projected from one wide upstream record."""

from collections.abc import Sequence

from aidm.plugins.dnd5e.content.records.base import ContentRef
from aidm.plugins.dnd5e.content.records.monsters import (
    MonsterAction,
    MonsterAttack,
    MonsterMultiattack,
    MonsterProcedure,
    MonsterRecord,
    MonsterSave,
    MonsterSpell,
    MonsterSpellcasting,
    MultiattackOption,
    MultiattackStep,
    Senses,
    Speed,
)
from aidm.plugins.dnd5e.values import Ability, Attributes

from .common import PACK_ID, ability, damages, feet, index_of, owner_of, usage
from .upstream.monsters import (
    Action,
    ActionOption,
    Monster,
    MultiattackEntry,
    Proficiency,
    SpecialAbility,
)


def _attack_step(option: ActionOption) -> MultiattackStep:
    if option.action_name is None or option.count is None or option.type is None:
        raise ValueError(f"multiattack option is missing a field: {option!r}")
    return MultiattackStep(
        action_name=option.action_name, count=option.count, attack_type=option.type
    )


def _fixed_step(entry: MultiattackEntry) -> MultiattackStep | None:
    """`None` where the count is not a number — the hydra's 'Number of Heads', and a '1d4'."""
    if not isinstance(entry.count, int):
        return None
    return MultiattackStep(action_name=entry.action_name, count=entry.count, attack_type=entry.type)


def _multiattack_options(action: Action) -> tuple[MultiattackOption, ...] | None:
    """A fixed routine is one option; a choice is several. A routine with a count no number can hold
    stays prose rather than being defaulted to one attack."""
    if action.actions:
        steps = tuple(s for e in action.actions if (s := _fixed_step(e)) is not None)
        return (MultiattackOption(steps=steps),) if len(steps) == len(action.actions) else None
    if action.action_options is None:
        return None
    return tuple(
        MultiattackOption(
            steps=tuple(_attack_step(i) for i in option.items)
            if option.option_type == "multiple"
            else (_attack_step(option),)
        )
        for option in action.action_options.options.options
    )


def _action(action: Action, owner: str) -> list[MonsterAction]:
    """A list, because a dragon's "Breath Weapons" is one upstream entry holding two saves that
    share one recharge — flattening them is what types 40 breaths that were prose before.

    An `attack_bonus` makes an entry an attack even when a save rides along (the aboleth's tentacle,
    the pack's only action with both): the to-hit roll is what `engine/` would resolve first."""
    when = usage(action.usage)
    damage = damages(action.damage, owner)
    if action.options is not None:
        return [
            MonsterSave(
                name=f"{action.name}: {breath.name}",
                desc=action.desc,
                usage=when,
                damage=damages(breath.damage, owner),
                save_ability=ability(breath.dc.dc_type.index),
                dc=breath.dc.dc_value,
                on_success=breath.dc.success_type,
            )
            for breath in action.options.options.options
        ]
    if (options := _multiattack_options(action)) is not None:
        return [
            MonsterMultiattack(
                name=action.name, desc=action.desc, usage=when, damage=damage, options=options
            )
        ]
    if action.attack_bonus is not None:
        return [
            MonsterAttack(
                name=action.name,
                desc=action.desc,
                usage=when,
                damage=damage,
                attack_bonus=action.attack_bonus,
            )
        ]
    if action.dc is not None:
        return [
            MonsterSave(
                name=action.name,
                desc=action.desc,
                usage=when,
                damage=damage,
                save_ability=ability(action.dc.dc_type.index),
                dc=action.dc.dc_value,
                on_success=action.dc.success_type,
            )
        ]
    return [MonsterProcedure(name=action.name, desc=action.desc, usage=when, damage=damage)]


def _actions(actions: Sequence[Action], owner: str) -> tuple[MonsterAction, ...]:
    return tuple(projected for a in actions for projected in _action(a, owner))


def _spellcasting(abilities: Sequence[SpecialAbility]) -> MonsterSpellcasting | None:
    """At most one per monster, verified pack-wide."""
    casting = next((a.spellcasting for a in abilities if a.spellcasting is not None), None)
    if casting is None:
        return None
    return MonsterSpellcasting(
        ability=ability(casting.ability.index),
        dc=casting.dc,
        modifier=casting.modifier,
        level=casting.level,
        slots=casting.slots,
        spells=tuple(
            MonsterSpell(
                ref=ContentRef(pack=PACK_ID, collection="spells", index=index_of(spell.url)),
                name=spell.name,
                level=spell.level,
                usage=usage(spell.usage),
                notes=spell.notes,
            )
            for spell in casting.spells
        ),
    )


def _speed(speed: dict[str, str | bool]) -> Speed:
    walk = {mode: feet(v) for mode, v in speed.items() if isinstance(v, str)}
    return Speed(**walk, hover=speed.get("hover") is True)


def _senses(senses: dict[str, int | str]) -> Senses:
    ranges = {sense: feet(v) for sense, v in senses.items() if isinstance(v, str)}
    passive = senses.get("passive_perception")
    if not isinstance(passive, int):
        raise ValueError("a monster with no passive perception has no perception DC")
    return Senses(passive_perception=passive, **ranges)


def _proficiencies(profs: Sequence[Proficiency], prefix: str) -> dict[str, int]:
    return {
        p.proficiency.index.removeprefix(prefix): p.value
        for p in profs
        if p.proficiency.index.startswith(prefix)
    }


def _saving_throws(profs: Sequence[Proficiency]) -> dict[Ability, int]:
    abbreviations = _proficiencies(profs, "saving-throw-")
    return {ability(a): v for a, v in abbreviations.items()}


def monster(monster: Monster) -> MonsterRecord:
    """Only the first `armor_class` entry is projected: the 7 records carrying a second one gate it
    on a spell or a condition, which is a rule `engine/` cannot apply."""
    owner = owner_of("monsters", monster.index)
    return MonsterRecord(
        index=monster.index,
        name=monster.name,
        size=monster.size,
        type=monster.type,
        challenge_rating=monster.challenge_rating,
        armor_class=monster.armor_class[0].value,
        hit_points=monster.hit_points,
        hit_points_roll=monster.hit_points_roll,
        attributes=Attributes(
            strength=monster.strength,
            dexterity=monster.dexterity,
            constitution=monster.constitution,
            intelligence=monster.intelligence,
            wisdom=monster.wisdom,
            charisma=monster.charisma,
        ),
        speed=_speed(monster.speed),
        senses=_senses(monster.senses),
        damage_resistances=tuple(monster.damage_resistances),
        damage_immunities=tuple(monster.damage_immunities),
        damage_vulnerabilities=tuple(monster.damage_vulnerabilities),
        condition_immunities=tuple(c.index for c in monster.condition_immunities),
        saving_throws=_saving_throws(monster.proficiencies),
        skills=_proficiencies(monster.proficiencies, "skill-"),
        actions=_actions(monster.actions, owner),
        legendary_actions=_actions(monster.legendary_actions, owner),
        reactions=_actions(monster.reactions, owner),
        traits=_actions(monster.special_abilities, owner),
        spellcasting=_spellcasting(monster.special_abilities),
    )
