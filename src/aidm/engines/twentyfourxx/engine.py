from collections.abc import Iterable, Mapping
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
    character_packs,
    find_entry,
    pack_options,
    picked_entry,
)
from aidm.engines.sources import SHIPPED_PACKS, PackSources
from aidm.engines.twentyfourxx.rules import (
    GROWTH,
    Advance,
    Attempt,
    Defence,
    GearItem,
    LuckTest,
    Mechanics,
    Pack,
    Sheet,
    ShipFunction,
    ShipUpgrade,
    SkillDie,
    StakedAttempt,
    apply_change_credits,
    breaks_trait,
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
    Slug,
    Trait,
    require_unique,
    slug,
)
from aidm.state.facts import Fact, explained_fact
from aidm.state.model import Game


class SettleDefence(Frozen):
    item_id: CheckedEntityId | None = Field(
        description="Exact id of the carried, unbroken item to break, or null to take the hit."
    )


class BuyGear(Frozen):
    actor_id: CheckedEntityId = Field(
        description="Exact id of the player or an actor here who pays."
    )
    gear_id: Slug = Field(description="Exact id of a catalogue entry.")
    onto_id: CheckedEntityId | None = Field(
        default=None,
        description="Exact id of the ship a ship upgrade is installed in, or null to be carried.",
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
        "Roll an actor's risky attempt directly. For the player, use `stake_attempt` first unless "
        "they already accepted the exact risk.",
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

        skill = _canonical_skill(sheet, proposal.skill)
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
            draft, subject, "credits", sheet.credits, earned.kept, "paid for the job", "payments"
        )
        return (grown, dice_fact, *credit_facts)


def _canonical_skill(sheet: Sheet, named: str) -> str:
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
        if specialty is not None and specialty.kit_choice:
            steps.append(
                CreationStep(
                    id="specialty-kit",
                    prompt="Choose your specialty gear",
                    options=pack_options(specialty.kit_choice),
                )
            )
        steps.append(
            CreationStep(id="origin", prompt="Choose an origin", options=pack_options(pack.origins))
        )
        origin = picked_entry(pack.origins, picks, "origin")
        if origin is not None and origin.kit_choice:
            steps.append(
                CreationStep(
                    id="origin-kit",
                    prompt="Choose your origin gear",
                    options=pack_options(origin.kit_choice),
                )
            )
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
        chosen = picked(picks, "pack")[0]
        pack = self.packs[chosen]
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
        chosen_kit = [
            *(find_entry(specialty.kit_choice, one) for one in picked(picks, "specialty-kit")),
            *(find_entry(origin.kit_choice, one) for one in picked(picks, "origin-kit")),
        ]
        items = tuple(
            _carried(entry, EntityId(entry.id), PLAYER_ID)
            for entry in (*pack.starting_kit, *specialty.kit, *chosen_kit)
        )

        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief, traits=tuple(traits), items=items),
            rules={
                "packs": character_packs(chosen),
                "specialty": specialty.label,
                "origin": origin.label,
                "skills": skills_json,
            },
        )


BULKY = Trait(
    id="bulky", name="Bulky", text="Heavy or awkward to lug; more than one may hinder at times."
)


def _carried(entry: GearItem, item_id: EntityId, owner_id: EntityId) -> Entity:
    traits = [BULKY] if entry.bulky else []
    if entry.breaks > 1:
        traits.append(breaks_trait(entry.breaks))
    return Entity(
        id=item_id,
        kind="item",
        name=entry.label,
        brief=entry.detail or entry.label,
        known=True,
        parent_id=owner_id,
        traits=traits,
    )


def _gear(packs: Mapping[str, Pack]) -> dict[Slug, GearItem]:
    entries = tuple(
        item
        for pack in packs.values()
        for item in (*pack.gear, *(up for one in pack.ship for up in one.upgrades))
    )
    require_unique("24XX gear ids across installed packs", (item.id for item in entries))
    return {item.id: item for item in entries}


def _ship(packs: Mapping[str, Pack]) -> tuple[ShipFunction, ...]:
    functions = tuple(one for pack in packs.values() for one in pack.ship)
    require_unique("24XX ship function ids across installed packs", (one.id for one in functions))
    return functions


def _catalogue(gear: Iterable[GearItem]) -> str:
    return ", ".join(f"{one.id} (₡{one.cost})" if one.cost > 1 else one.id for one in gear)


def _for_sale(packs: Mapping[str, Pack], ship: tuple[ShipFunction, ...]) -> str:
    catalogue = _catalogue(item for pack in packs.values() for item in pack.gear)
    offer = (
        "Buy one catalogue item at its printed price, charged to the buyer. "
        f"Most cost ₡1. For sale: {catalogue}"
    )
    if not ship:
        return offer
    return (
        f"{offer}. Every starship already has the basic version of each function below; one of "
        f"their upgrades costs ₡10 and needs `onto_id`. {_functions(ship)}"
    )


def _functions(ship: Iterable[ShipFunction]) -> str:
    lines: list[str] = []
    for one in ship:
        printed = [one.detail] if one.detail else []
        if one.upgrades:
            printed.append(f"Upgrade with {', '.join(up.id for up in one.upgrades)}.")
        lines.append(f"{one.label}: {' '.join(printed)}")
    return " ".join(lines)


def _count_prompt(what: str, count: int, verb: str = "Choose") -> str:
    return f"{verb} one {what}" if count == 1 else f"{verb} {count} {what}s"


class TwentyfourxxEngine(SheetEngine[Sheet]):
    id = EngineId("twentyfourxx")
    badge = ("24XX", "indigo-7")
    engine_dir = Path(__file__).parent
    sheet_type = Sheet
    mechanics_type = Mechanics
    pack_type = Pack
    decisions = (StakedAttempt, Defence)
    authoring_instructions = (
        "24XX AUTHORING\n"
        "Actors may omit rules; describe opposition through behavior, risks, and obstacles. When "
        "an actor has rules, set packs to every table set it uses and use only skill names those "
        "selected packs supply."
    )

    def __init__(self, sources: PackSources = SHIPPED_PACKS) -> None:
        super().__init__(sources)
        self.packs = sources.load(self.engine_dir / "packs", Pack)
        self.gear = _gear(self.packs)
        self.ship = _ship(self.packs)
        self.advancement = TwentyfourxxAdvancement(self.engine_dir)
        self.creation = TwentyfourxxCreation(self.packs)
        self.director_commands = (
            *DIRECTOR_COMMANDS,
            action("buy_gear", _for_sale(self.packs, self.ship), BuyGear, self._buy_gear),
        )

    def pack_models(self) -> Mapping[str, Pack]:
        return self.packs

    def check_sheet(self, entity: Entity, sheet: Sheet) -> None:
        skills: set[str] = set()
        for pack in (self.packs[pack_id] for pack_id in sheet.packs):
            skills.update(option.label for option in pack.skills)
            skills.update(skill for specialty in pack.specialties for skill in specialty.skills)
            skills.update(
                skill
                for specialty in pack.specialties
                for choice in specialty.choices
                for skill in choice.skills
            )
        if unknown := sorted(set(sheet.skills) - skills):
            raise ValueError(
                f"{entity.id!r} uses skills outside packs {list(sheet.packs)!r}: {unknown}"
            )

    def _buy_gear(self, draft: Game, args: BuyGear) -> list[Fact]:
        entry = self.gear.get(args.gear_id)
        if entry is None:
            on_sale = ", ".join(self.gear)
            raise ValueError(
                f"no gear {args.gear_id!r} is for sale. On offer: {on_sale or '(nothing)'}"
            )
        if isinstance(entry, ShipUpgrade):
            if args.onto_id is None:
                raise ValueError(f"{entry.label} is a ship upgrade: name the ship in `onto_id`")
            _ = draft.world.require_kind(args.onto_id, "location")
        elif args.onto_id is not None:
            raise ValueError(f"{entry.label} is carried gear: leave `onto_id` null")
        paid = apply_change_credits(draft, args.actor_id, -entry.cost)
        item_id = EntityId(slug(entry.label, draft.world.all_ids()))
        return [*paid, draft.add(_carried(entry, item_id, args.onto_id or args.actor_id))]
