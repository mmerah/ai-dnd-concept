from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from random import Random

from pydantic import Field, JsonValue

from aidm.content.io import engine_text
from aidm.content.model import Character, CharacterProfile
from aidm.engines.core import (
    ADVANCE_TOOL,
    DirectorTool,
    Engine,
    EntityRules,
    NoRules,
    PackCreation,
    adjust,
    advances_owed,
    chapter_tool,
    describe_by,
    director_tool,
    find_entry,
    load_packs,
    party_member,
    rules,
)
from aidm.engines.twentyfourxx.rules import (
    GROWTH,
    Advance,
    Attempt,
    Defence,
    GearItem,
    ItemSheet,
    LuckTest,
    Pack,
    Sheet,
    ShipFunction,
    ShipUpgrade,
    SkillDie,
    StakedAttempt,
    apply_change_credits,
    raised,
    resolve_attempt,
    resolve_luck_test,
    resolve_stake,
)
from aidm.engines.world import CORE_TOOLS
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
from aidm.state.entities import (
    PLAYER_ID,
    CheckedEntityId,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    Kind,
    Slug,
    Trait,
    require_unique,
    slug,
)
from aidm.state.facts import Fact, MechanicEvent, entity_fact
from aidm.state.model import Game

ENGINE_DIR = Path(__file__).parent


def picked_entry[T: CreationOption](entries: Sequence[T], picks: Picks, step: Slug) -> T | None:
    chosen = picked(picks, step)[:1]
    return next((entry for entry in entries if entry.id in chosen), None)


RULES_TYPES: Mapping[Kind, type[EntityRules]] = {
    "actor": Sheet,
    "item": ItemSheet,
    "location": NoRules,
}


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


DIRECTOR_TOOLS: tuple[DirectorTool, ...] = (
    director_tool(
        "roll_attempt",
        "Roll an actor's risky attempt directly. For the player, use `stake_attempt` first unless "
        "they already accepted the exact `risk`.",
        Attempt,
        resolve_attempt,
    ),
    director_tool(
        "stake_attempt",
        "Show the player one attempt's `risk` and let them accept or revise it before rolling.",
        StakedAttempt,
        lambda draft, one, _rng: resolve_stake(draft, one),
    ),
    director_tool(
        "roll_luck_test", "Roll a standalone bad-luck test.", LuckTest, resolve_luck_test
    ),
    director_tool(
        "change_credits",
        "Pay or charge an actor.",
        ChangeCredits,
        lambda draft, one, _rng: apply_change_credits(draft, one.actor_id, one.amount),
    ),
    chapter_tool("Record that the current job has ended.", "the job is done", Sheet),
)


def advance(draft: Game, proposal: Advance, rng: Random) -> tuple[Fact, ...]:
    """One advance per job a party member worked: a skill raised and the job's pay."""
    subject = party_member(draft, proposal.subject_id)
    with rules(subject, Sheet) as sheet:
        if sheet.chapters <= sheet.jobs:
            raise ValueError(f"{subject.name} has no advance owed")
        skill = _canonical_skill(sheet, proposal.skill)
        die = raised(sheet.skills.get(skill))
        sheet.skills[skill] = die
        grown = entity_fact(
            subject,
            "skill_increased",
            f"{subject.name} raised {skill} to d{die} ({proposal.why})",
            event=MechanicEvent(title=f"{subject.name}: {skill} d{die}", icon="military_tech"),
        )
        earned, dice_fact = roll_pool((6,), "credits earned", rng, label="Credits")
        credit_facts = adjust(
            draft, subject, "credits", sheet.credits, earned.kept, "paid for the job", "payments"
        )
        sheet.jobs += 1
        spent = entity_fact(
            subject,
            "job_advance_taken",
            f"{draft.label(subject)} jobs -> {sheet.jobs} (a job's advance taken)",
            event=MechanicEvent(
                title=f"{subject.name}: job {sheet.jobs} advance taken", icon="military_tech"
            ),
        )
    return (grown, dice_fact, *credit_facts, spent)


def _canonical_skill(sheet: Sheet, named: str) -> str:
    return next((skill for skill in sheet.skills if skill.lower() == named.lower()), named)


class TwentyfourxxCreation(PackCreation[Pack]):
    def steps_for(self, pack: Pack, picks: Picks) -> tuple[AnyStep, ...]:
        steps: list[AnyStep] = [
            CreationStep(
                id="specialty",
                prompt="Choose a specialty",
                options=pack.specialties,
            ),
        ]
        specialty = picked_entry(pack.specialties, picks, "specialty")
        if specialty is not None and specialty.choices:
            steps.append(
                CreationStep(
                    id="training",
                    prompt="Choose training",
                    options=specialty.choices,
                )
            )
        if specialty is not None and specialty.kit_choice:
            steps.append(
                CreationStep(
                    id="specialty-kit",
                    prompt="Choose your specialty gear",
                    options=specialty.kit_choice,
                )
            )
        steps.append(CreationStep(id="origin", prompt="Choose an origin", options=pack.origins))
        origin = picked_entry(pack.origins, picks, "origin")
        if origin is not None and origin.kit_choice:
            steps.append(
                CreationStep(
                    id="origin-kit",
                    prompt="Choose your origin gear",
                    options=origin.kit_choice,
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

    def create(self, name: str, brief: str, picks: Picks) -> Character:
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

        return Character(
            id=slug(name, ()),
            profile=CharacterProfile(name=name, brief=brief, traits=tuple(traits), items=items),
            rules={
                "specialty": specialty.label,
                "origin": origin.label,
                "skills": skills_json,
            },
        )


def _carried(entry: GearItem, item_id: EntityId, owner_id: EntityId) -> Entity:
    # Default-free, so a plain item's `rules` stays empty and its sheet is only made if it breaks.
    rules: dict[str, JsonValue] = {}
    if entry.bulky:
        rules["bulky"] = True
    if entry.breaks > 1:
        rules["breaks"] = {"current": entry.breaks, "maximum": entry.breaks}
    return Entity(
        id=item_id,
        kind="item",
        name=entry.label,
        brief=entry.detail or entry.label,
        known=True,
        parent_id=owner_id,
        rules=rules,
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


def _checks(state: Game) -> None:
    # The played character rolls their own skills, so a successor without rules cannot play.
    if not state.player.rules:
        raise ValueError(f"{state.player.name} has no character sheet")


def _buy_gear(gear: Mapping[Slug, GearItem], draft: Game, args: BuyGear) -> list[Fact]:
    entry = gear.get(args.gear_id)
    if entry is None:
        on_sale = ", ".join(gear)
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


def build(user_packs: Path) -> Engine:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    gear, ship = _gear(packs), _ship(packs)
    return Engine(
        id=EngineId("twentyfourxx"),
        badge=("24XX", "indigo-7"),
        director_instructions=engine_text(ENGINE_DIR / "director.md"),
        rules_types=RULES_TYPES,
        packs=packs,
        creation=TwentyfourxxCreation(packs),
        checks=_checks,
        describe=describe_by(RULES_TYPES),
        decisions=(StakedAttempt, Defence),
        owed_notes=lambda state: advances_owed(state, Sheet, lambda sheet: sheet.jobs),
        authoring_instructions=(
            "24XX AUTHORING\n"
            "Actors may omit rules; describe opposition through behavior, risks, and obstacles. "
            "When an actor has rules, use only skill names the selected packs supply."
        ),
        director_tools=(
            *CORE_TOOLS,
            *DIRECTOR_TOOLS,
            director_tool(
                "buy_gear",
                _for_sale(packs, ship),
                BuyGear,
                lambda draft, one, _rng: _buy_gear(gear, draft, one),
            ),
            director_tool("advance", ADVANCE_TOOL + GROWTH, Advance, advance),
        ),
    )
