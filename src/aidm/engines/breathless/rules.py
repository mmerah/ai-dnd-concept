from random import Random
from typing import Literal, Self, get_args

from pydantic import Field, model_validator

from aidm.engines.core import (
    adjust,
    keep_highest,
    mechanics_of,
    pool,
    rules,
    sheet_of,
    stake_decision,
)
from aidm.state.entities import (
    CheckedEntityId,
    Counter,
    Entity,
    EntityId,
    Frozen,
    Mutable,
    slug,
)
from aidm.state.facts import Fact, entity_fact
from aidm.state.model import Game
from aidm.state.play import DecisionOption, PendingDecision, PendingOption
from aidm.state.tools import director_tool
from aidm.world.actions import require_actor_here
from aidm.world.topology import children, location_of

type Die = Literal[4, 6, 8, 10, 12]
type Skill = Literal["Bash", "Dash", "Sneak", "Shoot", "Think", "Sway"]


DIE_FLOOR: Die = 4  # skills never go below d4; an item at d4 has broken, been lost, or faded
LOOT_START: Die = 12
STUNT_DIE: Die = 12
STARTING_ITEM: Die = 10
FAIL_AT = 2  # 1-2 fails with a complication
MIXED_AT = 4  # 3-4 succeeds with a complication
TROUBLE_HERE_AT = 2  # loot 1-2
TROUBLE_AHEAD_AT = 4  # loot 3-4
MED_KIT_AT = 9  # loot 9+ may be a med kit instead of the item
MED_KIT_CLEARS = 2
VULNERABLE_AT = 4
CARRY_LIMIT = 3  # items besides the one med kit

LADDER: tuple[Die, ...] = get_args(Die.__value__)
SKILLS: tuple[Skill, ...] = get_args(Skill.__value__)


def stepped(die: Die) -> Die:
    index = LADDER.index(die)
    return LADDER[max(index - 1, 0)]


def loot_die(kept: int) -> Die:
    # 5-6 is a d6 item, 7-8 a d8, 9-10 a d10, 11-12 a d12.
    return LADDER[(kept - 3) // 2]


class Sheet(Mutable):
    job: str = ""
    pronouns: str = ""
    # Ratings as created; `worn` is where each skill stands now, reset by Catch Your Breath.
    skills: dict[Skill, Die] = Field(default_factory=dict)
    worn: dict[Skill, Die] = Field(default_factory=dict)
    loot: Die = LOOT_START
    stress: Counter = Counter(current=0, maximum=VULNERABLE_AT)
    stunted: bool = False
    med_kit: bool = False

    @model_validator(mode="after")
    def _six_skills(self) -> Self:
        for skill in SKILLS:
            self.skills.setdefault(skill, DIE_FLOOR)
            self.worn.setdefault(skill, self.skills[skill])
        if over := sorted(skill for skill in SKILLS if self.worn[skill] > self.skills[skill]):
            raise ValueError(f"a worn skill cannot stand above its rating: {over}")
        return self

    @property
    def vulnerable(self) -> bool:
        return self.stress.current >= VULNERABLE_AT

    def rested(self) -> bool:
        return self.worn == self.skills and self.loot == LOOT_START and not self.stunted

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


class ItemSheet(Mutable):
    die: Die

    def rows(self) -> tuple[tuple[str, str], ...]:
        spent = self.die == DIE_FLOOR
        return (("Die", "d4: broken, lost, or faded" if spent else f"d{self.die}"),)


class BreathlessState(Mutable):
    sheets: dict[EntityId, Sheet] = Field(default_factory=dict)
    items: dict[EntityId, ItemSheet] = Field(default_factory=dict)


def item_sheet_of(game: BreathlessState, item: Entity) -> ItemSheet:
    """Every item is a die: one the scenario rated none is refused by `validate` before play."""
    sheet = game.items.get(item.id)
    if sheet is None:
        raise ValueError(f"{item.name} names no die")
    return sheet


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


class ChangeStress(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or an actor here.")
    amount: int = Field(description="Positive adds stress; negative clears it.")
    why: str = Field(min_length=1, description="The complication or the rest, in one line.")


class Breathe(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or a party member here.")


def outcome_for(kept: int) -> str:
    if kept <= FAIL_AT:
        return "fail"
    if kept <= MIXED_AT:
        return "mixed"
    return "success"


def _rolls(
    draft: Game,
    game: BreathlessState,
    actor: Entity,
    skill: str,
    item_id: EntityId | None,
    stunt: bool,
) -> tuple[Die, str, list[Fact]]:
    """The die one roller brings, worn down after the roll: the trace line and facts of the wear."""
    if stunt:
        sheet = sheet_of(game.sheets, actor)
        if sheet.stunted:
            raise ValueError(
                f"{actor.name} has pulled a stunt already; they catch their breath before another"
            )
        sheet.stunted = True
        return STUNT_DIE, "stunt d12", []
    if item_id is not None:
        item = draft.world.require_kind(item_id, "item")
        if item.parent_id != actor.id:
            raise ValueError(f"{actor.name} does not carry {item.name}")
        held = item_sheet_of(game, item)
        if held.die == DIE_FLOOR:
            raise ValueError(f"{item.name} is at d4: broken, lost, or faded. It rolls no more")
        face = held.die
        held.die = stepped(face)
        spent = f"d{held.die}"
        if held.die == DIE_FLOOR:
            # Broken, lost, or faded: it leaves the backpack and frees its slot.
            item.parent_id = location_of(draft.world, actor)
            spent = "d4: broken, lost, or faded, out of the backpack"
        trace = f"{item.name} d{face} -> {spent}"
        return face, f"{item.name} d{face}", [entity_fact(item, "item_worn", trace)]
    if skill not in SKILLS:
        raise ValueError("a check rolls a skill, an item, or a stunt")
    sheet = sheet_of(game.sheets, actor)
    face = sheet.worn[skill]
    sheet.worn[skill] = stepped(face)
    trace = f"{draft.label(actor)} {skill} d{face} -> d{sheet.worn[skill]}"
    return face, f"{skill} d{face}", [entity_fact(actor, "skill_worn", trace)]


def resolve_stake(draft: Game, action: Check) -> tuple[Fact, ...]:
    if action.actor_id != draft.player_id:
        raise ValueError("stake only the player's check; roll an actor's check directly")
    # A throwaway resolution: only its refusal matters, so the dice it draws are discarded.
    _ = resolve_check(draft.draft(), action, Random())
    draft.pending = stake_decision(action.risk, ROLL_CHECK, action.model_dump(mode="json"))
    return ()


ROLL_CHECK = "roll_check"


def resolve_check(draft: Game, action: Check, rng: Random) -> tuple[Fact, ...]:
    with rules(draft.world, BreathlessState) as game:
        return _check(draft, game, action, rng)


def _check(draft: Game, game: BreathlessState, action: Check, rng: Random) -> tuple[Fact, ...]:
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    face, badge, worn = _rolls(draft, game, actor, action.skill, action.item_id, action.stunt)
    faces, detail = [face], [f"Rolls {badge}"]
    rollers = [actor]
    if action.helper_id is not None:
        if action.helper_id == actor.id:
            raise ValueError(f"{actor.name} cannot help themselves; leave `helper_id` null")
        helper = require_actor_here(draft, action.helper_id)
        facts.extend(draft.reveal(helper))
        helped, helper_badge, helper_worn = _rolls(
            draft, game, helper, action.helper_skill, action.helper_item_id, action.helper_stunt
        )
        faces.append(helped)
        detail.append(f"{helper.name} helps: {helper_badge}")
        worn.extend(helper_worn)
        rollers.append(helper)

    kept, pooled, rolled = keep_highest(faces, f"{action.goal} — {badge}", rng, label="Check")
    outcome = outcome_for(kept)
    effects = [fact.trace for fact in worn]
    trace = f"{action.goal} (risk: {action.risk}) -> {outcome}"
    if outcome == "fail" and action.dangerous:
        # Everyone who rolled shares the risk, so each vulnerable roller is named.
        for roller in rollers:
            sheet = game.sheets.get(roller.id)
            if sheet is not None and sheet.vulnerable:
                warning = (
                    f"{roller.name} is vulnerable and failed a dangerous action: taken out, or dead"
                )
                effects.append(warning)
                trace += f". {warning}"
    card = "\n".join((f"Check — {outcome}", *detail, *effects))
    facts.extend(
        (rolled, entity_fact(actor, "check_resolved", trace, card=card, dice=(pooled,)), *worn)
    )
    return tuple(facts)


def resolve_luck_test(draft: Game, action: LuckTest, rng: Random) -> tuple[Fact, ...]:
    del draft
    kept, die, rolled = keep_highest((action.die,), f"luck — {action.subject}", rng, label="Luck")
    outcome = outcome_for(kept)
    return (
        rolled,
        Fact(kind="luck_tested", trace=f"{action.subject}: {outcome}", dice=(die,)),
    )


def resolve_loot(draft: Game, action: LootCheck, rng: Random) -> tuple[Fact, ...]:
    with rules(draft.world, BreathlessState) as game:
        return _loot(draft, game, action, rng)


def _loot(draft: Game, game: BreathlessState, action: LootCheck, rng: Random) -> tuple[Fact, ...]:
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    sheet = sheet_of(game.sheets, actor)
    face = sheet.loot
    sheet.loot = stepped(face)
    held_med_kit = sheet.med_kit
    kept, die, rolled = keep_highest((face,), f"loot — {action.seeking}", rng, label="Loot")
    facts.append(rolled)
    wear = f"loot die d{face} -> d{stepped(face)}"

    def found_fact(found: str) -> Fact:
        return entity_fact(
            actor,
            "loot_found",
            f"{found} — {wear}",
            card="\n".join((f"Loot — {found}", wear)),
            dice=(die,),
        )

    if kept <= TROUBLE_AHEAD_AT:
        here = kept <= TROUBLE_HERE_AT
        found = "trouble is here" if here else "there is trouble ahead"
        draft.notes = (
            *draft.notes,
            f"The loot check found {found} instead of {action.seeking}: show it "
            + ("arriving now." if here else "coming, before it bites."),
        )
        facts.append(found_fact(found))
        return tuple(facts)
    rating = loot_die(kept)
    if kept >= MED_KIT_AT and not held_med_kit:
        draft.pending = PendingDecision(
            kind="loot",
            prompt=MED_KIT_PROMPT,
            options=(
                PendingOption(
                    id="item",
                    label=f"Take {action.seeking} (d{rating})",
                    name=LOOT_ITEM.name,
                    args={"actor_id": actor.id, "seeking": action.seeking, "rating": rating},
                ),
                PendingOption(
                    id="med-kit",
                    label="Take a med kit",
                    name=LOOT_MED_KIT.name,
                    args={"actor_id": actor.id},
                ),
            ),
            allows_text=False,
        )
        facts.append(found_fact(f"a d{rating} item or a med kit"))
        return tuple(facts)
    facts.append(found_fact(f"a d{rating} item"))
    facts.append(_found(draft, game, actor, action.seeking, rating))
    return tuple(facts)


def _found(draft: Game, game: BreathlessState, actor: Entity, seeking: str, rating: Die) -> Fact:
    # A full backpack does not stop the find: the item lies where they stand until they drop one.
    full = len(children(draft.world, actor.id, "item")) >= CARRY_LIMIT
    item = Entity(
        id=EntityId(slug(seeking, draft.world.all_ids())),
        kind="item",
        name=seeking,
        brief=seeking,
        known=True,
        parent_id=location_of(draft.world, actor) if full else actor.id,
    )
    game.items[item.id] = ItemSheet(die=rating)
    where = f", left here: the backpack holds {CARRY_LIMIT}" if full else ""
    found = f"new item: {item.name}[{item.id}] d{rating}{where}"
    card = f"{item.name}, d{rating}{where}"
    return draft.add(item).model_copy(update={"trace": found, "card": card})


class LootItem(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the actor who scavenged.")
    seeking: str = Field(description="The item they hoped to find.")
    rating: Die = Field(description="The die the loot roll rated the find at.")


class LootMedKit(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the actor who scavenged.")


def loot_item(draft: Game, args: LootItem) -> tuple[Fact, ...]:
    actor = draft.world.require_kind(args.actor_id, "actor")
    with rules(draft.world, BreathlessState) as game:
        return (_found(draft, game, actor, args.seeking, args.rating),)


def loot_med_kit(draft: Game, args: LootMedKit) -> tuple[Fact, ...]:
    actor = draft.world.require_kind(args.actor_id, "actor")
    with rules(draft.world, BreathlessState) as game:
        sheet_of(game.sheets, actor).med_kit = True
    return (entity_fact(actor, "loot_found", "took a med kit", card="Med kit"),)


LOOT_ITEM = director_tool(
    "loot_item",
    "Take the item a loot roll turned up.",
    LootItem,
    lambda draft, one, _rng: loot_item(draft, one),
)

LOOT_MED_KIT = director_tool(
    "loot_med_kit",
    "Take a med kit instead of the item a loot roll turned up.",
    LootMedKit,
    lambda draft, one, _rng: loot_med_kit(draft, one),
)


def apply_change_stress(draft: Game, action: ChangeStress) -> list[Fact]:
    if action.amount == 0:
        raise ValueError("changing stress moves the counter; zero moves nothing")
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    with rules(draft.world, BreathlessState) as game:
        sheet = sheet_of(game.sheets, actor)
        facts.extend(adjust(draft, actor, "stress", sheet.stress, action.amount, action.why))
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
    with rules(draft.world, BreathlessState) as game:
        sheet = sheet_of(game.sheets, actor)
        sheet.worn = dict(sheet.skills)
        sheet.loot = LOOT_START
        sheet.stunted = False
    draft.notes = (
        *draft.notes,
        f"{actor.name} caught their breath: introduce a new complication for the group now, "
        "and put it in the world so it stays: reveal or move an actor, add a trait, add stress, "
        "or stake a check.",
    )
    trace = f"{draft.label(actor)} caught their breath: skills, loot die and stunt reset"
    card = f"{actor.name} catches their breath"
    return [entity_fact(actor, "breath_caught", trace, card=card)]


def apply_use_med_kit(draft: Game, action: Breathe) -> list[Fact]:
    actor = require_actor_here(draft, action.actor_id)
    with rules(draft.world, BreathlessState) as game:
        sheet = sheet_of(game.sheets, actor)
        if not sheet.med_kit:
            raise ValueError(f"{actor.name} carries no med kit")
        sheet.med_kit = False
        return adjust(draft, actor, "stress", sheet.stress, -MED_KIT_CLEARS, "used the med kit")


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
    """Only a member the scenario gave a sheet plays by one; the rest travel along."""
    game = mechanics_of(state.world, BreathlessState)
    members = (state.world.require(one) for one in (state.player_id, *state.world.party))
    return tuple(
        (member, sheet) for member in members if (sheet := game.sheets.get(member.id)) is not None
    )
