from random import Random
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.engines.counters import adjust, read_mechanics, write_mechanics
from aidm.engines.sheets import require_sheet
from aidm.state.apply import apply_effect, require_actor_here
from aidm.state.base import PLAYER_ID, Entity, EntityId, Frozen, Slug, Trait
from aidm.state.dice import roll_pool, roll_sum
from aidm.state.effects import Reveal
from aidm.state.facts import Fact, entity_fact
from aidm.state.world import GameState

from .actions import Attack, Save
from .mechanics import (
    DEPRIVED,
    UNARMED_DIE,
    Attribute,
    Mechanics,
    Sheet,
    armor_of,
    attribute_of,
    collapsed,
    saved,
)

IMPAIRED_DIE = 4
ENHANCED_DIE = 12
DOOMED: Slug = "doomed"


class Scar(Frozen):
    """One row of the Scars table: what the blow leaves, and the roll that may move a maximum."""

    id: Slug
    name: str
    text: str
    dice: int = Field(ge=1)
    die: int = 6
    attribute: Literal["hp", "strength", "dexterity", "willpower", "any"] = "hp"
    mode: Literal["higher", "add", "set"] = "higher"
    # Rows 8 and 10 only pay out on a passed save.
    save: Attribute | None = None
    # Rows that roll 1d6 for where the blow landed; exactly six entries when present.
    locations: tuple[str, ...] = ()
    deprived: bool = False

    @model_validator(mode="after")
    def _locations_are_a_die(self) -> Self:
        if self.locations and len(self.locations) != 6:
            raise ValueError("locations must be empty or exactly six entries, one per d6 face")
        return self


SCARS: tuple[Scar, ...] = (
    Scar(
        id="lasting-scar",
        name="Lasting Scar",
        text="(scar) A permanent mark of the blow that made it.",
        dice=1,
        locations=("Neck", "Hands", "Eye", "Chest", "Legs", "Ear"),
    ),
    Scar(
        id="rattling-blow",
        name="Rattling Blow",
        text="(scar) A blow that had to be shaken off.",
        dice=1,
    ),
    Scar(
        id="walloped",
        name="Walloped",
        text="(scar) Deprived until they rest a few hours.",
        dice=1,
        mode="add",
        deprived=True,
    ),
    Scar(
        id="broken-limb",
        name="Broken Limb",
        text="(scar) A bone that must mend before it can be trusted.",
        dice=2,
        locations=("Leg", "Leg", "Arm", "Arm", "Rib", "Skull"),
    ),
    Scar(
        id="diseased",
        name="Diseased",
        text="(scar) A sickness that has to run its course.",
        dice=2,
    ),
    Scar(
        id="head-wound",
        name="Reorienting Head Wound",
        text="(scar) The world no longer sits where it did.",
        dice=3,
        attribute="any",
    ),
    Scar(
        id="hamstrung",
        name="Hamstrung",
        text="(scar) Barely mobile until serious help and rest.",
        dice=3,
        attribute="dexterity",
    ),
    Scar(
        id="deafened",
        name="Deafened",
        text="(scar) Deaf until extraordinary aid restores their hearing.",
        dice=1,
        die=4,
        attribute="willpower",
        mode="add",
        save="willpower",
    ),
    Scar(
        id="re-brained",
        name="Re-brained",
        text="(scar) Something in the way they think has been rearranged.",
        dice=3,
        attribute="willpower",
    ),
    Scar(
        id="sundered",
        name="Sundered",
        text="(scar) An appendage is lost or useless.",
        dice=1,
        attribute="willpower",
        mode="add",
        save="willpower",
    ),
    Scar(
        id="mortal-wound",
        name="Mortal Wound",
        text="(scar) Out of action; dead within the hour unless healed.",
        dice=2,
        mode="set",
        deprived=True,
    ),
    Scar(
        id=DOOMED,
        name="Doomed",
        text="(scar) If their next critical damage save fails, they die horribly.",
        dice=3,
    ),
)

_ANY_ATTRIBUTES: tuple[Attribute, ...] = (
    "strength",
    "strength",
    "dexterity",
    "dexterity",
    "willpower",
    "willpower",
)


def resolve_save(draft: GameState, action: Save, rng: Random) -> tuple[list[Fact], Slug]:
    actor = require_actor_here(draft, action.actor_id)
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    mechanics = read_mechanics(draft, Mechanics)
    sheet = require_sheet(mechanics.sheets, actor)
    score = attribute_of(sheet, action.attribute).current
    rolled, rolled_fact = roll_pool((20,), f"{action.risk} — {action.attribute} save", rng)
    facts.append(rolled_fact)
    outcome: Slug = "pass" if saved(rolled, score) else "fail"
    facts.append(
        entity_fact(
            actor,
            "save_resolved",
            f"{action.risk} — {action.attribute} save -> {outcome}",
            {"outcome": outcome, "attribute": action.attribute, "rolled": rolled, "score": score},
        )
    )
    return facts, outcome


def resolve_attack(draft: GameState, action: Attack, rng: Random) -> tuple[list[Fact], Slug]:
    attacker = require_actor_here(draft, action.attacker_id)
    target = require_actor_here(draft, action.target_id)
    if target.id == attacker.id:
        raise ValueError(f"{attacker.name} cannot be their own target. Name who they strike.")
    if target.trait("dead") is not None:
        raise ValueError(
            f"{target.name} is already dead. Settle the scene instead of striking them again."
        )
    facts = apply_effect(draft, Reveal(entity_id=action.attacker_id))
    facts.extend(apply_effect(draft, Reveal(entity_id=action.target_id)))
    mechanics = read_mechanics(draft, Mechanics)
    _ = require_sheet(mechanics.sheets, attacker)
    sheet = require_sheet(mechanics.sheets, target)
    faces = attack_faces(draft, mechanics, attacker, action)
    kept, rolled_fact = roll_pool(faces, f"{attacker.name} strikes {target.name}", rng)
    facts.append(rolled_fact)
    damage = max(kept - armor_of(draft, mechanics, target), 0)
    damage_facts, outcome = _damage(draft, mechanics, target, sheet, damage, rng)
    facts.extend(damage_facts)
    write_mechanics(draft, mechanics)
    return facts, outcome


def attack_faces(
    state: GameState, mechanics: Mechanics, attacker: Entity, action: Attack
) -> tuple[int, ...]:
    seen: set[EntityId] = set()
    for joiner_id in action.joined_by:
        if joiner_id == attacker.id or joiner_id == action.target_id:
            raise ValueError(
                "`joined_by` names the others who strike alongside the attacker, not the "
                f"attacker or the target. Remove {joiner_id!r}."
            )
        if joiner_id in seen:
            raise ValueError(
                f"{joiner_id!r} already joins this attack. Name each joiner once in `joined_by`."
            )
        seen.add(joiner_id)
    dice = (
        weapon_die(state, mechanics, attacker, action.weapon_id),
        *(
            _best_weapon(state, mechanics, require_actor_here(state, joiner_id))
            for joiner_id in action.joined_by
        ),
    )
    match action.modifier:
        case "impaired":
            return (IMPAIRED_DIE,) * len(dice)
        case "enhanced":
            return (ENHANCED_DIE,) * len(dice)
        case "normal":
            return dice


def weapon_die(
    state: GameState, mechanics: Mechanics, attacker: Entity, weapon_id: EntityId | None
) -> int:
    if weapon_id is None:
        return UNARMED_DIE
    item = state.world.require_kind(weapon_id, "item")
    weapons = _carried_weapons(state, mechanics, attacker)
    if item.parent_id != attacker.id:
        raise ValueError(
            f"{attacker.name} does not carry {weapon_id!r}. Their weapons are: {weapons}. Leave "
            "`weapon_id` null for an unarmed blow."
        )
    damage = mechanics.rules_of(item.id).damage
    if not damage:
        raise ValueError(
            f"{item.name} deals no damage. {attacker.name}'s weapons are: {weapons}. Leave "
            "`weapon_id` null for an unarmed blow."
        )
    return damage


def _carried_weapons(state: GameState, mechanics: Mechanics, attacker: Entity) -> str:
    ids = sorted(
        item.id
        for item in state.world.children(attacker.id, "item")
        if mechanics.rules_of(item.id).damage
    )
    return ", ".join(ids) or "(none)"


def _best_weapon(state: GameState, mechanics: Mechanics, actor: Entity) -> int:
    dice = (mechanics.rules_of(item.id).damage for item in state.world.children(actor.id, "item"))
    return max((die for die in dice if die), default=UNARMED_DIE)


def _damage(
    draft: GameState, mechanics: Mechanics, target: Entity, sheet: Sheet, damage: int, rng: Random
) -> tuple[list[Fact], Slug]:
    if damage == 0:
        blocked = entity_fact(
            target, "attack_blocked", f"{target.name} takes the blow on their armour", {"damage": 0}
        )
        return [blocked], "blocked"
    lost = min(damage, sheet.hp.current)
    facts = adjust(target, "hp", sheet.hp, -lost, "struck")
    overflow = damage - lost
    if overflow == 0:
        if sheet.hp.current == 0 and target.id == PLAYER_ID:
            facts.extend(_take_scar(draft, target, sheet, lost, rng))
        return facts, "hit"
    facts.extend(adjust(target, "strength", sheet.strength, -overflow, "critical damage"))
    if sheet.strength.current == 0:
        # STR 0 is death outright; a save against zero would still pass on a natural 1.
        facts.extend(collapsed(target, sheet))
        draft.world.pending_notes = (
            *draft.world.pending_notes,
            f"{target.name} is dead. Let the story move on.",
        )
        return facts, "down"
    rolled, rolled_fact = roll_pool(
        (20,), f"{target.name} — strength save against critical damage", rng
    )
    facts.append(rolled_fact)
    if saved(rolled, sheet.strength.current):
        facts.append(
            entity_fact(
                target,
                "critical_damage_survived",
                f"{target.name} stays in the fight",
                {"strength": sheet.strength.current},
            )
        )
        return facts, "wounded"
    facts.extend(_fell(draft, target, sheet))
    return facts, "down"


def _fell(draft: GameState, target: Entity, sheet: Sheet) -> list[Fact]:
    doomed = target.trait(DOOMED) is not None
    if target.id == PLAYER_ID and not doomed:
        if target.trait("critical-damage") is None:
            target.traits.append(
                Trait(
                    id="critical-damage",
                    name="Critical Damage",
                    text="(condition) Able only to crawl weakly; dead within the hour without aid.",
                )
            )
        fact = entity_fact(
            target,
            "critical_damage",
            f"{target.name} is critically wounded",
            {"strength": sheet.strength.current},
        )
        note = f"{target.name} is critically wounded and can only crawl weakly without aid."
    else:
        if target.trait("dead") is None:
            target.traits.append(Trait(id="dead", name="Dead", text="(condition) Dead."))
        fact = entity_fact(target, "slain", f"{target.name} is dead", {})
        note = f"{target.name} is dead."
    draft.world.pending_notes = (*draft.world.pending_notes, f"{note} Let the story move on.")
    return [fact]


def _take_scar(
    draft: GameState, actor: Entity, sheet: Sheet, hp_lost: int, rng: Random
) -> list[Fact]:
    """The Scars table, indexed by the HP that blow took: the row is rolled resolver-side."""
    scar = SCARS[min(max(hp_lost, 1), 12) - 1]
    facts: list[Fact] = []
    shown, text = scar.name, scar.text
    if scar.locations:
        rolled, location_fact = roll_pool((6,), f"{scar.name} — where", rng)
        facts.append(location_fact)
        location = scar.locations[rolled - 1]
        shown, text = f"{scar.name} ({location})", f"{scar.text} ({location})"
    if actor.trait(scar.id) is None:
        actor.traits.append(Trait(id=scar.id, name=scar.name, text=text))
    if scar.deprived and actor.trait(DEPRIVED) is None:
        actor.traits.append(
            Trait(
                id=DEPRIVED,
                name="Deprived",
                text="(condition) Recovers no HP, attributes or slots until they eat and rest.",
            )
        )
    facts.append(
        entity_fact(
            actor,
            "scar_taken",
            f"{actor.name} takes a scar: {shown}",
            {"scar": scar.id, "hp_lost": hp_lost},
        )
    )
    draft.world.pending_notes = (
        *draft.world.pending_notes,
        f"{actor.name} has taken a scar: {shown} — the narration showed it landing. Show it in "
        "the fiction and let it shape what follows.",
    )
    facts.extend(_recover(sheet, scar, actor, rng))
    return facts


def _recover(sheet: Sheet, scar: Scar, actor: Entity, rng: Random) -> list[Fact]:
    facts: list[Fact] = []
    attribute = scar.attribute
    if attribute == "any":
        rolled, which_fact = roll_pool((6,), f"{scar.name} — which attribute", rng)
        facts.append(which_fact)
        attribute = _ANY_ATTRIBUTES[rolled - 1]
    if scar.save is not None:
        rolled, save_fact = roll_pool((20,), f"{scar.name} — {scar.save} save", rng)
        facts.append(save_fact)
        if not saved(rolled, attribute_of(sheet, scar.save).current):
            return facts
    recovery, recovery_fact = roll_sum((scar.die,) * scar.dice, f"{scar.name} — recovery", rng)
    facts.append(recovery_fact)
    counter = sheet.hp if attribute == "hp" else attribute_of(sheet, attribute)
    if counter.maximum is None:
        raise ValueError(f"{actor.name}'s {attribute} has no maximum to move")
    new_maximum = _moved_maximum(scar.mode, counter.maximum, recovery)
    changed = new_maximum != counter.maximum
    counter.maximum = new_maximum
    counter.current = counter.clamped(counter.current)
    if changed:
        facts.append(
            entity_fact(
                actor,
                "maximum_moved",
                f"{actor.name} maximum {attribute} -> {new_maximum}",
                {"attribute": attribute, "maximum": new_maximum},
            )
        )
    return facts


def _moved_maximum(mode: Literal["higher", "add", "set"], maximum: int, recovery: int) -> int:
    match mode:
        case "higher":
            return max(maximum, recovery)
        case "add":
            return maximum + recovery
        case "set":
            return recovery
