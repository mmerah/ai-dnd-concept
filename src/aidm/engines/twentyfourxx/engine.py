from collections.abc import Mapping
from pathlib import Path
from random import Random

from pydantic import JsonValue
from pydantic_ai import RunContext
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset

from aidm.content.model import CharacterOverlay, CharacterProfile, CreatedCharacter
from aidm.engines.core import (
    Advancement,
    CharacterCreation,
    Engine,
    EventCause,
    PlanContext,
    ProposalBase,
    act,
    actor_sheets,
    adjust,
    check_sheets,
    load_packs,
    pack_paths,
    pack_step,
    require_sheet,
    sequential_toolset,
    with_enum,
)
from aidm.engines.twentyfourxx.rules import (
    GROWTH,
    TAKE_THE_HIT,
    Advance,
    Attempt,
    Defence,
    KitItem,
    LuckTest,
    Mechanics,
    Origin,
    Pack,
    Sheet,
    SkillDie,
    SkillGrant,
    Specialty,
    apply_change_credits,
    apply_complete_chapter,
    attempt_events,
    describe_entity,
    luck_test_events,
    raised,
    resolve_attempt,
    resolve_defence,
    resolve_luck_test,
    resolve_stake,
)
from aidm.state.actions import roll_pool
from aidm.state.creation import (
    AnyStep,
    CreationOption,
    CreationStep,
    Picks,
    TextStep,
    check_picks,
    picked,
)
from aidm.state.entities import PLAYER_ID, Counter, EngineId, Entity, EntityId, Trait, text_slug
from aidm.state.facts import Fact, explained_fact
from aidm.state.model import Game, WorldState
from aidm.state.play import MechanicEvent, OptionId, PendingDecision


def _skills_in_play(state: Game) -> set[str]:
    """Limit attempt skills to actors present with the player."""
    sheets = Mechanics.of_game(state).sheets
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


class TwentyfourxxAdvancement(Advancement):
    proposal_type = Advance
    ledger_key = "jobs"
    occasion = "finishes a job"
    offer_text = GROWTH
    spent_why = "a job's advance taken"

    def ledger(self, state: Game, subject_id: EntityId) -> Counter:
        return Mechanics.of_game(state).sheets[subject_id].jobs

    def earned(self, state: Game) -> int:
        return Mechanics.of_game(state).completed.current

    def grant(
        self, draft: Game, subject_id: EntityId, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        assert isinstance(proposal, Advance)
        sheet = Mechanics.of_game(draft).sheets[subject_id]
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


class TwentyfourxxEngine(Engine):
    id = EngineId("twentyfourxx")
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
        check_sheets(state.world, Mechanics.of_game(state).sheets, self.id)

    def seed(self, draft: Game, entity: Entity, rng: Random) -> None:
        del rng
        mechanics = Mechanics.of_game(draft)
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
        return describe_entity(Mechanics.of_game(state), entity)

    def sheet_view(self, state: Game) -> tuple[tuple[str, str], ...]:
        sheet = Mechanics.of_game(state).sheets[PLAYER_ID]
        return (
            ("Specialty", sheet.specialty),
            ("Origin", sheet.origin),
            (
                "Skills",
                ", ".join(f"{name} d{face}" for name, face in sorted(sheet.skills.items())),
            ),
            ("Credits", str(sheet.credits.current)),
        )

    def player_events(
        self, cause: EventCause, facts: tuple[Fact, ...]
    ) -> tuple[MechanicEvent, ...]:
        if cause in (EventCause("tool", "roll_attempt"), EventCause("decision", "stake")):
            return attempt_events(cause.name, facts)
        if cause == EventCause("tool", "roll_luck_test"):
            return luck_test_events(facts)
        return super().player_events(cause, facts)
