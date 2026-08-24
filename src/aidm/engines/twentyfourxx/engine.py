from collections.abc import Mapping
from pathlib import Path
from random import Random
from typing import Literal, Self

from pydantic import Field, JsonValue, model_validator
from pydantic_ai import RunContext
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset

from aidm.content.model import CharacterOverlay, CharacterProfile, CreatedCharacter
from aidm.engines.core import (
    Advancement,
    CharacterCreation,
    Engine,
    PlanContext,
    ProposalBase,
    SheetBase,
    SheetMechanics,
    act,
    actor_sheets,
    adjust,
    check_sheets,
    chipped,
    complete_chapter,
    dice_by_role,
    dice_event,
    load_packs,
    pack_paths,
    pack_step,
    render_counters,
    require_dice_role,
    require_sheet,
    sequential_toolset,
    spend,
    with_enum,
)
from aidm.state.actions import add_trait, require_actor_here, roll_pool
from aidm.state.model import (
    PLAYER_ID,
    AnyStep,
    Chip,
    ContentSlug,
    Counter,
    CreationOption,
    CreationStep,
    EngineId,
    Entity,
    EntityId,
    EventBadge,
    Fact,
    Frozen,
    Game,
    MechanicEvent,
    Option,
    OptionId,
    PendingDecision,
    Picks,
    Slug,
    TextStep,
    Trait,
    WorldState,
    check_picks,
    entity_fact,
    explained_fact,
    picked,
    text_slug,
)

STARTING_CREDITS = 2
DEFAULT_FACE = 6  # an unlisted skill rolls the bare d6
HINDERED_FACE = 4

type SkillDie = Literal[8, 10, 12]
LADDER: tuple[SkillDie, ...] = (8, 10, 12)


class Sheet(SheetBase):
    """The one sheet shape, whether it belongs to the player or to an NPC."""

    specialty: str = ""
    origin: str = ""
    skills: dict[str, SkillDie] = Field(default_factory=dict)
    credits: Counter = Counter(current=STARTING_CREDITS)
    jobs: Counter = Counter(current=0)

    def counters(self) -> dict[Slug, Counter]:
        return {"credits": self.credits}

    def face(self, skill: str) -> int:
        return self.skills.get(skill, DEFAULT_FACE)


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
        description="Exact id of the actor attempting this: the player, or an actor here."
    )
    goal: str = Field(
        min_length=1,
        description="What the actor is trying to do and what they risk by trying, in one line.",
    )
    skill: str = Field(
        default="",
        description="The skill on the actor's sheet this calls on, or empty for none.",
    )
    helped: str = Field(
        default="",
        description="The circumstance that makes this easier — a skill, a piece of gear, the "
        "ground they hold, an ally's presence — in a few words. Empty when nothing does, and "
        "never alongside `helper_id`.",
    )
    helper_id: EntityId | None = Field(
        default=None,
        description="Exact id of an ally here who helps with this — they roll their own skill "
        "die into the pool. Null when nobody helps.",
    )
    helper_skill: str = Field(
        default="",
        description="The skill on the *helper's* sheet this calls on, or empty for none.",
    )
    hindered: str = Field(
        default="",
        description="The circumstance that makes this harder, in a few words. Empty when "
        "nothing does.",
    )
    luck_test: str = Field(
        default="",
        description="What bad luck might arrive alongside this. Empty for no test.",
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


class LuckTest(Frozen):
    actor_id: EntityId = Field(
        description="Exact id of the actor whose luck is tested: the player, or an actor here."
    )
    subject: str = Field(
        min_length=1,
        description="What bad luck might arrive — running out of ammo, running into guards.",
    )


TROUBLE = 2  # 1-2 on the bad-luck die
SIGNS = 4  # 3-4 on the bad-luck die

HURT: tuple[Slug, ...] = ("disaster", "setback")
BROKEN: Slug = "broken"
TAKE_THE_HIT: OptionId = "take-it"
DEFENCE_PROMPT = (
    "A hit lands: say how one of your items breaks to turn it into a brief hindrance, or take it."
)
BREAK_TEXT = "Broken turning a hit into a brief hindrance; useless until repaired."


class Defence(Frozen):
    """The hit a defence decision is answered against, frozen while the player chooses."""

    outcome: Slug
    goal: str


def outcome_for(kept: int) -> Slug:
    if kept <= 2:
        return "disaster"
    if kept <= 4:
        return "setback"
    return "success"


def pool_faces(sheet: Sheet, action: Attempt, helper: Sheet | None) -> tuple[int, ...]:
    """Hindrance drops the die to a d4; help adds one die at most — the helper's own, or a d6."""
    base = HINDERED_FACE if action.hindered else sheet.face(action.skill)
    if helper is not None:
        return (base, helper.face(action.helper_skill))
    return (base, DEFAULT_FACE) if action.helped else (base,)


def _require_skill(actor: Entity, sheet: Sheet, skill: str, field: str) -> None:
    if skill and skill not in sheet.skills:
        written = ", ".join(sorted(sheet.skills)) or "(none)"
        raise ValueError(
            f"{actor.name} has no skill {skill!r}. Their skills are: {written}. Leave "
            f"`{field}` empty to roll the bare d6."
        )


def _skills_in_play(state: Game) -> set[str]:
    """Limit attempt skills to actors present with the player."""
    sheets = Mechanics.of(state).sheets
    return {
        skill
        for actor in state.world.of_kind("actor")
        if state.is_here(actor)
        for skill in require_sheet(sheets, actor).skills
    }


def _narrow_to_skills_in_play(
    ctx: RunContext[PlanContext], tools: list[ToolDefinition]
) -> list[ToolDefinition]:
    skills = ["", *sorted(_skills_in_play(ctx.deps.state))]
    return [_with_skills(tool, skills) for tool in tools]


def _with_skills(tool: ToolDefinition, skills: list[str]) -> ToolDefinition:
    fields = ("skill", "helper_skill")
    if tool.name == "roll_attempt":
        return with_enum(tool, fields, skills)
    if tool.name == "stake_attempt":
        return with_enum(tool, fields, skills, inside="Attempt")
    return tool


def _defence_to_settle(ctx: RunContext[PlanContext]) -> PendingDecision | None:
    """One hit, one settlement: the decision an open answer consumed, until this run settles it."""
    answered = ctx.deps.answered
    if answered is None or answered.kind != "defence":
        return None
    if any(fact.kind in ("defence_turned", "defence_taken") for fact in ctx.deps.log.facts):
        return None
    return answered


def apply_change_credits(draft: Game, actor_id: EntityId, amount: int) -> list[Fact]:
    if amount == 0:
        raise ValueError("changing credits moves the pool; zero moves nothing")
    actor = require_actor_here(draft, actor_id)
    facts = draft.reveal(actor)
    credits = require_sheet(Mechanics.of(draft).sheets, actor).credits
    if amount > 0:
        return [*facts, *chipped(adjust(actor, "credits", credits, amount, "paid"), "payments")]
    # `spend`, not a negative adjust: an overdraw is refused, not clamped.
    return [*facts, *chipped(spend(actor, "credits", credits, -amount), "payments")]


def apply_complete_chapter(draft: Game) -> list[Fact]:
    return complete_chapter(draft, "the job is done")


def _require_playable(
    draft: Game, action: Attempt
) -> tuple[Entity, Sheet, Sheet | None, list[Fact]]:
    """Everything an attempt must satisfy before any die is rolled, with the reveals it earns."""
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    sheet = require_sheet(Mechanics.of(draft).sheets, actor)
    helper_sheet = _helper_sheet(draft, actor, action, facts)
    _require_skill(actor, sheet, action.skill, "skill")
    return actor, sheet, helper_sheet, facts


def resolve_stake(draft: Game, action: Attempt, risk: str) -> tuple[Fact, ...]:
    if action.actor_id != PLAYER_ID:
        raise ValueError(
            "the advise step is the player's own: stake only the player's attempt, and roll an "
            "NPC's directly"
        )
    # Validated against a copy: freezing an attempt reveals nothing and rolls nothing yet.
    _ = _require_playable(draft.draft(), action)
    draft.pending = PendingDecision(
        kind="stake",
        prompt=risk,
        options=(Option(id="proceed", label="Proceed"),),
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
                {"goal": goal},
                chip=Chip(title="Took the hit", icon="heart_broken"),
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
            {"goal": goal, "item_id": item_id},
        ),
    )


def _defence_decision(draft: Game, outcome: Slug, goal: str) -> PendingDecision:
    unbroken = tuple(
        Option(id=item.id, label=f"Break the {item.name}")
        for item in draft.world.children(PLAYER_ID, "item")
        if item.trait(BROKEN) is None
    )
    return PendingDecision(
        kind="defence",
        prompt=DEFENCE_PROMPT,
        options=(*unbroken, Option(id=TAKE_THE_HIT, label="Take the hit")),
        payload={"outcome": outcome, "goal": goal},
    )


def resolve_attempt(draft: Game, action: Attempt, rng: Random) -> tuple[Fact, ...]:
    actor, sheet, helper_sheet, facts = _require_playable(draft, action)

    faces = pool_faces(sheet, action, helper_sheet)
    kept, rolled = roll_pool(
        faces, f"{action.goal} — {action.skill or 'no skill'}", rng, role="pool"
    )
    facts.append(rolled)

    outcome = outcome_for(kept)
    facts.append(
        entity_fact(
            actor,
            "attempt_resolved",
            f"{action.goal} -> {outcome}",
            {
                "goal": action.goal,
                "outcome": outcome,
                "kept": kept,
                "skill": action.skill,
                "faces": list(faces),
                "helper": action.helper_id,
                "hindered": bool(action.hindered),
            },
        )
    )

    if action.luck_test:
        facts.extend(_bad_luck(draft, actor, action.luck_test, rng))
    # `Attempt` names no target, and the printed defence is the player's own: only their roll hits.
    if action.actor_id == PLAYER_ID and outcome in HURT:
        draft.pending = _defence_decision(draft, outcome, action.goal)
    return tuple(facts)


def resolve_luck_test(draft: Game, action: LuckTest, rng: Random) -> tuple[Fact, ...]:
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    facts.extend(_bad_luck(draft, actor, action.subject, rng))
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
    sheet = require_sheet(Mechanics.of(draft).sheets, helper)
    _require_skill(helper, sheet, action.helper_skill, "helper_skill")
    return sheet


def _bad_luck(draft: Game, actor: Entity, subject: str, rng: Random) -> list[Fact]:
    kept, rolled = roll_pool((6,), f"bad luck — {subject}", rng, role="luck")
    if kept > SIGNS:
        return [rolled]
    trouble = kept <= TROUBLE
    note = (
        f"Bad luck has caught up with them: {subject} — the narration showed it arriving this "
        "turn. Develop it next: what it costs, what it changes."
        if trouble
        else f"Bad luck is circling: signs of {subject} showed this turn. Let the scene warn of "
        "it before it bites."
    )
    draft.world.pending_notes = (*draft.world.pending_notes, note)
    label = "trouble" if trouble else "signs of it"
    tested = entity_fact(
        actor,
        "luck_tested",
        f"bad luck — {subject}: {label}",
        {"subject": subject, "trouble": trouble},
    )
    return [rolled, tested]


def attempt_events(source: str, facts: tuple[Fact, ...]) -> tuple[MechanicEvent, ...]:
    resolved = next((fact for fact in facts if fact.kind == "attempt_resolved"), None)
    if resolved is None:
        raise ValueError("no 'attempt_resolved' fact anchors this call")
    if resolved.narrator is None:
        return ()
    badges = tuple(
        badge
        for badge in (_skill_badge(resolved), _help_badge(resolved), _hindered_badge(resolved))
        if badge is not None
    )
    effects = tuple(
        fact.narrator for fact in facts if fact.kind == "luck_tested" and fact.narrator is not None
    )
    dice = [dice_event("Pool", require_dice_role(facts, "pool"))]
    # A riding luck test shows its die even when it came up clear and left no `luck_tested` fact.
    if (luck_roll := dice_by_role(facts, "luck")) is not None:
        dice.append(dice_event("Luck", luck_roll))
    event = MechanicEvent(
        tool=source,
        title="Attempt",
        badges=badges,
        dice=tuple(dice),
        outcome=str(resolved.data["outcome"]),
        effects=effects,
    )
    return (event,)


def luck_test_events(facts: tuple[Fact, ...]) -> tuple[MechanicEvent, ...]:
    rolled = require_dice_role(facts, "luck")
    tested = next((fact for fact in facts if fact.kind == "luck_tested"), None)
    outcome = ""
    if tested is not None and tested.narrator is not None:
        outcome = "Trouble" if tested.data["trouble"] else "Signs"
    return (
        MechanicEvent(
            tool="roll_luck_test",
            title="Luck Test",
            dice=(dice_event("Luck", rolled),),
            outcome=outcome,
            icon="warning",
        ),
    )


def _skill_badge(resolved: Fact) -> EventBadge | None:
    skill = resolved.data["skill"]
    return EventBadge(label="Skill", value=skill) if isinstance(skill, str) and skill else None


def _help_badge(resolved: Fact) -> EventBadge | None:
    """Shows only the die, never the helper's name, to match the unnamed skill badge."""
    faces = resolved.data["faces"]
    if not isinstance(faces, list) or len(faces) < 2:
        return None
    help_die = faces[-1]
    if not isinstance(help_die, int):
        raise ValueError(f"attempt_resolved carries a non-int help die: {faces!r}")
    return EventBadge(label="Help", value=f"d{help_die}")


def _hindered_badge(resolved: Fact) -> EventBadge | None:
    return EventBadge(label="Hindered", value="") if resolved.data["hindered"] else None


def director_toolset() -> AbstractToolset[PlanContext]:
    def roll_attempt(ctx: RunContext[PlanContext], attempt: Attempt) -> str:
        """Put one risky attempt to the highest die of a pool. The player's own attempt goes to
        `stake_attempt` first; roll here directly only for an NPC's attempt, or when the player's
        words already accepted the named risk.

        Args:
            attempt: The attempt to put to the dice.
        """
        return act(ctx, lambda draft, rng: resolve_attempt(draft, attempt, rng))

    def stake_attempt(ctx: RunContext[PlanContext], attempt: Attempt, risk: str) -> str:
        """Name the risk of one attempt out loud and hand the player the choice to proceed or
        revise, before anything is rolled.

        Args:
            attempt: The attempt exactly as it would be rolled; it is frozen here, so what the
                player proceeds with is what rolls.
            risk: What a bad roll costs them, in one line, in your own words: the warning the
                player reads before deciding.
        """
        return act(ctx, lambda draft, _rng: resolve_stake(draft, attempt, risk))

    def settle_defence(ctx: RunContext[PlanContext], item_id: EntityId | None) -> str:
        """Settle the hit the player's own words just answered for: their item breaks and turns
        it into a brief hindrance, or the hit lands in full.

        Args:
            item_id: Exact id of the carried, unbroken item their words break, or null when they
                take the hit instead.
        """
        answered = _defence_to_settle(ctx)
        assert answered is not None  # the filter below offers this tool only while one is open
        goal = Defence.model_validate(answered.payload).goal
        return act(ctx, lambda draft, _rng: resolve_defence(draft, goal, item_id))

    def roll_luck_test(ctx: RunContext[PlanContext], test: LuckTest) -> str:
        """Put the SRD's standalone bad-luck test to the dice.

        Args:
            test: The luck test to put to the dice.
        """
        return act(ctx, lambda draft, rng: resolve_luck_test(draft, test, rng))

    def change_credits(ctx: RunContext[PlanContext], actor_id: EntityId, amount: int) -> str:
        """Move an actor's credits.

        Args:
            actor_id: Exact id of the actor: the player, or an actor here.
            amount: Positive to pay them, negative to charge them.
        """
        return act(
            ctx,
            lambda draft, _rng: tuple(apply_change_credits(draft, actor_id, amount)),
        )

    def complete_chapter(ctx: RunContext[PlanContext]) -> str:
        """Record that the job this crew has been running is done."""
        return act(ctx, lambda draft, _rng: tuple(apply_complete_chapter(draft)))

    toolset = sequential_toolset(
        [
            roll_attempt,
            stake_attempt,
            settle_defence,
            roll_luck_test,
            change_credits,
            complete_chapter,
        ]
    )
    # A hit the player answered in words has to land or be turned, once; nothing else settles one.
    offered = toolset.filtered(
        lambda ctx, tool: tool.name != "settle_defence" or _defence_to_settle(ctx) is not None
    )
    return offered.prepared(_narrow_to_skills_in_play)


GROWTH = (
    "Say which skill this job improves. One skill only: a skill already on the sheet rises a "
    "step up the ladder, or a new one is taken at d8. The engine pays the d6 credits and records "
    "the job itself, so propose neither."
)


class Advance(ProposalBase):
    """The one change a job buys. The engine pays the credits and records the job itself."""

    skill: str = Field(
        min_length=1,
        description="The skill this job improves, in title case: one already on the sheet to "
        "raise it a step, or a new one to take at d8.",
    )
    why: str = Field(description="One short sentence the player reads before confirming.")


class TwentyfourxxAdvancement(Advancement):
    proposal_type = Advance
    ledger_key = "jobs"
    occasion = "finishes a job"
    offer_text = GROWTH
    spent_why = "a job's advance taken"

    def ledger(self, state: Game, subject_id: EntityId) -> Counter:
        return Mechanics.of(state).sheets[subject_id].jobs

    def earned(self, state: Game) -> int:
        return Mechanics.of(state).completed.current

    def grant(
        self, draft: Game, subject_id: EntityId, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        assert isinstance(proposal, Advance)
        sheet = Mechanics.of(draft).sheets[subject_id]
        subject = draft.world.require(subject_id)

        skill = _on_sheet(sheet, proposal.skill)
        die = raised(sheet.skills.get(skill))
        sheet.skills[skill] = die
        grown = explained_fact(
            subject,
            "skill_increased",
            f"{subject.name} raised {skill} to d{die}",
            {"skill": skill, "die": die},
            proposal.why,
            narrate=False,
        )

        earned, dice_fact = roll_pool((6,), "credits earned", rng, role="credits")
        credit_facts = adjust(subject, "credits", sheet.credits, earned, "paid for the job")
        return (grown, dice_fact, *credit_facts)


def _on_sheet(sheet: Sheet, named: str) -> str:
    """A proposal that miscases a skill must raise the one already written, not take a twin."""
    return next((skill for skill in sheet.skills if skill.lower() == named.lower()), named)


class TwentyfourxxCreation(CharacterCreation):
    def __init__(self, packs: Mapping[str, Pack]) -> None:
        self._packs = packs

    def steps(self, picks: Picks) -> tuple[AnyStep, ...]:
        first = pack_step(self._packs)
        chosen = picked(picks, "pack")
        pack = self._packs.get(chosen[0]) if chosen else None
        if pack is None:
            return (first,)
        steps: list[AnyStep] = [
            first,
            CreationStep(
                id="specialty",
                prompt="Choose a specialty",
                options=_options(pack.specialties),
            ),
        ]
        specialty = _picked_entry(pack.specialties, picks, "specialty")
        if specialty is not None and specialty.choices:
            steps.append(
                CreationStep(
                    id="training",
                    prompt="Choose their training",
                    options=_options(specialty.choices),
                )
            )
        steps.append(
            CreationStep(id="origin", prompt="Choose an origin", options=_options(pack.origins))
        )
        origin = _picked_entry(pack.origins, picks, "origin")
        if origin is not None and origin.invents:
            steps.append(
                TextStep(
                    id="traits",
                    prompt=_count_prompt("trait", origin.invents, verb="Invent"),
                    count=origin.invents,
                    hint=", ".join(option.label for option in origin.traits),
                )
            )
        if origin is not None and origin.increases:
            steps.append(
                CreationStep(
                    id="skills",
                    prompt=_count_prompt("further skill", origin.increases),
                    options=pack.skills,
                    choose=origin.increases,
                    repeats=True,
                )
            )
        return tuple(steps)

    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        check_picks(self.steps(picks), picks)
        pack = self._packs[picked(picks, "pack")[0]]
        specialty = _find(pack.specialties, picked(picks, "specialty")[0])
        origin = _find(pack.origins, picked(picks, "origin")[0])

        skills: dict[str, SkillDie] = {}
        for skill in specialty.skills:
            skills[skill] = raised(skills.get(skill))
        for grant_id in picked(picks, "training"):
            grant = _find(specialty.choices, grant_id)
            for skill in grant.skills:
                held = skills.get(skill)
                skills[skill] = grant.die if held is None else max(held, grant.die)
        for skill_id in picked(picks, "skills"):
            label = _find(pack.skills, skill_id).label
            skills[label] = raised(skills.get(label))
        skills_json: dict[str, JsonValue] = {skill: die for skill, die in skills.items()}

        traits: list[Trait] = []
        for written in picked(picks, "traits"):
            taken = [trait.id for trait in traits]
            traits.append(Trait(id=text_slug(written, taken), name=written))
        items = tuple(_carried(entry) for entry in (*pack.starting_kit, *specialty.kit))

        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief, traits=tuple(traits), items=items),
            overlay=CharacterOverlay(
                character={
                    "specialty": specialty.label,
                    "origin": origin.label,
                    "skills": skills_json,
                }
            ),
        )


BULKY = Trait(
    id="bulky", name="Bulky", text="Heavy or awkward to lug; more than one may hinder at times."
)


def _carried(entry: KitItem) -> Entity:
    return Entity(
        id=EntityId(entry.id),
        kind="item",
        name=entry.label,
        brief=entry.detail or entry.label,
        known=True,
        parent_id=PLAYER_ID,
        traits=[BULKY] if entry.bulky else [],
    )


def _options(
    entries: tuple[Specialty, ...] | tuple[Origin, ...] | tuple[SkillGrant, ...],
) -> tuple[CreationOption, ...]:
    return tuple(
        CreationOption(id=entry.id, label=entry.label, detail=entry.detail) for entry in entries
    )


def _find[T: Specialty | Origin | SkillGrant | CreationOption](
    entries: tuple[T, ...], chosen: str
) -> T:
    return next(entry for entry in entries if entry.id == chosen)


def _picked_entry[T: Specialty | Origin](
    entries: tuple[T, ...], picks: Picks, step: str
) -> T | None:
    chosen = picked(picks, step)
    if not chosen:
        return None
    return next((entry for entry in entries if entry.id == chosen[0]), None)


def _count_prompt(what: str, count: int, verb: str = "Choose") -> str:
    return f"{verb} one {what}" if count == 1 else f"{verb} {count} {what}s"


ENGINE_ID: EngineId = EngineId("twentyfourxx")


class TwentyfourxxEngine(Engine):
    id = ENGINE_ID
    badge = ("24XX", "indigo-7")
    engine_dir = Path(__file__).parent
    mechanics_type = Mechanics

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.advancement = TwentyfourxxAdvancement(self.engine_dir)
        self.creation = TwentyfourxxCreation(self.packs)
        self.director_toolsets = (director_toolset(),)

    def check_overlay(self, rules: dict[str, JsonValue]) -> None:
        _ = Sheet.model_validate(rules)

    def opening_mechanics(self, world: WorldState, player_rules: dict[str, JsonValue]) -> Mechanics:
        return Mechanics(sheets=actor_sheets(world, player_rules, Sheet))

    def validate(self, state: Game) -> None:
        check_sheets(state.world, Mechanics.of(state).sheets, self.id)

    def seed(self, draft: Game, entity: Entity, rng: Random) -> None:
        del rng
        mechanics = Mechanics.of(draft)
        if entity.kind != "actor" or entity.id in mechanics.sheets:
            return
        # A newcomer starts level with the party: jobs done before they joined are not owed.
        mechanics.sheets[entity.id] = Sheet(jobs=Counter(current=mechanics.completed.current))

    def resume(
        self, draft: Game, pending: PendingDecision, option_id: OptionId, rng: Random
    ) -> tuple[Fact, ...]:
        match pending.kind, option_id:
            case ("stake", "proceed"):
                return resolve_attempt(draft, Attempt.model_validate(pending.payload), rng)
            case ("defence", _):
                goal = Defence.model_validate(pending.payload).goal
                item = None if option_id == TAKE_THE_HIT else EntityId(option_id)
                return resolve_defence(draft, goal, item)
            case _:
                return super().resume(draft, pending, option_id, rng)

    def check_pending(self, pending: PendingDecision) -> None:
        if pending.kind == "stake":
            _ = Attempt.model_validate(pending.payload)
        elif pending.kind == "defence":
            _ = Defence.model_validate(pending.payload)
        else:
            super().check_pending(pending)

    def describe(self, state: Game, entity: Entity) -> str:
        return describe_entity(Mechanics.of(state), entity)

    def sheet_view(self, state: Game) -> tuple[tuple[str, str], ...]:
        sheet = Mechanics.of(state).sheets[PLAYER_ID]
        return (
            ("Specialty", sheet.specialty),
            ("Origin", sheet.origin),
            (
                "Skills",
                ", ".join(f"{name} d{face}" for name, face in sorted(sheet.skills.items())),
            ),
            ("Credits", str(sheet.credits.current)),
        )

    def player_events(self, source: str, facts: tuple[Fact, ...]) -> tuple[MechanicEvent, ...]:
        if source in ("roll_attempt", "stake"):
            return attempt_events(source, facts)
        if source == "roll_luck_test":
            return luck_test_events(facts)
        return super().player_events(source, facts)
