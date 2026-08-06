from collections.abc import Mapping, Sequence
from random import Random

from pydantic import JsonValue

from aidm.engines.loader import Engine
from aidm.state.base import PLAYER_ID, Entity, EntityId, Slug
from aidm.state.dice import DiceExpr, roll
from aidm.state.effects import (
    AddTag,
    AdjustCounter,
    SetNote,
    SpendCounter,
    apply_effect,
    entity_fact,
    require_actor_here,
)
from aidm.state.facts import Fact
from aidm.state.plan import TurnPlanBase, apply_branch, check_plan_base
from aidm.state.sheet import Sheet
from aidm.state.world import GameState, player_sheet, sheet_of

from .actions import (
    CONTESTED,
    FAILURE,
    SUCCESS,
    UNCONTESTED,
    Attack,
    CastSpell,
    Check,
    Dnd5eAction,
    Dnd5ePlan,
    Improvise,
    Rest,
    UseFeature,
)
from .advance import ADVANCEMENT_READY, LEVEL
from .content import SpellFacts, spell_of, spellcasting_ability, weapon_of

ARMOR_CLASS = "armor-class"
CONCENTRATION = "concentration"
HP = "hp"
PROFICIENCY = "proficiency-bonus"
SLOT = "slot-"
D20 = "1d20"
SAVE_DC_BASE = 8
DEFAULT_LEVEL = 1
MILESTONE_TAG = AddTag(
    entity_id=PLAYER_ID,
    tag_id=ADVANCEMENT_READY,
    text="The story has earned a level.",
)


def check_plan(engine: Engine, state: GameState, plan: TurnPlanBase) -> str | None:
    try:
        fivee = _dnd5e_plan(plan)
        action = fivee.action
        if action is not None:
            # The resolver raises every refusal the check owes the model, so trial it on a draft
            # that is thrown away rather than stating each precondition twice.
            _ = _resolved(state.draft(), engine, action, Random(0))
        labels = _labels(engine, action)
    except ValueError as refused:
        return str(refused)
    return check_plan_base(state, fivee, labels, engine.default_rules)


def resolve_action(engine: Engine, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
    fivee = _dnd5e_plan(plan)
    facts, outcome = _resolved(draft, engine, fivee.action, rng)
    if outcome is not None:
        facts.extend(apply_branch(draft, plan, outcome, engine.default_rules))
    if fivee.milestone_earned and player_sheet(draft).tag(ADVANCEMENT_READY) is None:
        facts.extend(apply_effect(draft, MILESTONE_TAG, engine.default_rules))
    return facts


def _dnd5e_plan(plan: TurnPlanBase) -> Dnd5ePlan:
    if not isinstance(plan, Dnd5ePlan):
        raise ValueError(f"the 5e engine cannot resolve a {type(plan).__name__}")
    return plan


def _labels(engine: Engine, action: Dnd5eAction | None) -> frozenset[Slug]:
    match action:
        case CastSpell():
            spell = _spell(engine, action)
            return CONTESTED if spell.attack or spell.save_ability is not None else UNCONTESTED
        case Improvise():
            return CONTESTED if action.vs is not None else UNCONTESTED
        case Attack() | Check():
            return CONTESTED
        case None | UseFeature() | Rest():
            return UNCONTESTED


def _resolved(
    draft: GameState, engine: Engine, action: Dnd5eAction | None, rng: Random
) -> tuple[list[Fact], Slug | None]:
    match action:
        case None:
            return [], None
        case Attack():
            return _attack(draft, engine, action, rng)
        case CastSpell():
            return _cast(draft, engine, action, rng)
        case Check():
            actor = require_actor_here(draft, action.actor_id)
            rolled, fact = roll(
                D20,
                f"{actor.name}: {action.reason}",
                rng,
                vs=action.dc,
                mode=action.mode,
                bonus=action.bonus,
            )
            return [*_seen(draft, actor), fact], _verdict(rolled.total >= action.dc)
        case UseFeature():
            return _feature(draft, engine, action, rng)
        case Rest():
            return _rest(draft, engine, action)
        case Improvise():
            rolled, fact = roll(action.dice, action.reason, rng, vs=action.vs, mode=action.mode)
            return [fact], None if action.vs is None else _verdict(rolled.total >= action.vs)


def _attack(
    draft: GameState, engine: Engine, action: Attack, rng: Random
) -> tuple[list[Fact], Slug]:
    attacker = require_actor_here(draft, action.actor_id)
    target = require_actor_here(draft, action.target_id)
    facts = _seen(draft, attacker, target)
    to_hit, damage, damage_bonus = _attack_terms(draft, engine, attacker, action)
    armor_class = _armor_class(draft, target)
    rolled, fact = roll(
        D20,
        f"{attacker.name} attacks {target.name}",
        rng,
        vs=armor_class,
        mode=action.mode,
        bonus=to_hit,
    )
    facts.append(fact)
    if rolled.total < armor_class:
        return facts, FAILURE
    hurt, damage_fact = roll(damage, f"{attacker.name}'s damage", rng, bonus=damage_bonus)
    facts.append(damage_fact)
    facts.extend(_harm(draft, engine, target.id, -hurt.total, f"{attacker.name}'s attack"))
    return facts, SUCCESS


def _attack_terms(
    state: GameState, engine: Engine, attacker: Entity, action: Attack
) -> tuple[int, DiceExpr, int]:
    if action.weapon_item_id is None:
        if action.attack_bonus is None or action.damage is None:
            raise ValueError(
                "an attack needs either a `weapon_item_id` the attacker carries, or both "
                "`attack_bonus` and `damage` copied off their stat block's attack line"
            )
        return action.attack_bonus, action.damage, 0
    if action.attack_bonus is not None or action.damage is not None:
        raise ValueError(
            "a weapon's to-hit and damage come from its record: leave `attack_bonus` and `damage` "
            "null when you name a `weapon_item_id`"
        )
    item = _carried(state, attacker, action.weapon_item_id)
    weapon = weapon_of(engine.content, sheet_of(state, item.id))
    if weapon is None:
        raise ValueError(
            f"{item.name} is no weapon. Attack with a weapon the attacker carries, or give "
            "`attack_bonus` and `damage` yourself."
        )
    sheet = sheet_of(state, attacker.id)
    strength = _modifier(sheet, "strength")
    dexterity = _modifier(sheet, "dexterity")
    if weapon.finesse:
        ability = max(strength, dexterity)
    else:
        ability = dexterity if weapon.ranged else strength
    return ability + sheet.numbers.get(PROFICIENCY, 0), weapon.dice(action.two_handed), ability


def _cast(
    draft: GameState, engine: Engine, action: CastSpell, rng: Random
) -> tuple[list[Fact], Slug | None]:
    caster = require_actor_here(draft, action.actor_id)
    sheet = sheet_of(draft, caster.id)
    spell = _spell(engine, action)
    modifier = _spell_modifier(engine, sheet)
    slot = _slot_spent(action, spell)
    facts = _seen(draft, caster)
    if action.target_id is not None:
        facts.extend(_seen(draft, require_actor_here(draft, action.target_id)))
    if slot is not None:
        facts.extend(_spend(draft, engine, caster.id, f"{SLOT}{slot}"))
    outcome, contest = _contest(draft, engine, action, spell, caster, modifier, rng)
    facts.extend(contest)
    # A cantrip spends no slot, so it is the caster's own level that scales it.
    scale = slot if slot is not None else sheet.numbers.get(LEVEL, DEFAULT_LEVEL)
    facts.extend(_spell_effect(draft, engine, action, spell, caster, modifier, scale, outcome, rng))
    if spell.concentration:
        note = SetNote(entity_id=caster.id, key=CONCENTRATION, text=spell.name)
        facts.extend(apply_effect(draft, note, engine.default_rules))
    return facts, outcome


def _contest(
    draft: GameState,
    engine: Engine,
    action: CastSpell,
    spell: SpellFacts,
    caster: Entity,
    modifier: int,
    rng: Random,
) -> tuple[Slug | None, list[Fact]]:
    """A save is read from the caster's side: `success` means the target failed to resist."""
    sheet = sheet_of(draft, caster.id)
    proficiency = sheet.numbers.get(PROFICIENCY, 0)
    if spell.attack:
        target = _spell_target(draft, action, spell)
        armor_class = _armor_class(draft, target)
        reason = f"{caster.name} casts {spell.name} at {target.name}"
        rolled, fact = roll(D20, reason, rng, vs=armor_class, bonus=modifier + proficiency)
        return _verdict(rolled.total >= armor_class), [fact]
    if spell.save_ability is not None:
        target = _spell_target(draft, action, spell)
        dc = SAVE_DC_BASE + proficiency + modifier
        save = _modifier(sheet_of(draft, target.id), spell.save_ability)
        reason = f"{target.name} resists {spell.name}"
        rolled, fact = roll(D20, reason, rng, vs=dc, bonus=save)
        return _verdict(rolled.total < dc), [fact]
    return None, []


def _spell_effect(
    draft: GameState,
    engine: Engine,
    action: CastSpell,
    spell: SpellFacts,
    caster: Entity,
    modifier: int,
    scale: int,
    outcome: Slug | None,
    rng: Random,
) -> list[Fact]:
    """A miss or a full save ends the spell; a save that only halves the damage still rolls it."""
    if outcome == FAILURE and not spell.half_on_save:
        return []
    facts: list[Fact] = []
    if (damage := spell.damage_at(scale)) is not None:
        target = _spell_target(draft, action, spell)
        rolled, fact = roll(damage.dice, f"{spell.name} damage", rng, bonus=damage.bonus(modifier))
        total = rolled.total // 2 if outcome == FAILURE else rolled.total
        facts.append(fact)
        facts.extend(_harm(draft, engine, target.id, -total, spell.name))
    if (heal := spell.heal_at(scale)) is not None:
        healed = require_actor_here(draft, action.target_id or caster.id)
        rolled, fact = roll(heal.dice, f"{spell.name} healing", rng, bonus=heal.bonus(modifier))
        facts.append(fact)
        facts.extend(_harm(draft, engine, healed.id, rolled.total, spell.name))
    return facts


def _feature(
    draft: GameState, engine: Engine, action: UseFeature, rng: Random
) -> tuple[list[Fact], None]:
    actor = require_actor_here(draft, action.actor_id)
    facts = _seen(draft, actor)
    facts.extend(_spend(draft, engine, actor.id, action.counter))
    if action.heal is not None:
        rolled, fact = roll(action.heal, f"{actor.name} draws on {action.counter}", rng)
        facts.append(fact)
        facts.extend(_harm(draft, engine, actor.id, rolled.total, action.counter))
    return facts, None


def _rest(draft: GameState, engine: Engine, action: Rest) -> tuple[list[Fact], None]:
    actor = require_actor_here(draft, action.actor_id)
    refilled = _refilled_by(engine, action.label)
    seen = _seen(draft, actor)
    sheet = sheet_of(draft, actor.id)
    keys: list[str] = []
    for key, counter in sorted(sheet.counters.items()):
        maximum = counter.maximum
        if maximum is None or counter.recharge not in refilled or counter.current == maximum:
            continue
        counter.current = maximum
        keys.append(key)
    if not keys:
        return seen, None
    trace = f"{actor.name} took {action.label}: refilled {', '.join(keys)}"
    data: Mapping[str, JsonValue] = {"label": action.label, "counters": list(keys)}
    return [*seen, entity_fact(actor, "recharged", trace, data)], None


def _spell(engine: Engine, action: CastSpell) -> SpellFacts:
    spell = spell_of(engine.content, action.spell)
    if spell is None:
        raise ValueError(
            f"the rules for {action.spell} are not written in a form this engine resolves: "
            "resolve it with `improvise` instead"
        )
    return spell


def _spell_modifier(engine: Engine, sheet: Sheet) -> int:
    ability = spellcasting_ability(engine.content, sheet)
    if ability is None:
        raise ValueError(
            "this actor's class casts no spells, so it has no spellcasting ability: resolve what "
            "they do with `improvise` instead"
        )
    return _modifier(sheet, ability)


def _slot_spent(action: CastSpell, spell: SpellFacts) -> int | None:
    if spell.level is None:
        if action.slot_level is not None:
            raise ValueError(f"{spell.name} is a cantrip: it spends no slot, so leave it null")
        return None
    if action.slot_level is None:
        raise ValueError(
            f"{spell.name} is a level {spell.level} spell: name the `slot_level` it is cast from"
        )
    if action.slot_level < spell.level:
        raise ValueError(
            f"{spell.name} needs a slot of level {spell.level} or higher, not {action.slot_level}"
        )
    return action.slot_level


def _spell_target(state: GameState, action: CastSpell, spell: SpellFacts) -> Entity:
    if action.target_id is None:
        raise ValueError(f"{spell.name} is aimed at a creature: name its `target_id`")
    return require_actor_here(state, action.target_id)


def _carried(state: GameState, holder: Entity, item_id: EntityId) -> Entity:
    item = state.world.record(item_id, "item").entity
    if item.parent_id != holder.id:
        raise ValueError(f"{holder.name} does not carry item {item_id!r}")
    return item


def _armor_class(state: GameState, target: Entity) -> int:
    return sheet_of(state, target.id).numbers[ARMOR_CLASS]


def _modifier(sheet: Sheet, ability: Slug) -> int:
    return (sheet.numbers[ability] - 10) // 2


def _refilled_by(engine: Engine, label: str) -> Sequence[str]:
    refilled = engine.spec.recharge.get(label)
    if refilled is None:
        known = ", ".join(sorted(engine.spec.recharge)) or "(nothing)"
        raise ValueError(f"unknown rest {label!r}. This engine rests on: {known}")
    return refilled


def _spend(draft: GameState, engine: Engine, entity_id: EntityId, counter: Slug) -> list[Fact]:
    cost = SpendCounter(entity_id=entity_id, counter=counter, amount=1)
    return apply_effect(draft, cost, engine.default_rules)


def _harm(
    draft: GameState, engine: Engine, entity_id: EntityId, delta: int, reason: str
) -> list[Fact]:
    change = AdjustCounter(entity_id=entity_id, counter=HP, delta=delta, reason=reason)
    return apply_effect(draft, change, engine.default_rules)


def _seen(draft: GameState, *actors: Entity) -> list[Fact]:
    """Acting reveals an actor, as applying an effect to them does: the roll's fact names them in
    prose the Narrator reads."""
    return [fact for actor in actors for fact in draft.reveal(actor)]


def _verdict(landed: bool) -> Slug:
    return SUCCESS if landed else FAILURE
