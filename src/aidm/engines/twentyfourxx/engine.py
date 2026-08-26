from pathlib import Path
from random import Random

from pydantic import Field, JsonValue

from aidm.content.model import CharacterProfile, CreatedCharacter
from aidm.engines.core import (
    Command,
    DirectorContext,
    ProposalBase,
    SheetAdvancement,
    SheetEngine,
    action,
    adjust,
    apply_play,
    chapter_command,
    command,
    rule,
)
from aidm.engines.packs import (
    PackCreation,
    find_entry,
    load_packs,
    pack_options,
    pack_paths,
    picked_entry,
)
from aidm.engines.twentyfourxx.rules import (
    GROWTH,
    Advance,
    Attempt,
    Defence,
    KitItem,
    LuckTest,
    Mechanics,
    Pack,
    Sheet,
    SkillDie,
    StakedAttempt,
    apply_change_credits,
    raised,
    resolve_attempt,
    resolve_defence,
    resolve_luck_test,
    resolve_stake,
)
from aidm.state.actions import roll_pool
from aidm.state.creation import (
    AnyStep,
    CreationStep,
    Picks,
    TextStep,
    check_picks,
    picked,
)
from aidm.state.entities import (
    PLAYER_ID,
    CheckedEntityId,
    Counter,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    Trait,
    slug,
)
from aidm.state.facts import Fact, explained_fact
from aidm.state.model import Game


class SettleDefence(Frozen):
    item_id: CheckedEntityId | None = Field(
        description="Exact id of the carried, unbroken item to break, or null to take the hit."
    )


class ChangeCredits(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or an actor here.")
    amount: int = Field(description="Positive pays the actor; negative charges them.")


def _settle_defence(deps: DirectorContext, args: SettleDefence) -> str:
    # One hit, one settlement: the decision an open answer consumed, until this run settles it.
    answered = deps.answered
    settled = any(fact.kind in ("defence_turned", "defence_taken") for fact in deps.log.facts)
    if answered is None or answered.kind != "defence" or settled:
        raise ValueError("no hit is waiting to be settled; there is nothing to break or take.")
    goal = Defence.model_validate(answered.payload).goal
    return apply_play(deps, lambda draft, _rng: resolve_defence(draft, goal, args.item_id))


DIRECTOR_COMMANDS: tuple[Command, ...] = (
    rule(
        "roll_attempt",
        "Roll one risky attempt. Roll an NPC's attempt directly; put the player's own attempt\n"
        "to `stake_attempt` first, unless their words already accepted the exact risk.",
        Attempt,
        resolve_attempt,
    ),
    action(
        "stake_attempt",
        "Let the player accept or revise one risky attempt before rolling it.",
        StakedAttempt,
        resolve_stake,
    ),
    command(
        "settle_defence",
        "Apply the player's choice to break an item or take the full hit.",
        SettleDefence,
        _settle_defence,
    ),
    rule("roll_luck_test", "Roll a standalone bad-luck test.", LuckTest, resolve_luck_test),
    action(
        "change_credits",
        "Pay or charge an actor.",
        ChangeCredits,
        lambda draft, one: apply_change_credits(draft, one.actor_id, one.amount),
    ),
    chapter_command("Record that the current job has ended.", "the job is done"),
)


class TwentyfourxxAdvancement(SheetAdvancement):
    proposal_type = Advance
    ledger_key = "jobs"
    occasion = "finishes a job"
    offer_text = GROWTH
    spent_why = "a job's advance taken"

    def ledger(self, state: Game, subject_id: EntityId) -> Counter:
        return Mechanics.of_game(state).sheets[subject_id].jobs

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
            proposal.why,
            narrate=False,
        )

        earned, dice_fact = roll_pool((6,), "credits earned", rng, label="Credits")
        credit_facts = adjust(
            subject, "credits", sheet.credits, earned.kept, "paid for the job", "payments"
        )
        return (grown, dice_fact, *credit_facts)


def _on_sheet(sheet: Sheet, named: str) -> str:
    """A proposal that miscases a skill must raise the one already written, not take a twin."""
    return next((skill for skill in sheet.skills if skill.lower() == named.lower()), named)


class TwentyfourxxCreation(PackCreation[Pack]):
    def steps_for(self, pack: Pack, picks: Picks) -> tuple[AnyStep, ...]:
        steps: list[AnyStep] = [
            CreationStep(
                id="specialty",
                prompt="Choose a specialty",
                options=pack_options(pack.specialties),
            ),
        ]
        specialty = picked_entry(pack.specialties, picks, "specialty")
        if specialty is not None and specialty.choices:
            steps.append(
                CreationStep(
                    id="training",
                    prompt="Choose training",
                    options=pack_options(specialty.choices),
                )
            )
        steps.append(
            CreationStep(id="origin", prompt="Choose an origin", options=pack_options(pack.origins))
        )
        origin = picked_entry(pack.origins, picks, "origin")
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

    def create(self, name: str, brief: str, picks: Picks, rng: Random) -> CreatedCharacter:
        del rng
        check_picks(self.steps(picks), picks)
        pack = self.packs[picked(picks, "pack")[0]]
        specialty = find_entry(pack.specialties, picked(picks, "specialty")[0])
        origin = find_entry(pack.origins, picked(picks, "origin")[0])

        skills: dict[str, SkillDie] = {}
        for skill in specialty.skills:
            skills[skill] = raised(skills.get(skill))
        for grant_id in picked(picks, "training"):
            grant = find_entry(specialty.choices, grant_id)
            for skill in grant.skills:
                held = skills.get(skill)
                skills[skill] = grant.die if held is None else max(held, grant.die)
        for skill_id in picked(picks, "skills"):
            label = find_entry(pack.skills, skill_id).label
            skills[label] = raised(skills.get(label))
        skills_json: dict[str, JsonValue] = {skill: die for skill, die in skills.items()}

        traits: list[Trait] = []
        for written in picked(picks, "traits"):
            taken = [trait.id for trait in traits]
            traits.append(Trait(id=slug(written, taken), name=written))
        items = tuple(_carried(entry) for entry in (*pack.starting_kit, *specialty.kit))

        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief, traits=tuple(traits), items=items),
            rules={
                "specialty": specialty.label,
                "origin": origin.label,
                "skills": skills_json,
            },
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


def _count_prompt(what: str, count: int, verb: str = "Choose") -> str:
    return f"{verb} one {what}" if count == 1 else f"{verb} {count} {what}s"


class TwentyfourxxEngine(SheetEngine[Sheet]):
    id = EngineId("twentyfourxx")
    badge = ("24XX", "indigo-7")
    engine_dir = Path(__file__).parent
    sheet_type = Sheet
    mechanics_type = Mechanics
    decisions = (StakedAttempt, Defence)

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.advancement = TwentyfourxxAdvancement(self.engine_dir)
        self.creation = TwentyfourxxCreation(self.packs)
        self.director_commands = DIRECTOR_COMMANDS
