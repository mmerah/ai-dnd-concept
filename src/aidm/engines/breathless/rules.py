from dataclasses import dataclass
from random import Random
from typing import ClassVar, Literal, Self, get_args

from pydantic import Field, model_validator

from aidm.engines.core import (
    Decision,
    EntityRules,
    SheetBase,
    adjust,
    pool,
    rules,
)
from aidm.state.actions import require_actor_here, roll_pool
from aidm.state.entities import (
    CheckedEntityId,
    Counter,
    Entity,
    EntityId,
    Frozen,
    slug,
)
from aidm.state.facts import EventBadge, Fact, MechanicEvent, entity_fact
from aidm.state.model import Game
from aidm.state.play import DecisionOption

type Die = Literal[4, 6, 8, 10, 12]
type Skill = Literal["Bash", "Dash", "Sneak", "Shoot", "Think", "Sway"]


@dataclass(frozen=True, slots=True)
class Rules:
    floor: Die = 4  # skills never go below d4; an item at d4 has broken, been lost, or faded
    loot_start: Die = 12
    stunt_die: Die = 12
    starting_item: Die = 10
    fail_at: int = 2  # 1-2 fails with a complication
    mixed_at: int = 4  # 3-4 succeeds with a complication
    trouble_here_at: int = 2  # loot 1-2
    trouble_ahead_at: int = 4  # loot 3-4
    med_kit_at: int = 9  # loot 9+ may be a med kit instead of the item
    med_kit_clears: int = 2
    vulnerable_at: int = 4
    carry: int = 3  # items besides the one med kit


RULES = Rules()

LADDER: tuple[Die, ...] = get_args(Die.__value__)
SKILLS: tuple[Skill, ...] = get_args(Skill.__value__)


def stepped(die: Die) -> Die:
    index = LADDER.index(die)
    return LADDER[max(index - 1, 0)]


def loot_die(kept: int) -> Die:
    # 5-6 is a d6 item, 7-8 a d8, 9-10 a d10, 11-12 a d12.
    return LADDER[(kept - 3) // 2]


class Sheet(SheetBase):
    job: str = ""
    pronouns: str = ""
    # Ratings as created; `worn` is where each skill stands now, reset by Catch Your Breath.
    skills: dict[Skill, Die] = Field(default_factory=dict)
    worn: dict[Skill, Die] = Field(default_factory=dict)
    loot: Die = RULES.loot_start
    stress: Counter = Counter(current=0, maximum=RULES.vulnerable_at)
    stunted: bool = False
    med_kit: bool = False

    @model_validator(mode="after")
    def _six_skills(self) -> Self:
        for skill in SKILLS:
            self.skills.setdefault(skill, RULES.floor)
            self.worn.setdefault(skill, self.skills[skill])
        if over := sorted(skill for skill in SKILLS if self.worn[skill] > self.skills[skill]):
            raise ValueError(f"a worn skill cannot stand above its rating: {over}")
        return self

    @property
    def vulnerable(self) -> bool:
        return self.stress.current >= RULES.vulnerable_at

    def rested(self) -> bool:
        return self.worn == self.skills and self.loot == RULES.loot_start and not self.stunted

    def rows(self) -> tuple[tuple[str, str], ...]:
        skills = ", ".join(
            f"{skill} d{self.worn[skill]}"
            + (f" (rated d{self.skills[skill]})" if self.worn[skill] != self.skills[skill] else "")
            for skill in SKILLS
        )
        return (
            ("Job", self.job),
            ("Pronouns", self.pronouns),
            ("Skills", skills),
            ("Loot die", f"d{self.loot}"),
            ("Stress", pool(self.stress) + (", vulnerable" if self.vulnerable else "")),
            ("Stunt", "spent until they catch their breath" if self.stunted else ""),
            ("Med kit", "yes" if self.med_kit else ""),
        )


class ItemSheet(EntityRules):
    die: Die

    def rows(self) -> tuple[tuple[str, str], ...]:
        spent = self.die == RULES.floor
        return (("Die", "d4: broken, lost, or faded" if spent else f"d{self.die}"),)


class Pack(Frozen):
    name: str
    source: str
    license: str
    skills: tuple[DecisionOption, ...] = Field(min_length=1)
    jobs: tuple[str, ...] = ()
    weapons: tuple[str, ...] = ()
    long_range_weapons: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()
    complications: tuple[str, ...] = ()
    missions: tuple[str, ...] = ()


class Check(Frozen):
    actor_id: CheckedEntityId = Field(
        description="Exact id of the player or actor here who takes the action."
    )
    goal: str = Field(min_length=1, description="The actor's goal, in one line.")
    risk: str = Field(
        min_length=1,
        description="One-line cost of a bad roll, told to the player first. No roll without one.",
    )
    dangerous: bool = Field(
        description="True when failing could harm the actor; a vulnerable actor may then die."
    )
    skill: Skill | Literal[""] = Field(
        default="", description="The skill rolled, or empty when an item or a stunt is used."
    )
    item_id: CheckedEntityId | None = Field(
        default=None,
        description="Exact id of a carried item rolled in place of a skill, or null.",
    )
    stunt: bool = Field(
        default=False, description="True to roll a d12 stunt instead of a skill or item."
    )
    helper_id: CheckedEntityId | None = Field(
        default=None,
        description="Exact id of an ally here who also rolls and shares the risk, or null.",
    )
    helper_skill: Skill | Literal[""] = Field(
        default="", description="The helper's skill, or empty when they use an item."
    )
    helper_item_id: CheckedEntityId | None = Field(
        default=None, description="Exact id of the item the helper rolls instead, or null."
    )
    helper_stunt: bool = Field(default=False, description="True when the helper stunts instead.")

    @model_validator(mode="after")
    def _one_die_each(self) -> Self:
        if sum((bool(self.skill), self.item_id is not None, self.stunt)) != 1:
            raise ValueError("a check rolls exactly one of `skill`, `item_id` or `stunt`")
        helper_dice = sum(
            (bool(self.helper_skill), self.helper_item_id is not None, self.helper_stunt)
        )
        if self.helper_id is None and helper_dice:
            raise ValueError("`helper_skill`, `helper_item_id` and `helper_stunt` need `helper_id`")
        if self.helper_id is not None and helper_dice != 1:
            raise ValueError(
                "a helper rolls exactly one of `helper_skill`, `helper_item_id` or `helper_stunt`"
            )
        return self


class StakedCheck(Check, Decision):
    kind: ClassVar = "stake"

    def resolve(self, draft: Game, option_id: str, rng: Random) -> tuple[Fact, ...]:
        # `proceed` is the only option the engine offers; the player's own words revise instead.
        del option_id
        return resolve_check(draft, self, rng)


class LuckTest(Frozen):
    subject: str = Field(min_length=1, description="What may happen, in one line.")
    die: Die = Field(description="Die rated by the odds: d4 unlikely, d12 near certain.")


class LootCheck(Frozen):
    actor_id: CheckedEntityId = Field(
        description="Exact id of the player or actor here who scavenges."
    )
    seeking: str = Field(
        min_length=1, description="The item they hope to find, named like `a crowbar`."
    )


MED_KIT_PROMPT = "The loot roll is high enough for a med kit. Take the item found, or a med kit?"


class Loot(Decision):
    """A 9+ loot roll: the SRD gives the player the choice, so the choice is theirs to make."""

    kind: ClassVar = "loot"

    actor_id: EntityId
    seeking: str
    rating: Die

    def resolve(self, draft: Game, option_id: str, rng: Random) -> tuple[Fact, ...]:
        del rng
        actor = draft.world.require_kind(self.actor_id, "actor")
        if option_id == "med-kit":
            with rules(actor, Sheet) as sheet:
                sheet.med_kit = True
            card = MechanicEvent(title="Med kit", icon="medical_services")
            return (entity_fact(actor, "loot_found", "took a med kit", event=card),)
        return (_found(draft, actor, self.seeking, self.rating),)


class ChangeStress(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or an actor here.")
    amount: int = Field(description="Positive adds stress; negative clears it.")
    why: str = Field(min_length=1, description="The complication or the rest, in one line.")


class Breathe(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or a party member here.")


def outcome_for(kept: int) -> str:
    if kept <= RULES.fail_at:
        return "fail"
    if kept <= RULES.mixed_at:
        return "mixed"
    return "success"


def _rolls(
    draft: Game, actor: Entity, skill: str, item_id: EntityId | None, stunt: bool
) -> tuple[Die, str, list[Fact]]:
    """The die one roller brings, worn down after the roll: the trace line and facts of the wear."""
    if stunt:
        with rules(actor, Sheet) as sheet:
            if sheet.stunted:
                raise ValueError(
                    f"{actor.name} has pulled a stunt already; they catch their breath before "
                    "another"
                )
            sheet.stunted = True
        return RULES.stunt_die, "stunt d12", []
    if item_id is not None:
        item = draft.world.require_kind(item_id, "item")
        if item.parent_id != actor.id:
            raise ValueError(f"{actor.name} does not carry {item.name}")
        with rules(item, ItemSheet) as held:
            if held.die == RULES.floor:
                raise ValueError(f"{item.name} is at d4: broken, lost, or faded. It rolls no more")
            face = held.die
            held.die = stepped(face)
            spent = f"d{held.die}"
            if held.die == RULES.floor:
                # Broken, lost, or faded: it leaves the backpack and frees its slot.
                item.parent_id = draft.world.location_of(actor)
                spent = "d4: broken, lost, or faded, out of the backpack"
        trace = f"{item.name} d{face} -> {spent}"
        return face, f"{item.name} d{face}", [entity_fact(item, "item_worn", trace)]
    if skill not in SKILLS:
        raise ValueError("a check rolls a skill, an item, or a stunt")
    with rules(actor, Sheet) as sheet:
        face = sheet.worn[skill]
        sheet.worn[skill] = stepped(face)
        trace = f"{draft.label(actor)} {skill} d{face} -> d{sheet.worn[skill]}"
    return face, f"{skill} d{face}", [entity_fact(actor, "skill_worn", trace)]


def resolve_stake(draft: Game, action: StakedCheck) -> tuple[Fact, ...]:
    if action.actor_id != draft.player_id:
        raise ValueError("stake only the player's check; roll an actor's check directly")
    _ = resolve_check(draft.draft(), action, Random(0))
    draft.pending = action.pending(
        f"{action.risk}\n\nProceed, or change your plan.",
        (DecisionOption(id="proceed", label="Proceed"),),
    )
    return ()


def resolve_check(draft: Game, action: Check, rng: Random) -> tuple[Fact, ...]:
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    face, badge, worn = _rolls(draft, actor, action.skill, action.item_id, action.stunt)
    faces, badges = [face], [EventBadge(label="Rolls", value=badge)]
    rollers = [actor]
    if action.helper_id is not None:
        if action.helper_id == actor.id:
            raise ValueError(f"{actor.name} cannot help themselves; leave `helper_id` null")
        helper = require_actor_here(draft, action.helper_id)
        facts.extend(draft.reveal(helper))
        helped, helper_badge, helper_worn = _rolls(
            draft, helper, action.helper_skill, action.helper_item_id, action.helper_stunt
        )
        faces.append(helped)
        badges.append(EventBadge(label=f"{helper.name} helps", value=helper_badge))
        worn.extend(helper_worn)
        rollers.append(helper)

    pooled, rolled = roll_pool(faces, f"{action.goal} — {badge}", rng, label="Check")
    outcome = outcome_for(pooled.kept)
    effects = [fact.trace for fact in worn]
    trace = f"{action.goal} (risk: {action.risk}) -> {outcome}"
    if outcome == "fail" and action.dangerous:
        # Everyone who rolled shares the risk, so each vulnerable roller is named.
        for roller in rollers:
            if Sheet.model_validate(roller.rules).vulnerable:
                warning = (
                    f"{roller.name} is vulnerable and failed a dangerous action: taken out, or dead"
                )
                effects.append(warning)
                trace += f". {warning}"
    card = MechanicEvent(
        title="Check", badges=tuple(badges), dice=(pooled,), outcome=outcome, effects=tuple(effects)
    )
    facts.extend((rolled, entity_fact(actor, "check_resolved", trace, event=card), *worn))
    return tuple(facts)


def resolve_luck_test(draft: Game, action: LuckTest, rng: Random) -> tuple[Fact, ...]:
    del draft
    die, rolled = roll_pool((action.die,), f"luck — {action.subject}", rng, label="Luck")
    outcome = outcome_for(die.kept)
    card = MechanicEvent(title="Luck", dice=(die,), outcome=outcome, icon="casino")
    return (rolled, Fact(kind="luck_tested", trace=f"{action.subject}: {outcome}", event=card))


def resolve_loot(draft: Game, action: LootCheck, rng: Random) -> tuple[Fact, ...]:
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    with rules(actor, Sheet) as sheet:
        face = sheet.loot
        sheet.loot = stepped(face)
        held_med_kit = sheet.med_kit
    die, rolled = roll_pool((face,), f"loot — {action.seeking}", rng, label="Loot")
    facts.append(rolled)
    wear = f"loot die d{face} -> d{stepped(face)}"
    if die.kept <= RULES.trouble_ahead_at:
        here = die.kept <= RULES.trouble_here_at
        found = "trouble is here" if here else "there is trouble ahead"
        draft.world.pending_notes = (
            *draft.world.pending_notes,
            f"The loot check found {found} instead of {action.seeking}: show it "
            + ("arriving now." if here else "coming, before it bites."),
        )
        card = MechanicEvent(title="Loot", dice=(die,), outcome=found, effects=(wear,))
        facts.append(entity_fact(actor, "loot_found", f"{found} — {wear}", event=card))
        return tuple(facts)
    rating = loot_die(die.kept)
    if die.kept >= RULES.med_kit_at and not held_med_kit:
        choice = Loot(actor_id=actor.id, seeking=action.seeking, rating=rating)
        draft.pending = choice.pending(
            MED_KIT_PROMPT,
            (
                DecisionOption(id="item", label=f"Take {action.seeking} (d{rating})"),
                DecisionOption(id="med-kit", label="Take a med kit"),
            ),
            allows_text=False,
        )
        outcome = f"a d{rating} item or a med kit"
        card = MechanicEvent(title="Loot", dice=(die,), outcome=outcome, effects=(wear,))
        facts.append(entity_fact(actor, "loot_found", f"{outcome} — {wear}", event=card))
        return tuple(facts)
    card = MechanicEvent(title="Loot", dice=(die,), outcome=f"a d{rating} item", effects=(wear,))
    facts.append(entity_fact(actor, "loot_found", f"a d{rating} item — {wear}", event=card))
    facts.append(_found(draft, actor, action.seeking, rating))
    return tuple(facts)


def _found(draft: Game, actor: Entity, seeking: str, rating: Die) -> Fact:
    # A full backpack does not stop the find: the item lies where they stand until they drop one.
    full = len(draft.world.children(actor.id, "item")) >= RULES.carry
    item = Entity(
        id=EntityId(slug(seeking, draft.world.all_ids())),
        kind="item",
        name=seeking,
        brief=seeking,
        known=True,
        parent_id=draft.world.location_of(actor) if full else actor.id,
        rules={"die": rating},
    )
    where = f", left here: the backpack holds {RULES.carry}" if full else ""
    card = MechanicEvent(title=f"{item.name}, d{rating}{where}", icon="backpack")
    found = f"new item: {item.name}[{item.id}] d{rating}{where}"
    return draft.add(item).model_copy(update={"trace": found, "event": card})


def apply_change_stress(draft: Game, action: ChangeStress) -> list[Fact]:
    if action.amount == 0:
        raise ValueError("changing stress moves the counter; zero moves nothing")
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    with rules(actor, Sheet) as sheet:
        facts.extend(
            adjust(draft, actor, "stress", sheet.stress, action.amount, action.why, "monitor_heart")
        )
        vulnerable = sheet.vulnerable
    if action.amount > 0 and vulnerable:
        facts.append(
            entity_fact(
                actor,
                "vulnerable",
                f"{draft.label(actor)} is vulnerable: failing a dangerous action may take them "
                "out or kill them",
            )
        )
    return facts


def apply_catch_breath(draft: Game, action: Breathe) -> list[Fact]:
    actor = require_actor_here(draft, action.actor_id)
    with rules(actor, Sheet) as sheet:
        sheet.worn = dict(sheet.skills)
        sheet.loot = RULES.loot_start
        sheet.stunted = False
    draft.world.pending_notes = (
        *draft.world.pending_notes,
        f"{actor.name} caught their breath: introduce a new complication for the group now, "
        "and put it in the world so it stays: reveal or move an actor, add a trait, add stress, "
        "or stake a check.",
    )
    card = MechanicEvent(title=f"{actor.name} catches their breath", icon="air")
    trace = f"{draft.label(actor)} caught their breath: skills, loot die and stunt reset"
    return [entity_fact(actor, "breath_caught", trace, event=card)]


def apply_use_med_kit(draft: Game, action: Breathe) -> list[Fact]:
    actor = require_actor_here(draft, action.actor_id)
    with rules(actor, Sheet) as sheet:
        if not sheet.med_kit:
            raise ValueError(f"{actor.name} carries no med kit")
        sheet.med_kit = False
        return adjust(
            draft,
            actor,
            "stress",
            sheet.stress,
            -RULES.med_kit_clears,
            "used the med kit",
            "healing",
        )


def breathers(state: Game) -> tuple[tuple[str, Breathe], ...]:
    return tuple(
        (
            "Catch your breath"
            if member.id == state.player_id
            else f"{member.name} catches their breath",
            Breathe(actor_id=member.id),
        )
        for member, sheet in _party(state)
        if not sheet.rested()
    )


def med_kit_holders(state: Game) -> tuple[tuple[str, Breathe], ...]:
    return tuple(
        (
            "Use the med kit"
            if member.id == state.player_id
            else f"{member.name} uses their med kit",
            Breathe(actor_id=member.id),
        )
        for member, sheet in _party(state)
        if sheet.med_kit and sheet.stress.current > 0
    )


def _party(state: Game) -> tuple[tuple[Entity, Sheet], ...]:
    """Only a member the scenario gave rules plays by a sheet; the rest travel along."""
    members = (state.world.require(one) for one in (state.player_id, *state.world.party))
    return tuple((member, Sheet.model_validate(member.rules)) for member in members if member.rules)
