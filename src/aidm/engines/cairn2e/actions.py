from collections.abc import Mapping, Sequence
from random import Random
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.engines.counters import adjust
from aidm.engines.sheets import require_sheet
from aidm.state.apply import apply_effect, require_actor_here
from aidm.state.base import PLAYER_ID, Entity, EntityId, Frozen, Slug, Trait, require_unique
from aidm.state.dice import roll_pool, roll_sum
from aidm.state.effects import Reveal
from aidm.state.facts import CORE, Fact, entity_fact, explained
from aidm.state.plan import Followup, Resolution
from aidm.state.world import GameState

from .mechanics import (
    DEPRIVED,
    UNARMED_DIE,
    Attribute,
    Mechanics,
    Sheet,
    armor_of,
    attribute_of,
    check_load,
    collapsed,
    saved,
)

IMPAIRED_DIE = 4
ENHANCED_DIE = 12
FAVORABLE = 4
SEVERITY: tuple[Slug, ...] = ("blocked", "hit", "wounded", "down")
DOOMED: Slug = "doomed"
GRAVE: frozenset[str] = frozenset({"scar_taken", "critical_damage", "slain", "attribute_emptied"})


class Save(Frozen):
    """A roll to avoid a bad outcome: d20 under the attribute, where 1 always passes and 20 always
    fails."""

    actor_id: EntityId = Field(
        description="Exact id of the actor at risk: the player, or an actor here with them; when "
        "two sides oppose each other, whoever is most at risk saves."
    )
    attribute: Attribute = Field(
        description="Which attribute answers: strength for force and endurance, dexterity for "
        "speed, reflexes and stealth, willpower for nerve, persuasion, morale, panic and reading "
        "a spell."
    )
    risk: str = Field(min_length=1, description="What the actor avoids by passing, in one line.")


class Attack(Frozen):
    """One attack, which always hits: the weapon die less the target's armor comes off their HP."""

    attacker_id: EntityId = Field(
        description="Exact id of the actor striking: the player, or an actor here with them."
    )
    target_ids: tuple[EntityId, ...] = Field(
        min_length=1,
        description="Exact ids of the actors struck, each here with the player. Name more than "
        "one only for a blast that catches them all: each takes its own roll of the same pool.",
    )
    weapon_ids: tuple[EntityId, ...] = Field(
        default=(),
        description="Exact ids of the weapons the attacker strikes with, each one they carry; "
        "empty is an unarmed blow, always d4. Name two when they fight with both — every die is "
        "rolled and only the single highest counts.",
    )
    modifier: Literal["normal", "impaired", "enhanced"] = Field(
        default="normal",
        description="`impaired` (a position of weakness: cover, bound hands, a distant shot) "
        "rolls d4 whatever the weapon; `enhanced` (a position of advantage: a helpless foe, a "
        "daring manoeuvre) rolls d12.",
    )
    joined_by: tuple[EntityId, ...] = Field(
        default=(),
        description="Other actors here striking the same targets in the same round; every damage "
        "die is rolled and only the single highest counts.",
    )


class Fate(Frozen):
    """The die of fate: one d6 on an outcome nobody's skill decides, where 4 or more favors the
    player."""

    question: str = Field(
        min_length=1,
        description="The uncertain question the die answers, phrased so that a favorable answer "
        "is the one the player wants.",
    )


class Reaction(Frozen):
    """The reaction table: 2d6 for how an NPC the player has just met takes them."""

    actor_id: EntityId = Field(
        description="Exact id of the NPC reacting, who must be here with the player; never the "
        "player themselves."
    )


class PassTime(Frozen):
    """Downtime: full days pass in the fiction — a journey, a camp, a week under a healer's care —
    and any actor named in `mended_ids` whose scars waited on recovery is paid out. The engine
    adds each deprived character's daily Fatigue and rolls that payout itself — never write
    either yourself."""

    days: int = Field(
        ge=0,
        description="How many full days pass; 0 when only a few hours' rest completes a "
        "recovery named in `mended_ids`.",
    )
    mended_ids: tuple[EntityId, ...] = Field(
        default=(),
        description="Exact ids of actors here whose waiting scars this rest heals — name one "
        "only when the fiction has actually mended them, not merely rested them.",
    )
    why: str = Field(
        min_length=1,
        description="What passes the time, in one line, for the player.",
    )

    @model_validator(mode="after")
    def _moves_something(self) -> Self:
        if not self.days and not self.mended_ids:
            raise ValueError("pass-time passes days, completes a recovery, or both")
        return self


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
    # Rows whose SRD text defers the payout to rest or recovery, paid out by `pass-time`.
    until_mended: bool = False

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
        until_mended=True,
    ),
    Scar(
        id="broken-limb",
        name="Broken Limb",
        text="(scar) A bone that must mend before it can be trusted.",
        dice=2,
        locations=("Leg", "Leg", "Arm", "Arm", "Rib", "Skull"),
        until_mended=True,
    ),
    Scar(
        id="diseased",
        name="Diseased",
        text="(scar) A sickness that has to run its course.",
        dice=2,
        until_mended=True,
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
        until_mended=True,
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
        until_mended=True,
    ),
    Scar(
        id=DOOMED,
        name="Doomed",
        text="(scar) If their next critical damage save fails, they die horribly.",
        dice=3,
    ),
)

# The rows whose SRD text defers the payout, keyed by id: membership and payout in one place.
MENDING: Mapping[Slug, Scar] = {scar.id: scar for scar in SCARS if scar.until_mended}

_ANY_ATTRIBUTES: tuple[Attribute, ...] = (
    "strength",
    "strength",
    "dexterity",
    "dexterity",
    "willpower",
    "willpower",
)


def reaction_for(total: int) -> Slug:
    """The SRD's five rows, hostile through helpful, read off 2d6."""
    if total == 2:
        return "hostile"
    if total <= 5:
        return "wary"
    if total <= 8:
        return "curious"
    if total <= 11:
        return "kind"
    return "helpful"


def resolve_fate(draft: GameState, action: Fate, rng: Random) -> Resolution:
    kept, rolled = roll_pool((6,), f"die of fate — {action.question}", rng)
    outcome: Slug = "favorable" if kept >= FAVORABLE else "unfavorable"
    draft.world.pending_notes = (
        *draft.world.pending_notes,
        f"The die of fate answered {action.question} — {outcome}. Take it as settled and play out "
        "what it means.",
    )
    fact = Fact(
        source=CORE,
        kind="fate_rolled",
        trace=f"die of fate — {action.question} -> {outcome}",
        narrator=f"the die of fate answers {action.question}: {outcome}",
        data={"question": action.question, "outcome": outcome, "rolled": kept},
    )
    return Resolution(facts=(rolled, fact), outcome=outcome)


def resolve_reaction(draft: GameState, action: Reaction, rng: Random) -> Resolution:
    if action.actor_id == PLAYER_ID:
        raise ValueError(
            "the reaction table is rolled for an NPC meeting the player, never for the player. "
            "Name who reacts."
        )
    actor = require_actor_here(draft, action.actor_id)
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    total, rolled = roll_sum((6, 6), f"reaction — {actor.name}", rng)
    facts.append(rolled)
    outcome = reaction_for(total)
    facts.append(
        entity_fact(
            actor,
            "reaction_rolled",
            f"{actor.name} takes them: {outcome}",
            {"outcome": outcome, "rolled": total},
        )
    )
    draft.world.pending_notes = (
        *draft.world.pending_notes,
        f"{actor.name} takes the player as {outcome} — play them that way from here.",
    )
    return Resolution(facts=tuple(facts), outcome=outcome)


def resolve_save(draft: GameState, action: Save, rng: Random) -> Resolution:
    actor = require_actor_here(draft, action.actor_id)
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    mechanics = draft.mechanics_as(Mechanics)
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
    return Resolution(facts=tuple(facts), outcome=outcome)


def resolve_attack(draft: GameState, action: Attack, rng: Random) -> Resolution:
    attacker = require_actor_here(draft, action.attacker_id)
    facts = apply_effect(draft, Reveal(entity_id=action.attacker_id))
    mechanics = draft.mechanics_as(Mechanics)
    _ = require_sheet(mechanics.sheets, attacker)
    seen: set[EntityId] = set()
    for target_id in action.target_ids:
        if target_id in seen:
            raise ValueError(
                f"{target_id!r} is named twice. Name each target once in `target_ids`."
            )
        seen.add(target_id)
        target = require_actor_here(draft, target_id)
        if target.id == attacker.id:
            raise ValueError(f"{attacker.name} cannot be their own target. Name who they strike.")
        if target.trait("dead") is not None:
            raise ValueError(
                f"{target.name} is already dead. Settle the scene instead of striking them again."
            )
        # Every target is checked before the first one is struck, so a blast refuses whole.
        _ = require_sheet(mechanics.sheets, target)
    faces = attack_faces(draft, mechanics, attacker, action)
    outcomes: dict[EntityId, Slug] = {}
    for target_id in action.target_ids:
        target_facts, outcome = _strike(draft, mechanics, attacker, target_id, faces, rng)
        facts.extend(target_facts)
        outcomes[target_id] = outcome
    return Resolution(facts=tuple(facts), outcome=_worst(outcomes), followup=_followup(facts))


def _strike(
    draft: GameState,
    mechanics: Mechanics,
    attacker: Entity,
    target_id: EntityId,
    faces: tuple[int, ...],
    rng: Random,
) -> tuple[list[Fact], Slug]:
    facts = apply_effect(draft, Reveal(entity_id=target_id))
    target = draft.world.require(target_id)
    sheet = require_sheet(mechanics.sheets, target)
    kept, rolled_fact = roll_pool(faces, f"{attacker.name} strikes {target.name}", rng)
    facts.append(rolled_fact)
    damage = max(kept - armor_of(draft, mechanics, target), 0)
    damage_facts, outcome = _damage(draft, mechanics, target, sheet, damage, rng)
    facts.extend(damage_facts)
    return facts, outcome


def _worst(outcomes: Mapping[EntityId, Slug]) -> Slug:
    """A blast reports the harshest outcome it landed — the player's own when they are struck."""
    own = outcomes.get(PLAYER_ID)
    return own if own is not None else max(outcomes.values(), key=SEVERITY.index)


def _followup(facts: Sequence[Fact]) -> Followup:
    """Only the player's own grave moment settles the turn; an NPC going down is a consequence."""
    grave = any(fact.kind in GRAVE and fact.data.get("entity_id") == PLAYER_ID for fact in facts)
    return "settle" if grave else "continue"


def attack_faces(
    state: GameState, mechanics: Mechanics, attacker: Entity, action: Attack
) -> tuple[int, ...]:
    seen: set[EntityId] = set()
    for joiner_id in action.joined_by:
        if joiner_id == attacker.id or joiner_id in action.target_ids:
            raise ValueError(
                "`joined_by` names the others who strike alongside the attacker, not the "
                f"attacker or a target. Remove {joiner_id!r}."
            )
        if joiner_id in seen:
            raise ValueError(
                f"{joiner_id!r} already joins this attack. Name each joiner once in `joined_by`."
            )
        seen.add(joiner_id)
    dice = (
        *weapon_faces(state, mechanics, attacker, action.weapon_ids),
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


def weapon_faces(
    state: GameState, mechanics: Mechanics, attacker: Entity, weapon_ids: tuple[EntityId, ...]
) -> tuple[int, ...]:
    if not weapon_ids:
        return (UNARMED_DIE,)
    weapons = _carried_weapons(state, mechanics, attacker)
    seen: set[EntityId] = set()
    faces: list[int] = []
    for weapon_id in weapon_ids:
        if weapon_id in seen:
            raise ValueError(
                f"{weapon_id!r} already strikes in this attack. Name each weapon once in "
                "`weapon_ids`."
            )
        seen.add(weapon_id)
        item = state.world.require_kind(weapon_id, "item")
        if item.parent_id != attacker.id:
            raise ValueError(
                f"{attacker.name} does not carry {weapon_id!r}. Their weapons are: {weapons}. "
                "Leave `weapon_ids` empty for an unarmed blow."
            )
        damage = mechanics.rules_of(item.id).damage
        if not damage:
            raise ValueError(
                f"{item.name} deals no damage. {attacker.name}'s weapons are: {weapons}. Leave "
                "`weapon_ids` empty for an unarmed blow."
            )
        faces.append(damage)
    return tuple(faces)


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
    note = (
        f"{actor.name} has taken a scar: {shown} — the narration showed it landing. Show it in "
        "the fiction and let it shape what follows."
    )
    if scar.until_mended:
        note += (
            " Its recovery waits: when the fiction has mended them, name them in `pass-time`'s "
            "`mended_ids` and the engine pays it out."
        )
    draft.world.pending_notes = (*draft.world.pending_notes, note)
    if scar.until_mended:
        if scar.id not in sheet.mending:
            sheet.mending.append(scar.id)
    else:
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


def resolve_pass_time(draft: GameState, action: PassTime, rng: Random) -> Resolution:
    mechanics = draft.mechanics_as(Mechanics)
    mended: list[tuple[Entity, Sheet]] = []
    seen: set[EntityId] = set()
    for mended_id in action.mended_ids:
        if mended_id in seen:
            raise ValueError(f"{mended_id!r} is named twice. Name each actor once in `mended_ids`.")
        seen.add(mended_id)
        actor = require_actor_here(draft, mended_id)
        if actor.trait("dead") is not None:
            raise ValueError(f"{actor.name} is dead and past mending. Let the story move on.")
        sheet = require_sheet(mechanics.sheets, actor)
        if not sheet.mending:
            raise ValueError(
                f"{actor.name} has no scar waiting on recovery. Lift an ordinary condition with "
                "`trait-change` instead."
            )
        mended.append((actor, sheet))
    facts: list[Fact] = []
    if action.days:
        mechanics.day += action.days
        facts.append(
            Fact(
                source=CORE,
                kind="time_passed",
                trace=explained(f"{action.days} day(s) pass -> day {mechanics.day}", action.why),
                data={"days": action.days, "day": mechanics.day},
            )
        )
    for entity_id, sheet in mechanics.sheets.items():
        actor = draft.world.find(entity_id)
        if actor is None or actor.trait("dead") is not None:
            continue
        if actor.trait(DEPRIVED) is not None:
            facts.extend(
                adjust(
                    actor, "fatigue", sheet.fatigue, action.days, "deprived: one Fatigue per day"
                )
            )
    for actor, sheet in mended:
        for scar_id in tuple(sheet.mending):
            scar = MENDING[scar_id]
            held = actor.trait(scar_id)
            if held is not None:
                actor.traits.remove(held)
            facts.append(
                entity_fact(
                    actor,
                    "scar_mended",
                    f"{actor.name}'s {scar.name} has mended",
                    {"scar": scar.id},
                )
            )
            facts.extend(_recover(sheet, scar, actor, rng))
        sheet.mending.clear()
    facts.extend(check_load(draft, mechanics))
    return Resolution(facts=tuple(facts))


def check_mending(state: GameState, mechanics: Mechanics) -> None:
    for entity_id, sheet in mechanics.sheets.items():
        if unknown := sorted(set(sheet.mending) - set(MENDING)):
            raise ValueError(f"{entity_id!r} waits on scars no row defers: {unknown}")
        require_unique(f"mending scars on {entity_id!r}", sheet.mending)
        actor = state.world.find(entity_id)
        if actor is None:
            continue
        if missing := sorted(one for one in sheet.mending if actor.trait(one) is None):
            raise ValueError(f"{entity_id!r} waits on scars they do not carry: {missing}")
