from dataclasses import dataclass
from random import Random
from typing import Literal, Self, get_args

from pydantic import Field, model_validator

from aidm.engines.core import ProposalBase, adjust, spend
from aidm.engines.sheets import (
    SheetBase,
    SheetMechanics,
    complete_chapter,
    render_counters,
    require_sheet,
)
from aidm.state.actions import add_trait, require_actor_here, roll_pool
from aidm.state.creation import CreationOption
from aidm.state.entities import PLAYER_ID, ContentSlug, Counter, Entity, EntityId, Frozen, Slug
from aidm.state.facts import DiceEvent, EventBadge, Fact, MechanicEvent, entity_fact
from aidm.state.model import Game
from aidm.state.play import DecisionOption, OptionId, PendingDecision


@dataclass(frozen=True, slots=True)
class Rules:
    """24XX's numbers in one place; docs/24XX.md names every deviation from the SRD."""

    starting_credits: int = 2
    default_face: int = 6  # an unlisted skill rolls the bare d6
    hindered_face: int = 4
    disaster_at: int = 2  # kept 1-2
    setback_at: int = 4  # kept 3-4
    trouble_at: int = 2  # 1-2 on the bad-luck die
    signs_at: int = 4  # 3-4 on the bad-luck die


RULES = Rules()


type SkillDie = Literal[8, 10, 12]


LADDER: tuple[SkillDie, ...] = get_args(SkillDie.__value__)


class Sheet(SheetBase):
    """The one sheet shape, whether it belongs to the player or to an NPC."""

    specialty: str = ""
    origin: str = ""
    skills: dict[str, SkillDie] = Field(default_factory=dict)
    credits: Counter = Counter(current=RULES.starting_credits)
    jobs: Counter = Counter(current=0)

    def counters(self) -> dict[Slug, Counter]:
        return {"credits": self.credits}

    def face(self, skill: str) -> int:
        return self.skills.get(skill, RULES.default_face)


class Mechanics(SheetMechanics[Sheet]): ...


def raised(current: SkillDie | None) -> SkillDie:
    """One step up the none -> d8 -> d10 -> d12 ladder; raises ValueError at the top."""
    if current is None:
        return LADDER[0]
    index = LADDER.index(current)
    if index + 1 == len(LADDER):
        raise ValueError("that skill is already d12, the top of the ladder")
    return LADDER[index + 1]


def describe_entity(mechanics: Mechanics, entity: Entity) -> str:
    sheet = mechanics.sheets.get(entity.id)
    if sheet is None:
        return ""
    skills = ", ".join(f"{name} d{face}" for name, face in sorted(sheet.skills.items()))
    lines = (
        f"specialty: {sheet.specialty}" if sheet.specialty else "",
        f"origin: {sheet.origin}" if sheet.origin else "",
        f"skills: {skills}" if skills else "",
        f"pools: {render_counters(sheet.counters())}",
    )
    return "\n".join(line for line in lines if line)


class KitItem(Frozen):
    """One piece of starting gear, carried as an item entity rather than written on the sheet."""

    id: ContentSlug
    label: str
    detail: str = ""
    bulky: bool = False


class SkillGrant(Frozen):
    """One side of a specialty's either/or: its skills land on the sheet at `die`."""

    id: ContentSlug
    label: str
    detail: str = ""
    skills: tuple[str, ...] = Field(min_length=1)
    die: SkillDie = 8


class Specialty(Frozen):
    """A specialty grants fixed skills, one chosen grant, and starting gear."""

    id: ContentSlug
    label: str
    detail: str = ""
    skills: tuple[str, ...] = ()
    choices: tuple[SkillGrant, ...] = ()
    kit: tuple[KitItem, ...] = ()

    @model_validator(mode="after")
    def _grants_a_skill_some_way(self) -> Self:
        if not self.skills and not self.choices:
            raise ValueError("a specialty grants at least one skill, fixed or chosen")
        return self


class Origin(Frozen):
    id: ContentSlug
    label: str
    detail: str = ""
    increases: int = Field(default=0, ge=0, le=3)
    # Example traits shown as hints when the player invents their own; not a bound on their answer.
    traits: tuple[CreationOption, ...] = ()
    invents: int = Field(default=0, ge=0)


class Pack(Frozen):
    """One published table set the player can build a character from."""

    name: str
    source: str
    license: str
    # What every character takes regardless of specialty: the SRD's comm.
    starting_kit: tuple[KitItem, ...] = ()
    specialties: tuple[Specialty, ...] = Field(min_length=1)
    origins: tuple[Origin, ...] = Field(min_length=1)
    # The skill menu an origin's increases are chosen from.
    skills: tuple[CreationOption, ...] = Field(min_length=1)


class Attempt(Frozen):
    actor_id: EntityId = Field(
        description="Exact id of the player or actor here who takes the action."
    )
    goal: str = Field(
        min_length=1,
        description="The actor's goal, in one line.",
    )
    skill: str = Field(
        default="",
        description="Matching skill from the actor's sheet, or empty for d6.",
    )
    helped: str = Field(
        default="",
        description="Helpful circumstance that adds d6. Empty when using `helper_id` or no help.",
    )
    helper_id: EntityId | None = Field(
        default=None,
        description="Exact id of an ally here who adds their skill die, or null for no helper.",
    )
    helper_skill: str = Field(
        default="",
        description="Matching skill from the helper's sheet, or empty for their d6.",
    )
    hindered: str = Field(
        default="",
        description="Hindering circumstance that lowers the actor's die to d4, or empty.",
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


class StakedAttempt(Attempt):
    risk: str = Field(min_length=1, description="One-line cost of a bad roll, shown to the player.")


class LuckTest(Frozen):
    actor_id: EntityId = Field(description="Exact id of the player or actor here facing bad luck.")
    subject: str = Field(
        min_length=1,
        description="Possible bad luck, such as low ammo or nearby guards.",
    )


HURT: tuple[Slug, ...] = ("disaster", "setback")


BROKEN: Slug = "broken"


TAKE_THE_HIT: OptionId = "take-it"


DEFENCE_PROMPT = (
    "A hit is coming. Break one carried item to make it a brief hindrance, or take the full hit."
)


BREAK_TEXT = "Broken turning a hit into a brief hindrance; useless until repaired."


class Defence(Frozen):
    """The hit a defence decision is answered against, frozen while the player chooses."""

    outcome: Slug
    goal: str


def outcome_for(kept: int) -> Slug:
    if kept <= RULES.disaster_at:
        return "disaster"
    if kept <= RULES.setback_at:
        return "setback"
    return "success"


def pool_faces(sheet: Sheet, action: Attempt, helper: Sheet | None) -> tuple[int, ...]:
    """Hindrance drops the die to a d4; help adds one die at most — the helper's own, or a d6."""
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
        return [*facts, *adjust(actor, "credits", credits, amount, "paid", "payments")]
    # `spend`, not a negative adjust: an overdraw is refused, not clamped.
    return [*facts, *spend(actor, "credits", credits, -amount, "payments")]


def apply_complete_chapter(draft: Game) -> list[Fact]:
    return complete_chapter(draft, "the job is done")


def _require_playable(
    draft: Game, action: Attempt
) -> tuple[Entity, Sheet, Sheet | None, list[Fact]]:
    """Everything an attempt must satisfy before any die is rolled, with the reveals it earns."""
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    sheet = require_sheet(Mechanics.of_game(draft).sheets, actor)
    helper_sheet = _helper_sheet(draft, actor, action, facts)
    _require_skill(actor, sheet, action.skill, "skill")
    return actor, sheet, helper_sheet, facts


def resolve_stake(draft: Game, action: StakedAttempt) -> tuple[Fact, ...]:
    if action.actor_id != PLAYER_ID:
        raise ValueError(
            "the advise step is the player's own: stake only the player's attempt, and roll an "
            "NPC's directly"
        )
    # Validated against a copy: freezing an attempt reveals nothing and rolls nothing yet.
    _ = _require_playable(draft.draft(), action)
    draft.pending = PendingDecision(
        kind="stake",
        prompt=action.risk,
        options=(DecisionOption(id="proceed", label="Proceed"),),
        payload=action.model_dump(mode="json"),
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
    if item.parent_id != PLAYER_ID:
        raise ValueError(f"the player does not carry {item.name}, so it cannot break for them")
    if item.trait(BROKEN) is not None:
        raise ValueError(f"{item.name} is already broken, so it turns nothing")
    return (
        *add_trait(draft, item_id, BROKEN, BREAK_TEXT),
        entity_fact(
            player,
            "defence_turned",
            f"{goal}: {item.name} breaks, turning the hit into a brief hindrance",
        ),
    )


def _defence_decision(draft: Game, outcome: Slug, goal: str) -> PendingDecision:
    unbroken = tuple(
        DecisionOption(id=item.id, label=f"Break the {item.name}")
        for item in draft.world.children(PLAYER_ID, "item")
        if item.trait(BROKEN) is None
    )
    return PendingDecision(
        kind="defence",
        prompt=DEFENCE_PROMPT,
        options=(*unbroken, DecisionOption(id=TAKE_THE_HIT, label="Take the hit")),
        payload={"outcome": outcome, "goal": goal},
    )


def resolve_attempt(draft: Game, action: Attempt, rng: Random) -> tuple[Fact, ...]:
    actor, sheet, helper_sheet, facts = _require_playable(draft, action)

    faces = pool_faces(sheet, action, helper_sheet)
    reason = f"{action.goal} — {action.skill or 'no skill'}"
    pooled, rolled = roll_pool(faces, reason, rng, label="Pool")
    facts.append(rolled)

    outcome = outcome_for(pooled.kept)
    resolved_at = len(facts)
    facts.append(entity_fact(actor, "attempt_resolved", f"{action.goal} -> {outcome}"))

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

    # `Attempt` names no target, and the printed defence is the player's own: only their roll hits.
    if action.actor_id == PLAYER_ID and outcome in HURT:
        draft.pending = _defence_decision(draft, outcome, action.goal)
    return tuple(facts)


def _badges(action: Attempt, faces: tuple[int, ...]) -> tuple[EventBadge, ...]:
    """Help shows only the die, never the helper's name, to match the unnamed skill badge."""
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
    """The die, the label a card shows (empty when the roll came up clear), and the facts."""
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
    why: str = Field(description="One short reason shown to the player before confirmation.")
