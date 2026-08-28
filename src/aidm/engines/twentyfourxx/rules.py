from dataclasses import dataclass
from random import Random
from typing import ClassVar, Literal, Self, get_args

from pydantic import Field, model_validator

from aidm.engines.core import Decision, ProposalBase, adjust, pool, spend
from aidm.engines.sheets import ItemBase, SheetBase, SheetMechanics, require_sheet
from aidm.state.actions import require_actor_here, roll_pool
from aidm.state.creation import CreationOption
from aidm.state.entities import (
    CheckedEntityId,
    Counter,
    Entity,
    EntityId,
    Frozen,
    Slug,
)
from aidm.state.facts import DiceEvent, EventBadge, Fact, MechanicEvent, entity_fact
from aidm.state.model import Game
from aidm.state.play import DecisionOption, PendingDecision


@dataclass(frozen=True, slots=True)
class Rules:
    starting_credits: int = 2
    default_face: int = 6  # an unlisted skill rolls the bare d6
    hindered_face: int = 4
    disaster_at: int = 2  # kept 1-2
    setback_at: int = 4  # kept 3-4
    trouble_at: int = 2  # 1-2 on the bad-luck die
    signs_at: int = 4  # 3-4 on the bad-luck die
    max_breaks: int = 3  # the sturdiest printed armour breaks up to 3x
    ship_upgrade: int = 10  # every starship upgrade is printed at the same price


RULES = Rules()


type SkillDie = Literal[8, 10, 12]


LADDER: tuple[SkillDie, ...] = get_args(SkillDie.__value__)


class Sheet(SheetBase):
    specialty: str = ""
    origin: str = ""
    skills: dict[str, SkillDie] = Field(default_factory=dict)
    credits: Counter = Counter(current=RULES.starting_credits)
    jobs: Counter = Counter(current=0)

    def rows(self) -> tuple[tuple[str, str], ...]:
        skills = ", ".join(f"{name} d{face}" for name, face in sorted(self.skills.items()))
        return (
            ("Specialty", self.specialty),
            ("Origin", self.origin),
            ("Skills", skills),
            ("Credits", pool(self.credits)),
        )

    def face(self, skill: str) -> int:
        return self.skills.get(skill, RULES.default_face)


def _mark(set_on: bool) -> str:
    return "yes" if set_on else ""


class ItemSheet(ItemBase):
    """A carried item's marks and the breaks it has left; every item breaks once by default."""

    bulky: bool = False
    broken: bool = False
    breaks: Counter = Counter(current=1, maximum=1)

    @model_validator(mode="after")
    def _broken_when_spent(self) -> Self:
        if self.broken != (self.breaks.current == 0):
            raise ValueError("an item is broken exactly when it has no breaks left")
        return self

    def rows(self) -> tuple[tuple[str, str], ...]:
        # Sturdy gear alone counts: every other item breaks once, which `broken` already says.
        counted = str(self.breaks.current) if self.breaks.maximum != 1 else ""
        return (
            ("Bulky", _mark(self.bulky)),
            ("Broken", _mark(self.broken)),
            ("Breaks left", counted),
        )


class Mechanics(SheetMechanics[Sheet, ItemSheet]): ...


def raised(current: SkillDie | None) -> SkillDie:
    if current is None:
        return LADDER[0]
    index = LADDER.index(current)
    if index + 1 == len(LADDER):
        raise ValueError("that skill is already d12, the top of the ladder")
    return LADDER[index + 1]


class GearItem(Frozen):
    id: Slug
    label: str
    detail: str = ""
    bulky: bool = False
    cost: int = Field(default=1, ge=1)
    breaks: int = Field(default=1, ge=1, le=RULES.max_breaks)


class ShipUpgrade(GearItem):
    cost: int = Field(default=RULES.ship_upgrade, ge=1)


class ShipFunction(Frozen):
    """A function every starship has a basic version of, and what ₡10 buys for it."""

    id: Slug
    label: str
    detail: str = ""
    upgrades: tuple[ShipUpgrade, ...] = ()


class SkillGrant(Frozen):
    id: Slug
    label: str
    detail: str = ""
    skills: tuple[str, ...] = Field(min_length=1)
    die: SkillDie = 8


class Specialty(Frozen):
    id: Slug
    label: str
    detail: str = ""
    skills: tuple[str, ...] = ()
    choices: tuple[SkillGrant, ...] = ()
    kit: tuple[GearItem, ...] = ()
    kit_choice: tuple[GearItem, ...] = ()

    @model_validator(mode="after")
    def _grants_a_skill_some_way(self) -> Self:
        if not self.skills and not self.choices:
            raise ValueError("a specialty grants at least one skill, fixed or chosen")
        return self


class Origin(Frozen):
    id: Slug
    label: str
    detail: str = ""
    increases: int = Field(default=0, ge=0, le=3)
    # Example traits shown as hints when the player invents their own; not a bound on their answer.
    traits: tuple[CreationOption, ...] = ()
    invents: int = Field(default=0, ge=0)
    kit_choice: tuple[GearItem, ...] = ()


class Pack(Frozen):
    name: str
    source: str
    license: str
    # What every character takes regardless of specialty: the SRD's comm.
    starting_kit: tuple[GearItem, ...] = ()
    gear: tuple[GearItem, ...] = ()
    ship: tuple[ShipFunction, ...] = ()
    specialties: tuple[Specialty, ...] = Field(min_length=1)
    origins: tuple[Origin, ...] = Field(min_length=1)
    # The skill menu an origin's increases are chosen from.
    skills: tuple[CreationOption, ...] = Field(min_length=1)


class Attempt(Frozen):
    actor_id: CheckedEntityId = Field(
        description="Exact id of the player or actor here who takes the action."
    )
    goal: str = Field(
        min_length=1,
        description="The actor's goal, in one line.",
    )
    risk: str = Field(
        min_length=1,
        description="One-line cost of a bad roll. There is no roll without one.",
    )
    hit: bool = Field(description="True when a bad roll means physical harm to the actor.")
    skill: str = Field(
        default="",
        description="Matching skill from the actor's sheet, or empty for d6.",
    )
    helped: str = Field(
        default="",
        description="Helpful circumstance that adds d6. Empty when using `helper_id` or no help.",
    )
    helper_id: CheckedEntityId | None = Field(
        default=None,
        description="Exact id of an ally here who adds their skill die, or null for no helper.",
    )
    helper_skill: str = Field(
        default="",
        description="Matching skill from the helper's sheet, or empty for their d6.",
    )
    hindered: str = Field(
        default="",
        description=(
            "Hindering circumstance that lowers the actor's die to d4, such as an injury trait "
            "in the way or a heavy load; empty when nothing hinders."
        ),
    )
    luck_test: str = Field(
        default="",
        description="Separate bad luck that may arrive, or empty for no test.",
    )

    @model_validator(mode="after")
    def _one_help_die(self) -> Self:
        if self.helper_id is not None and self.helped:
            raise ValueError(
                "help is one die: name the ally in `helper_id` or the circumstance in `helped`, "
                "never both"
            )
        if self.helper_skill and self.helper_id is None:
            raise ValueError(
                "`helper_skill` is the skill of the ally in `helper_id`; name them too"
            )
        return self


class StakedAttempt(Attempt, Decision):
    kind: ClassVar[Slug] = "stake"

    def resolve(self, draft: Game, option_id: Slug, rng: Random) -> tuple[Fact, ...]:
        # `proceed` is the only option the engine offers; the player's own words revise instead.
        del option_id
        return resolve_attempt(draft, self, rng)


class LuckTest(Frozen):
    actor_id: CheckedEntityId = Field(
        description="Exact id of the player or actor here facing bad luck."
    )
    subject: str = Field(
        min_length=1,
        description="Possible bad luck, such as low ammo or nearby guards.",
    )


TAKE_THE_HIT: Slug = "take-it"


DEFENCE_PROMPT = (
    "A hit is coming. Break one carried item to make it a brief hindrance, or take the full hit."
)


class Defence(Decision):
    kind: ClassVar[Slug] = "defence"

    goal: str

    def resolve(self, draft: Game, option_id: Slug, rng: Random) -> tuple[Fact, ...]:
        del rng
        item = None if option_id == TAKE_THE_HIT else EntityId(option_id)
        return resolve_defence(draft, self.goal, item)


def outcome_for(kept: int) -> Slug:
    if kept <= RULES.disaster_at:
        return "disaster"
    if kept <= RULES.setback_at:
        return "setback"
    return "success"


def pool_faces(sheet: Sheet, action: Attempt, helper: Sheet | None) -> tuple[int, ...]:
    base = RULES.hindered_face if action.hindered else sheet.face(action.skill)
    if helper is not None:
        return (base, helper.face(action.helper_skill))
    return (base, RULES.default_face) if action.helped else (base,)


def _require_skill(actor: Entity, sheet: Sheet, skill: str, field: str) -> None:
    if skill and skill not in sheet.skills:
        written = ", ".join(sorted(sheet.skills)) or "(none)"
        raise ValueError(
            f"{actor.name} has no skill {skill!r}. Their skills are: {written}. Leave "
            f"`{field}` empty to roll the bare d6."
        )


def apply_change_credits(draft: Game, actor_id: EntityId, amount: int) -> list[Fact]:
    if amount == 0:
        raise ValueError("changing credits moves the pool; zero moves nothing")
    actor = require_actor_here(draft, actor_id)
    facts = draft.reveal(actor)
    credits = require_sheet(Mechanics.of_game(draft).sheets, actor).credits
    if amount > 0:
        return [*facts, *adjust(draft, actor, "credits", credits, amount, "paid", "payments")]
    # `spend`, not a negative adjust: an overdraw is refused, not clamped.
    return [*facts, *spend(draft, actor, "credits", credits, -amount, "payments")]


def _require_playable(
    draft: Game, action: Attempt
) -> tuple[Entity, Sheet, Sheet | None, list[Fact]]:
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    sheet = Mechanics.of_game(draft).sheets.get(actor.id)
    if sheet is None:
        raise ValueError(
            f"{actor.name} has no character sheet, so it never rolls: narrate its threat, "
            "or put the risk on the player's own attempt or a luck test"
        )
    helper_sheet = _helper_sheet(draft, actor, action, facts)
    _require_skill(actor, sheet, action.skill, "skill")
    return actor, sheet, helper_sheet, facts


def resolve_stake(draft: Game, action: StakedAttempt) -> tuple[Fact, ...]:
    if action.actor_id != draft.player_id:
        raise ValueError("stake only the player's attempt; roll an actor's attempt directly")
    _ = _require_playable(draft.draft(), action)
    draft.pending = action.pending(
        f"{action.risk}\n\nProceed, or change your plan.",
        (DecisionOption(id="proceed", label="Proceed"),),
    )
    return ()


def resolve_defence(draft: Game, goal: str, item_id: EntityId | None) -> tuple[Fact, ...]:
    player = draft.player
    if item_id is None:
        return (
            entity_fact(
                player,
                "defence_taken",
                f"{goal}: the hit lands in full",
                event=MechanicEvent(title="Took the hit", icon="heart_broken"),
            ),
        )
    item = draft.world.require_kind(item_id, "item")
    if item.parent_id != draft.player_id:
        raise ValueError(f"the player does not carry {item.name}, so it cannot break for them")
    sheet = Mechanics.of_game(draft).items.setdefault(item.id, ItemSheet())
    if sheet.broken:
        raise ValueError(f"{item.name} is already broken, so it turns nothing")
    sheet.breaks.current -= 1
    if left := sheet.breaks.current:
        return (
            entity_fact(
                player,
                "defence_turned",
                f"{goal}: {item.name} takes the hit and holds; it can break {left} more times",
                event=MechanicEvent(title=f"{item.name} held, {left} left", icon="shield"),
            ),
        )
    # Broken gear stays carried until it is repaired, so its last break removes nothing.
    sheet.broken = True
    return (
        entity_fact(
            player,
            "defence_turned",
            f"{goal}: {item.name} breaks, turning the hit into a brief hindrance",
            event=MechanicEvent(title=f"{item.name} broke", icon="broken_image"),
        ),
    )


def _defence_decision(draft: Game, goal: str) -> PendingDecision:
    marks = Mechanics.of_game(draft).items
    unbroken = tuple(
        DecisionOption(id=item.id, label=f"Break the {item.name}")
        for item in draft.world.children(draft.player_id, "item")
        if item.id not in marks or not marks[item.id].broken
    )
    return Defence(goal=goal).pending(
        DEFENCE_PROMPT, (*unbroken, DecisionOption(id=TAKE_THE_HIT, label="Take the hit"))
    )


def resolve_attempt(draft: Game, action: Attempt, rng: Random) -> tuple[Fact, ...]:
    actor, sheet, helper_sheet, facts = _require_playable(draft, action)

    faces = pool_faces(sheet, action, helper_sheet)
    reason = f"{action.goal} — {action.skill or 'no skill'}"
    pooled, rolled = roll_pool(faces, reason, rng, label="Pool")
    facts.append(rolled)

    outcome = outcome_for(pooled.kept)
    resolved_at = len(facts)
    facts.append(
        entity_fact(actor, "attempt_resolved", f"{action.goal} (risk: {action.risk}) -> {outcome}")
    )

    dice, effects = (pooled,), ()
    if action.luck_test:
        # A riding luck test shows its die even when it came up clear and left no `luck_tested`.
        luck, _, luck_facts = _bad_luck(draft, actor, action.luck_test, rng)
        dice, effects = (pooled, luck), tuple(f.trace for f in luck_facts if f.told)
        facts.extend(luck_facts)
    card = MechanicEvent(
        title="Attempt", badges=_badges(action, faces), dice=dice, outcome=outcome, effects=effects
    )
    facts[resolved_at] = facts[resolved_at].model_copy(update={"event": card})

    if action.hit and action.actor_id == draft.player_id and outcome != "success":
        draft.pending = _defence_decision(draft, action.goal)
    return tuple(facts)


def _badges(action: Attempt, faces: tuple[int, ...]) -> tuple[EventBadge, ...]:
    badges = [EventBadge(label="Skill", value=action.skill)] if action.skill else []
    if len(faces) > 1:
        badges.append(EventBadge(label="Help", value=f"d{faces[-1]}"))
    if action.hindered:
        badges.append(EventBadge(label="Hindered", value=""))
    return tuple(badges)


def resolve_luck_test(draft: Game, action: LuckTest, rng: Random) -> tuple[Fact, ...]:
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    die, outcome, luck_facts = _bad_luck(draft, actor, action.subject, rng)
    if outcome:
        card = MechanicEvent(title="Luck Test", dice=(die,), outcome=outcome, icon="warning")
        luck_facts[-1] = luck_facts[-1].model_copy(update={"event": card})
    facts.extend(luck_facts)
    return tuple(facts)


def _helper_sheet(draft: Game, actor: Entity, action: Attempt, facts: list[Fact]) -> Sheet | None:
    if action.helper_id is None:
        return None
    if action.helper_id == actor.id:
        raise ValueError(
            f"{actor.name} cannot help themselves. Name the ally who does, or leave `helper_id` "
            "null."
        )
    helper = require_actor_here(draft, action.helper_id)
    facts.extend(draft.reveal(helper))
    sheet = require_sheet(Mechanics.of_game(draft).sheets, helper)
    _require_skill(helper, sheet, action.helper_skill, "helper_skill")
    return sheet


def _bad_luck(
    draft: Game, actor: Entity, subject: str, rng: Random
) -> tuple[DiceEvent, str, list[Fact]]:
    die, rolled = roll_pool((6,), f"bad luck — {subject}", rng, label="Luck")
    if die.kept > RULES.signs_at:
        return die, "", [rolled]
    trouble = die.kept <= RULES.trouble_at
    note = (
        f"Bad luck has caught up with them: {subject} — the narration showed it arriving this "
        "turn. Develop it next: what it costs, what it changes."
        if trouble
        else f"Bad luck is circling: signs of {subject} showed this turn. Let the scene warn of "
        "it before it bites."
    )
    draft.world.pending_notes = (*draft.world.pending_notes, note)
    label = "trouble" if trouble else "signs of it"
    tested = entity_fact(actor, "luck_tested", f"bad luck — {subject}: {label}")
    return die, "Trouble" if trouble else "Signs", [rolled, tested]


GROWTH = (
    "Choose one skill this job improves. Raise an existing skill one step or add a new one at d8."
)


class Advance(ProposalBase):
    """The skill increase earned by one job."""

    skill: str = Field(
        min_length=1,
        description="Title-case skill to raise one step or add at d8.",
    )
    why: str = Field(description="One short reason, in the fiction, for the change.")
