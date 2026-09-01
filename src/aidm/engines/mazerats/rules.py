"""Maze Rats procedures. These functions mutate only a game draft."""

from collections.abc import Mapping
from random import Random
from typing import Literal

from pydantic import Field

from aidm.core.entities import DEAD, CheckedEntityId, EntityId, Frozen, Trait
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.play import DecisionOption, PendingDecision, PendingOption
from aidm.engines.mazerats.creation import Pack, spell_name
from aidm.engines.mazerats.state import (
    ABILITIES,
    ABILITY_MAX,
    BASE_ARMOUR,
    HEALTH_PER_LEVEL,
    MAX_LEVEL,
    PATHS,
    XP_FOR_LEVEL,
    Ability,
    ActorSheet,
    CarryPosition,
    CombatState,
    ItemSheet,
    MazeRatsGame,
    MazeRatsSheet,
    MazeRatsWorld,
    Path,
    PendingAttack,
    Side,
)
from aidm.kits.entities import Entity

DANGER_TARGET = 10
DISPOSITION = "disposition"
BELT_LIMIT = 2
HANDS = 2


class DangerRoll(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the actor taking the danger roll.")
    ability: Ability = Field(description="Ability bonus used: strength, dexterity, or will.")
    danger: str = Field(
        min_length=1, description="The danger this roll determines whether they avoid."
    )
    advantage: bool = Field(default=False, description="Roll 3d6 and keep the best two dice.")
    opposed_by: CheckedEntityId | None = Field(
        default=None,
        description=(
            "Exact id of the actor resisting this action, who rolls against the actor and "
            "wins ties; null for an ordinary roll against 10."
        ),
    )
    opposed_ability: Ability | None = Field(
        default=None,
        description="Ability the resisting actor uses; null means the same one the actor used.",
    )


class Reaction(Frozen):
    actor_id: CheckedEntityId = Field(
        description="Exact id of the encountered actor whose disposition is unknown."
    )


class Attack(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the actor making this attack.")
    target_id: CheckedEntityId = Field(description="Exact id of the opposing actor being attacked.")
    weapon_id: CheckedEntityId | None = Field(
        default=None, description="Exact weapon item held by the attacker, or null for unarmed."
    )
    ambush: bool = Field(
        default=False,
        description="The attacker's side ambushes: it seizes initiative and strikes at advantage.",
    )
    shatter_shield: bool = Field(
        default=False,
        description=(
            "Only for the listed shield decision: destroy the target's shield to ignore this hit."
        ),
    )


class Stow(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the actor rearranging their gear.")
    item_id: CheckedEntityId = Field(description="Exact id of an item that actor already carries.")
    position: CarryPosition = Field(
        description="Where the item goes: hands, worn, belt, or backpack."
    )


class CastSpell(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the actor casting the spell.")
    slot: int = Field(ge=0, description="Zero-based spell-slot index to consume.")
    effect: str = Field(min_length=1, description="The fixed general effect ruling for this spell.")
    target_id: CheckedEntityId | None = Field(
        default=None, description="Exact target actor or null when the spell targets the scene."
    )


class Rest(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the actor taking the rest.")
    kind: Literal["night", "day"] = Field(
        default="night",
        description="A meal and a full night for 1 health, or a safe day for all of it.",
    )
    medicine_id: CheckedEntityId | None = Field(
        default=None, description="Optional medicine item carried by the actor to consume."
    )


class LevelUp(Frozen):
    actor_id: CheckedEntityId = Field(
        description="Exact id of the party member receiving XP or leveling."
    )
    amount: int = Field(
        default=0, ge=0, le=3, description="XP earned at session end, from zero to three."
    )
    choice: str | None = Field(
        default=None,
        description="The exact pending level-up option, or null to award XP and open it.",
    )


def danger_roll(draft: MazeRatsGame, action: DangerRoll, rng: Random) -> tuple[Fact, ...]:
    actor = _actor_here(draft, action.actor_id)
    if action.advantage:
        _check_advantage(draft.payload.world, actor, action.ability)
    total, event = _ability_roll(actor, action.ability, action.advantage, action.danger, rng)
    if action.opposed_by is None:
        avoided = total >= DANGER_TARGET
        return (_danger_fact(actor, action.danger, avoided, total, DANGER_TARGET, (event,)),)
    rival = _actor_here(draft, action.opposed_by)
    rival_ability = action.opposed_ability or action.ability
    rival_total, rival_event = _ability_roll(rival, rival_ability, False, action.danger, rng)
    dice = (event, rival_event)
    return (_danger_fact(actor, action.danger, total > rival_total, total, rival_total, dice),)


def reaction(draft: MazeRatsGame, action: Reaction, rng: Random) -> tuple[Fact, ...]:
    actor = _actor_here(draft, action.actor_id)
    if actor.trait(DISPOSITION) is not None:
        raise ValueError(f"{actor.name} already has a disposition toward the party")
    rolled, _ = roll((6,), f"Reaction for {actor.name}", rng)
    disposition = (
        "hostile"
        if rolled[0] == 1
        else "wary"
        if rolled[0] <= 3
        else "friendly"
        if rolled[0] <= 5
        else "helpful"
    )
    actor.traits.append(Trait(id=DISPOSITION, name=disposition, text="Encounter reaction."))
    return (
        Fact(
            kind="reaction",
            trace=f"{actor.name} is {disposition}",
            told=actor.known,
            entity_id=actor.id,
            card=f"Reaction: {disposition}",
            dice=(DiceEvent(label="reaction", faces=(6,), rolled=rolled),),
        ),
    )


def attack(draft: MazeRatsGame, action: Attack, rng: Random) -> tuple[Fact, ...]:
    world = draft.payload.world
    if draft.payload.pending_attack is not None:
        return _finish_pending_attack(draft, action, rng)
    attacker = _actor_here(draft, action.actor_id)
    target = _actor_here(draft, action.target_id)
    if attacker.id == target.id:
        raise ValueError("an actor cannot attack themselves")
    weapon = _weapon(world, attacker, action.weapon_id)
    combat = draft.payload.combat
    if _ranged(weapon) and combat is not None and _in_melee(world, combat, attacker.id):
        raise ValueError("a ranged weapon cannot be used while in melee combat")
    if combat is not None and action.ambush:
        raise ValueError("an ambush only opens combat, and this fight is already under way")
    if combat is None:
        combat, combat_facts = _open_combat(world, attacker.id, target.id, action.ambush, rng)
        _check_sides(combat, attacker.id, target.id)
        draft.payload.combat = combat
        if _side_of(combat, attacker.id) != combat.acting_side:
            # The initiative roll is already committed above; raising here would discard
            # it, so this side loses the swing instead of getting to re-roll initiative.
            return (*combat_facts, _initiative_lost_fact(combat))
    else:
        combat_facts = ()
        _enlist(combat, attacker.id, target.id)
        _check_sides(combat, attacker.id, target.id)
        _check_turn(combat, attacker.id)
    ambushing = combat.round == 1 and combat.ambusher == _side_of(combat, attacker.id)
    advantage = ambushing and _heavy_armour(world, attacker) is None
    total, kept, event = _attack_roll(attacker, advantage, rng)
    armour = _armour(world, target)
    critical = kept == (6, 6)
    raw = total - armour
    damage = 0 if raw <= 0 else _damage(raw, weapon, critical)
    attack_fact = _attack_fact(attacker, target, total, armour, damage, critical, event)
    if damage == 0:
        return (*combat_facts, attack_fact, *_take_action(draft, attacker.id, rng))
    if _shield(world, target) is not None:
        shielded = _shielded(draft, attacker, target, weapon, damage, rng)
        return (*combat_facts, attack_fact, *shielded)
    return (*combat_facts, attack_fact, *_land_hit(draft, target, damage, attacker.id, rng))


def stow(draft: MazeRatsGame, action: Stow, rng: Random) -> tuple[Fact, ...]:
    del rng
    world = draft.payload.world
    actor = _actor_here(draft, action.actor_id)
    item = world.require_kind(action.item_id, "item")
    sheet = item.sheet
    if item.carried_by != actor.id or not isinstance(sheet, ItemSheet):
        raise ValueError(f"{item.name} is not carried by {actor.name}")
    if sheet.position == action.position:
        raise ValueError(f"{item.name} is already carried there")
    item.sheet = ItemSheet.model_validate({**sheet.model_dump(), "position": action.position})
    check_carry(world, actor)
    return (
        Fact(
            kind="stowed",
            trace=f"{actor.name} moves {item.name} to their {action.position}",
            told=actor.known,
            entity_id=actor.id,
            card=f"{item.name}: {action.position}",
        ),
    )


def cast_spell(draft: MazeRatsGame, action: CastSpell, rng: Random) -> tuple[Fact, ...]:
    actor = _actor_here(draft, action.actor_id)
    sheet = _sheet(actor)
    slots = list(sheet.spell_slots)
    if action.slot >= len(slots) or (spell := slots[action.slot]) is None:
        raise ValueError(f"{actor.name} has no spell in slot {action.slot}")
    target = None if action.target_id is None else _actor_here(draft, action.target_id)
    combat = draft.payload.combat
    if combat is not None and actor.id in (*combat.player_side, *combat.enemy_side):
        _check_turn(combat, actor.id)
    slots[action.slot] = None
    sheet.spell_slots = tuple(slots)
    return (
        Fact(
            kind="spell_cast",
            trace=(
                f"{actor.name} cast {spell} on "
                f"{'the scene' if target is None else target.name}: {action.effect}"
            ),
            told=actor.known,
            entity_id=actor.id,
            card=f"Cast {spell}",
        ),
        *_take_action(draft, actor.id, rng),
    )


def rest(
    draft: MazeRatsGame, action: Rest, rng: Random, packs: Mapping[str, Pack]
) -> tuple[Fact, ...]:
    world = draft.payload.world
    actor = _actor_here(draft, action.actor_id)
    sheet = _sheet(actor)
    if draft.payload.combat is not None:
        raise ValueError("the party cannot rest during combat")
    medicine = (
        None if action.medicine_id is None else _medicine(world, actor, sheet, action.medicine_id)
    )
    if action.kind == "day":
        sheet.health.current = sheet.health.maximum or sheet.health.current
        healed = "fully restored"
    else:
        before = sheet.health.current
        sheet.health.current = sheet.health.clamped(before + 1)
        healed = f"healed {sheet.health.current - before}"
    sheet.dosed = False
    facts = [
        Fact(
            kind="rested",
            trace=f"{actor.name} rests for a {action.kind}: {healed}",
            told=actor.known,
            entity_id=actor.id,
            card=f"Rest: {healed}",
        )
    ]
    if medicine is not None:
        before = sheet.health.current
        sheet.health.current = sheet.health.clamped(before + 1)
        sheet.dosed = True
        del world.cast[medicine.id]
        facts.append(
            Fact(
                kind="medicine_used",
                trace=f"{actor.name} uses {medicine.name} and heals "
                f"{sheet.health.current - before}",
                told=actor.known,
                entity_id=actor.id,
                card=f"Medicine: +{sheet.health.current - before} health",
            )
        )
    if any(slot is None for slot in sheet.spell_slots):
        pack = _pack(draft, packs)
        sheet.spell_slots = tuple(
            slot if slot is not None else spell_name(pack, rng) for slot in sheet.spell_slots
        )
        facts.append(
            Fact(
                kind="spells_refreshed",
                trace=f"{actor.name}'s empty spell slots refill",
                told=actor.known,
                entity_id=actor.id,
                card="Spells refreshed",
            )
        )
    return tuple(facts)


def level_up(draft: MazeRatsGame, action: LevelUp, rng: Random) -> tuple[Fact, ...]:
    del rng
    actor = _actor_here(draft, action.actor_id)
    sheet = _sheet(actor)
    if action.choice is not None:
        if draft.payload.pending_level_up != actor.id:
            raise ValueError("no level-up choice is pending for this actor")
        draft.payload.pending_level_up = None
        return _apply_level_choice(actor, action.choice)
    if action.amount == 0:
        raise ValueError("level_up must award 1-3 XP or provide a pending choice")
    sheet.xp += action.amount
    facts = [
        Fact(
            kind="xp_awarded",
            trace=f"{actor.name} gains {action.amount} XP ({sheet.xp})",
            told=actor.known,
            entity_id=actor.id,
            card=f"XP +{action.amount}",
        )
    ]
    if sheet.level < MAX_LEVEL and sheet.xp >= XP_FOR_LEVEL[sheet.level - 1]:
        sheet.level += 1
        sheet.health.maximum = (sheet.health.maximum or sheet.health.current) + HEALTH_PER_LEVEL
        facts.append(
            Fact(
                kind="level_up",
                trace=(
                    f"{actor.name} reaches level {sheet.level} and gains "
                    f"{HEALTH_PER_LEVEL} maximum health"
                    + (" and may now retire" if sheet.level == MAX_LEVEL else "")
                ),
                told=actor.known,
                entity_id=actor.id,
                card=f"Level {sheet.level}",
            )
        )
        draft.pending = PendingDecision(
            kind="level-up",
            prompt=f"{actor.name} reached level {sheet.level}. Choose an advancement.",
            options=_level_options(sheet, actor.id),
            allows_text=False,
        )
        draft.payload.pending_level_up = actor.id
    return tuple(facts)


def check_carry(world: MazeRatsWorld, actor: Entity[MazeRatsSheet]) -> None:
    """Two hands and a two-item belt; a shield with a two-handed weapon already overruns hands."""
    hands, belt = 0, 0
    for item in world.carried_by(actor.id):
        sheet = item.sheet
        if not isinstance(sheet, ItemSheet):
            continue
        if sheet.position == "belt":
            belt += 1
        elif sheet.position == "hands":
            hands += 2 if sheet.weapon in ("heavy", "ranged") else 1
    if hands > HANDS:
        raise ValueError(
            f"{actor.name} holds more than two hands of gear: heavy and ranged weapons "
            "take both hands, and a shield takes the other one"
        )
    if belt > BELT_LIMIT:
        raise ValueError(f"{actor.name} carries more than {BELT_LIMIT} items on their belt")


def _actor_here(draft: MazeRatsGame, entity_id: EntityId) -> Entity[MazeRatsSheet]:
    actor = draft.payload.world.require_actor_here(entity_id)
    if not isinstance(actor.sheet, ActorSheet):
        raise ValueError(f"{actor.name} has no Maze Rats actor sheet")
    return actor


def _sheet(actor: Entity[MazeRatsSheet]) -> ActorSheet:
    sheet = actor.sheet
    if not isinstance(sheet, ActorSheet):
        raise ValueError(f"{actor.name} has no Maze Rats actor sheet")
    return sheet


def _pack(draft: MazeRatsGame, packs: Mapping[str, Pack]) -> Pack:
    pack = packs.get(draft.packs[0]) if draft.packs else None
    if pack is None:
        raise ValueError("spells refill from a selected table set, and none is installed")
    return pack


def _check_advantage(world: MazeRatsWorld, actor: Entity[MazeRatsSheet], ability: Ability) -> None:
    heavy = None if ability != "dexterity" else _heavy_armour(world, actor)
    if heavy is not None:
        raise ValueError(
            f"{actor.name} wears {heavy.name}: heavy armour gains no advantage on a DEX roll"
        )


def _heavy_armour(
    world: MazeRatsWorld, actor: Entity[MazeRatsSheet]
) -> Entity[MazeRatsSheet] | None:
    return next(
        (
            one
            for one in world.carried_by(actor.id)
            if isinstance(one.sheet, ItemSheet) and one.sheet.armour == "heavy"
        ),
        None,
    )


def _ability_roll(
    actor: Entity[MazeRatsSheet], ability: Ability, advantage: bool, danger: str, rng: Random
) -> tuple[int, DiceEvent]:
    faces = (6, 6, 6) if advantage else (6, 6)
    rolled, _ = roll(faces, f"{actor.name} rolls {ability} against {danger}", rng)
    kept = _best_two(rolled)
    total = sum(rolled[index] for index in kept) + _sheet(actor).ability(ability)
    return total, DiceEvent(label="danger roll", faces=faces, rolled=rolled, highlight=kept)


def _best_two(rolled: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(sorted(sorted(range(len(rolled)), key=lambda one: rolled[one], reverse=True)[:2]))


def _danger_fact(
    actor: Entity[MazeRatsSheet],
    danger: str,
    success: bool,
    total: int,
    against: int,
    dice: tuple[DiceEvent, ...],
) -> Fact:
    result = "Danger avoided" if success else "Danger strikes"
    return Fact(
        kind="danger_rolled",
        trace=f"{actor.name} rolled {total} against {against}; {danger} — {result.lower()}",
        told=actor.known,
        entity_id=actor.id,
        card=f"{result}: {total} vs {against}",
        dice=dice,
    )


def _open_combat(
    world: MazeRatsWorld, attacker_id: EntityId, target_id: EntityId, ambush: bool, rng: Random
) -> tuple[CombatState, tuple[Fact, ...]]:
    players = tuple(
        one.id
        for one in world.here()
        if one.kind == "actor"
        and one.trait(DEAD) is None
        and (one.id == world.player_id or one.id in world.companions)
    )
    enemies = tuple(one for one in (attacker_id, target_id) if one not in players)
    ambusher: Side | None = ("players" if attacker_id in players else "enemies") if ambush else None
    if ambusher is not None:
        first, dice = ambusher, ()
    else:
        first, event = _roll_initiative(rng)
        dice = (event,)
    combat = CombatState(
        player_side=players,
        enemy_side=enemies,
        first_side=first,
        acting_side=first,
        ambusher=ambusher,
    )
    opening = "an ambush seizes initiative" if ambush else "combat begins"
    return combat, (
        Fact(
            kind="combat_started",
            trace=f"{opening}; the {first} side acts first",
            told=True,
            card="Combat begins",
            dice=dice,
        ),
    )


def _initiative_lost_fact(combat: CombatState) -> Fact:
    return Fact(
        kind="initiative_lost",
        trace=f"the {combat.acting_side} side won initiative and acts first",
        told=True,
        card="Initiative lost",
    )


def _roll_initiative(rng: Random) -> tuple[Side, DiceEvent]:
    players, enemies = rng.randint(1, 6), rng.randint(1, 6)
    while players == enemies:
        enemies = rng.randint(1, 6)
    side: Side = "players" if players > enemies else "enemies"
    return side, DiceEvent(
        label="initiative",
        faces=(6, 6),
        rolled=(players, enemies),
        highlight=(0 if side == "players" else 1,),
    )


def _side_of(combat: CombatState, actor_id: EntityId) -> Side:
    return "players" if actor_id in combat.player_side else "enemies"


def _enlist(combat: CombatState, attacker_id: EntityId, target_id: EntityId) -> None:
    """Reinforcements join opposite whoever they crossed swords with."""
    for joining, against in ((attacker_id, target_id), (target_id, attacker_id)):
        enlisted = (*combat.player_side, *combat.enemy_side)
        if joining in enlisted or against not in enlisted:
            continue
        # A latecomer is absent from `acted`, so they may still act in their side's current turn.
        if _side_of(combat, against) == "players":
            combat.enemy_side = (*combat.enemy_side, joining)
        else:
            combat.player_side = (*combat.player_side, joining)


def _check_sides(combat: CombatState, attacker_id: EntityId, target_id: EntityId) -> None:
    everyone = (*combat.player_side, *combat.enemy_side)
    if attacker_id not in everyone or target_id not in everyone:
        raise ValueError("both combatants must be in the current combat")
    if (attacker_id in combat.player_side) == (target_id in combat.player_side):
        raise ValueError("combat attacks must cross sides")


def _check_turn(combat: CombatState, actor_id: EntityId) -> None:
    if _side_of(combat, actor_id) != combat.acting_side:
        raise ValueError(f"it is the turn of the {combat.acting_side} side, not this one")
    if actor_id in combat.acted:
        raise ValueError("that character has already taken their action this turn")


def _take_action(draft: MazeRatsGame, actor_id: EntityId, rng: Random) -> tuple[Fact, ...]:
    """One action each, then the side-turn ends; after both sides, initiative is rolled again."""
    combat = draft.payload.combat
    if combat is None or actor_id not in (*combat.player_side, *combat.enemy_side):
        return ()
    combat.acted = (*combat.acted, actor_id)
    acting = combat.player_side if combat.acting_side == "players" else combat.enemy_side
    if any(one not in combat.acted for one in _living_ids(draft.payload.world, acting)):
        return ()
    combat.acted = ()
    if combat.acting_side == combat.first_side:
        combat.acting_side = "enemies" if combat.acting_side == "players" else "players"
        return ()
    combat.round += 1
    combat.first_side, event = _roll_initiative(rng)
    combat.acting_side = combat.first_side
    return (
        Fact(
            kind="round_started",
            trace=f"round {combat.round} begins; the {combat.first_side} side acts first",
            told=True,
            card=f"Round {combat.round}",
            dice=(event,),
        ),
    )


def _in_melee(world: MazeRatsWorld, combat: CombatState, actor_id: EntityId) -> bool:
    """Melee is a property of the attacker: any living foe standing where they stand."""
    here = _place_of(world, actor_id)
    foes = combat.enemy_side if actor_id in combat.player_side else combat.player_side
    return any(
        world.require(one).trait(DEAD) is None and _place_of(world, one) == here for one in foes
    )


def _place_of(world: MazeRatsWorld, entity_id: EntityId) -> EntityId | None:
    place = world.location_of(world.require(entity_id))
    return None if place is None else place.id


def _weapon(
    world: MazeRatsWorld, actor: Entity[MazeRatsSheet], weapon_id: EntityId | None
) -> Entity[MazeRatsSheet] | None:
    if weapon_id is None:
        return None
    item = world.require_kind(weapon_id, "item")
    if (
        item.carried_by != actor.id
        or not isinstance(item.sheet, ItemSheet)
        or item.sheet.weapon is None
        or item.sheet.position != "hands"
    ):
        raise ValueError("the weapon must be an item held in the attacker's hands")
    check_carry(world, actor)
    return item


def _ranged(weapon: Entity[MazeRatsSheet] | None) -> bool:
    return (
        weapon is not None
        and isinstance(weapon.sheet, ItemSheet)
        and weapon.sheet.weapon == "ranged"
    )


def _attack_roll(
    attacker: Entity[MazeRatsSheet], advantage: bool, rng: Random
) -> tuple[int, tuple[int, ...], DiceEvent]:
    faces = (6, 6, 6) if advantage else (6, 6)
    rolled, _ = roll(faces, f"Attack by {attacker.name}", rng)
    keep = _best_two(rolled)
    kept = tuple(rolled[index] for index in keep)
    total = sum(kept) + _sheet(attacker).attack_bonus
    return total, kept, DiceEvent(label="attack", faces=faces, rolled=rolled, highlight=keep)


def _armour(world: MazeRatsWorld, target: Entity[MazeRatsSheet]) -> int:
    worn = max(
        (
            2 if item.sheet.armour == "heavy" else 1
            for item in world.carried_by(target.id)
            if isinstance(item.sheet, ItemSheet)
            and item.sheet.armour is not None
            and item.sheet.position == "worn"
        ),
        default=0,
    )
    shield = 1 if _shield(world, target) is not None else 0
    return BASE_ARMOUR + _sheet(target).armour + worn + shield


def _damage(raw: int, weapon: Entity[MazeRatsSheet] | None, critical: bool) -> int:
    heavy = (
        weapon is not None
        and isinstance(weapon.sheet, ItemSheet)
        and weapon.sheet.weapon == "heavy"
    )
    bonus = 1 if heavy else -1 if weapon is None else 0
    return max(1, raw + bonus) * (2 if critical else 1)


def _shield(world: MazeRatsWorld, actor: Entity[MazeRatsSheet]) -> Entity[MazeRatsSheet] | None:
    return next(
        (
            one
            for one in world.carried_by(actor.id)
            if isinstance(one.sheet, ItemSheet)
            and one.sheet.shield
            and one.sheet.position == "hands"
        ),
        None,
    )


def _attack_fact(
    attacker: Entity[MazeRatsSheet],
    target: Entity[MazeRatsSheet],
    total: int,
    armour: int,
    damage: int,
    critical: bool,
    event: DiceEvent,
) -> Fact:
    result = "critical hit" if critical and damage else "hit" if damage else "miss"
    return Fact(
        kind="attack",
        trace=f"{attacker.name} attacks {target.name}: {result} ({total} vs {armour})",
        told=attacker.known,
        entity_id=attacker.id,
        card=f"{result.capitalize()}: {damage} damage",
        dice=(event,),
    )


def _shielded(
    draft: MazeRatsGame,
    attacker: Entity[MazeRatsSheet],
    target: Entity[MazeRatsSheet],
    weapon: Entity[MazeRatsSheet] | None,
    damage: int,
    rng: Random,
) -> tuple[Fact, ...]:
    world = draft.payload.world
    if target.id == world.player_id or target.id in world.companions:
        draft.payload.pending_attack = PendingAttack(
            attacker_id=attacker.id,
            target_id=target.id,
            weapon_id=None if weapon is None else weapon.id,
            damage=damage,
        )
        draft.pending = _shield_decision(target, attacker, weapon, damage)
        return ()
    # No NPC player sits at the table, so the resolver spends an NPC's shield only to survive.
    if damage < _sheet(target).health.current:
        return _land_hit(draft, target, damage, attacker.id, rng)
    shield = _shield(world, target)
    if shield is None:
        raise ValueError(f"{target.name} has no shield to shatter")
    return (_shatter(target, shield), *_take_action(draft, attacker.id, rng))


def _shatter(target: Entity[MazeRatsSheet], shield: Entity[MazeRatsSheet]) -> Fact:
    sheet = shield.sheet
    if not isinstance(sheet, ItemSheet):
        raise ValueError(f"{shield.name} is not a Maze Rats item")
    sheet.shield = False
    return Fact(
        kind="shield_shattered",
        trace=f"{target.name}'s shield shatters and stops the blow",
        told=target.known,
        entity_id=target.id,
        card="Shield shattered",
    )


def _land_hit(
    draft: MazeRatsGame,
    target: Entity[MazeRatsSheet],
    damage: int,
    attacker_id: EntityId,
    rng: Random,
) -> tuple[Fact, ...]:
    facts = _apply_damage(target, damage)
    ending = _end_combat_if_over(draft)
    if ending:
        return (*facts, *ending)
    return (*facts, *_take_action(draft, attacker_id, rng))


def _apply_damage(target: Entity[MazeRatsSheet], damage: int) -> tuple[Fact, ...]:
    sheet = _sheet(target)
    sheet.health.current = max(0, sheet.health.current - damage)
    if sheet.health.current == 0 and target.trait(DEAD) is None:
        target.traits.append(Trait(id=DEAD, name="Dead"))
    return (
        Fact(
            kind="damage",
            trace=(
                f"{target.name} takes {damage} damage "
                f"({sheet.health.current}/{sheet.health.maximum})"
            ),
            told=target.known,
            entity_id=target.id,
            card=f"{target.name}: {damage} damage",
        ),
    )


def _end_combat_if_over(draft: MazeRatsGame) -> tuple[Fact, ...]:
    combat = draft.payload.combat
    if combat is None:
        return ()
    players_alive = _living_ids(draft.payload.world, combat.player_side)
    enemies_alive = _living_ids(draft.payload.world, combat.enemy_side)
    if players_alive and enemies_alive:
        return ()
    draft.payload.combat = None
    draft.payload.pending_attack = None
    result = "the players are defeated" if not players_alive else "the enemies are defeated"
    return (
        Fact(
            kind="combat_ended",
            trace=f"combat ends: {result}",
            told=True,
            card="Combat ends",
        ),
    )


def _living_ids(
    world: MazeRatsWorld, ids: tuple[CheckedEntityId, ...]
) -> tuple[CheckedEntityId, ...]:
    return tuple(entity_id for entity_id in ids if world.require(entity_id).trait(DEAD) is None)


def _finish_pending_attack(draft: MazeRatsGame, action: Attack, rng: Random) -> tuple[Fact, ...]:
    pending = draft.payload.pending_attack
    if pending is None:
        raise ValueError("no attack waits on a shield decision")
    if (action.actor_id, action.target_id, action.weapon_id) != (
        pending.attacker_id,
        pending.target_id,
        pending.weapon_id,
    ):
        raise ValueError("the shield decision belongs to a different attack")
    target = _actor_here(draft, pending.target_id)
    draft.payload.pending_attack = None
    if not action.shatter_shield:
        return _land_hit(draft, target, pending.damage, pending.attacker_id, rng)
    shield = _shield(draft.payload.world, target)
    if shield is None:
        raise ValueError("the target has no shield to shatter")
    return (_shatter(target, shield), *_take_action(draft, pending.attacker_id, rng))


def _shield_decision(
    target: Entity[MazeRatsSheet],
    attacker: Entity[MazeRatsSheet],
    weapon: Entity[MazeRatsSheet] | None,
    damage: int,
) -> PendingDecision:
    args_base = {
        "actor_id": attacker.id,
        "target_id": target.id,
        "weapon_id": None if weapon is None else weapon.id,
    }
    options = tuple(
        PendingOption(
            id=one.id,
            label=one.label,
            detail=one.detail,
            name="attack",
            args={**args_base, "shatter_shield": one.id == "shatter-shield"},
        )
        for one in (
            DecisionOption(
                id="shatter-shield",
                label="Shatter the shield",
                detail="Ignore this hit and destroy the shield.",
            ),
            DecisionOption(id="take-hit", label="Take the hit", detail=f"Take {damage} damage."),
        )
    )
    return PendingDecision(
        kind="shield",
        prompt=f"{target.name} is hit for {damage} damage. Shatter the shield?",
        options=options,
        allows_text=False,
    )


def _medicine(
    world: MazeRatsWorld,
    actor: Entity[MazeRatsSheet],
    sheet: ActorSheet,
    medicine_id: EntityId,
) -> Entity[MazeRatsSheet]:
    """Checked before the rest clears the dose, so two doses cannot cross a single rest."""
    if sheet.dosed:
        raise ValueError(f"{actor.name} has already taken a dose of medicine today")
    item = world.require_kind(medicine_id, "item")
    if item.carried_by != actor.id or not isinstance(item.sheet, ItemSheet):
        raise ValueError("medicine must be an item carried by the resting actor")
    if not item.sheet.medicine:
        raise ValueError("the selected item is not medicine")
    return item


def _level_options(sheet: ActorSheet, actor_id: EntityId) -> tuple[PendingOption, ...]:
    ids = (
        tuple(one for one in ABILITIES if sheet.ability(one) < ABILITY_MAX)
        if sheet.level % 2 == 0
        else ("attack-bonus", "spell-slot", *(one for one in PATHS if one not in sheet.paths))
    )
    if not ids:
        raise ValueError("every ability is already at the maximum, so this level offers no choice")
    return tuple(
        PendingOption(
            id=choice,
            label=choice.replace("-", " ").title(),
            name="level_up",
            args={"actor_id": actor_id, "choice": choice},
        )
        for choice in ids
    )


def _apply_level_choice(actor: Entity[MazeRatsSheet], choice: str) -> tuple[Fact, ...]:
    sheet = _sheet(actor)
    ability: Ability | None = next((one for one in ABILITIES if one == choice), None)
    path: Path | None = next((one for one in PATHS if one == choice), None)
    if ability is not None:
        setattr(sheet, ability, min(ABILITY_MAX, sheet.ability(ability) + 1))
    elif choice == "attack-bonus":
        sheet.attack_bonus += 1
    elif choice == "spell-slot":
        sheet.spell_slots = (*sheet.spell_slots, None)
    elif path is not None:
        if path in sheet.paths:
            raise ValueError(f"{actor.name} already walks the {path} path")
        sheet.paths = (*sheet.paths, path)
    else:
        raise ValueError(f"unknown level-up choice {choice!r}")
    return (
        Fact(
            kind="level_choice",
            trace=f"{actor.name} chooses {choice}",
            told=actor.known,
            entity_id=actor.id,
            card=f"Chosen: {choice}",
        ),
    )
