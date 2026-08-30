from collections.abc import Iterable, Mapping, Sequence
from functools import partial
from pathlib import Path
from random import Random

from pydantic import Field, JsonValue

from aidm.content.io import engine_text
from aidm.content.model import Character
from aidm.engines.core import (
    ADVANCE_SPENT,
    Engine,
    EntityRenderer,
    PackCreation,
    adjust,
    authoring_guidance,
    check_packs,
    describe_rows,
    find_entry,
    load_packs,
    mechanics_of,
    mechanics_patched,
    owed_notes,
    party_member,
    rules,
    sheet_of,
)
from aidm.engines.twentyfourxx.rules import (
    DEFEND,
    GROWTH,
    ROLL_ATTEMPT,
    Advance,
    Attempt,
    GearItem,
    ItemSheet,
    LuckTest,
    Pack,
    Sheet,
    ShipFunction,
    ShipUpgrade,
    SkillDie,
    TwentyfourxxState,
    apply_change_credits,
    move_credits,
    raised,
    resolve_attempt,
    resolve_luck_test,
    resolve_stake,
)
from aidm.state.creation import CreationStep, Picks, check_picks, numbered_steps, picked
from aidm.state.entities import (
    PLAYER_ID,
    CheckedEntityId,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    Slug,
    Trait,
    require_unique,
    slug,
)
from aidm.state.facts import Fact, entity_fact, roll
from aidm.state.model import Game
from aidm.state.play import DecisionOption
from aidm.state.tools import DirectorTool, NoArgs, director_tool
from aidm.world.authoring import rooms_brief, rooms_growth_due
from aidm.world.scene import rooms_scene
from aidm.world.succession import TAKE_OVER, player_over
from aidm.world.tools import DIRECTOR_WORLD, rooms_tools
from aidm.world.topology import validate_rooms

ENGINE_DIR = Path(__file__).parent


def picked_entry[T: DecisionOption](entries: Sequence[T], picks: Picks, step: Slug) -> T | None:
    chosen = picked(picks, step)
    return next((entry for entry in entries if entry.id == chosen), None)


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
        ROLL_ATTEMPT,
        "Roll an actor's risky attempt directly. For the player, use `stake_attempt` first unless "
        "they already accepted the exact `risk`.",
        Attempt,
        resolve_attempt,
    ),
    director_tool(
        "stake_attempt",
        "Show the player one attempt's `risk` and let them accept or revise it before rolling.",
        Attempt,
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
    director_tool(
        "complete_chapter",
        "Record that the current job has ended.",
        NoArgs,
        lambda draft, _args, _rng: complete_chapter(draft),
    ),
)


def complete_chapter(draft: Game) -> tuple[Fact, ...]:
    """Only those who played the chapter are credited with it: nobody is owed one they missed."""
    ending = "the job is done"
    with rules(draft.world, TwentyfourxxState) as game:
        for member_id in (draft.player_id, *draft.world.party):
            sheet = game.sheets.get(member_id)
            if sheet is not None:
                sheet.chapters += 1
    return (Fact(kind="chapter_completed", trace=ending, told=True, card=ending),)


def advance(draft: Game, proposal: Advance, rng: Random) -> tuple[Fact, ...]:
    """One advance per job a party member worked: a skill raised and the job's pay."""
    with rules(draft.world, TwentyfourxxState) as game:
        subject = party_member(draft, proposal.subject_id)
        sheet = sheet_of(game.sheets, subject)
        if sheet.chapters <= sheet.jobs:
            raise ValueError(f"{subject.name} has no advance owed")
        skill = _canonical_skill(sheet, proposal.skill)
        die = raised(sheet.skills.get(skill))
        sheet.skills[skill] = die
        grown = entity_fact(
            subject,
            "skill_increased",
            f"{subject.name} raised {skill} to d{die} ({proposal.why})",
            card=f"{subject.name}: {skill} d{die}",
        )
        (earned,), dice_fact = roll((6,), "credits earned", rng)
        credit_facts = adjust(
            draft,
            subject,
            "credits",
            sheet.credits,
            earned,
            "paid for the job",
        )
        sheet.jobs += 1
        spent = entity_fact(
            subject,
            "job_advance_taken",
            f"{draft.label(subject)} jobs -> {sheet.jobs} (a job's advance taken)",
            card=f"{subject.name}: job {sheet.jobs} advance taken",
        )
    return (grown, dice_fact, *credit_facts, spent)


def _canonical_skill(sheet: Sheet, named: str) -> str:
    return next((skill for skill in sheet.skills if skill.lower() == named.lower()), named)


class TwentyfourxxCreation(PackCreation[Pack]):
    def steps_for(self, pack: Pack, picks: Picks) -> tuple[CreationStep, ...]:
        steps: list[CreationStep] = [
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
        if origin is not None:
            hint = ", ".join(option.label for option in origin.traits)
            steps.extend(numbered_steps("trait", "Invent trait", origin.invents, hint=hint))
            steps.extend(numbered_steps("skill", "Raise skill", origin.increases, pack.skills))
        return tuple(steps)

    def create(self, name: str, brief: str, picks: Picks) -> Character:
        check_picks(self.steps(picks), picks)
        chosen = picked(picks, "pack")
        pack = self.packs[chosen]
        specialty = find_entry(pack.specialties, picked(picks, "specialty"))
        origin = find_entry(pack.origins, picked(picks, "origin"))

        skills: dict[str, SkillDie] = {}
        for skill in specialty.skills:
            skills[skill] = raised(skills.get(skill))
        if grant_id := picked(picks, "training"):
            grant = find_entry(specialty.choices, grant_id)
            for skill in grant.skills:
                held = skills.get(skill)
                skills[skill] = grant.die if held is None else max(held, grant.die)
        for index in range(origin.increases):
            label = find_entry(pack.skills, picked(picks, f"skill-{index + 1}")).label
            skills[label] = raised(skills.get(label))
        skills_json: dict[str, JsonValue] = {skill: die for skill, die in skills.items()}

        traits: list[Trait] = []
        for index in range(origin.invents):
            written = picked(picks, f"trait-{index + 1}")
            traits.append(Trait(id=slug(written, [trait.id for trait in traits]), name=written))
        chosen_kit = [
            find_entry(entries, one)
            for entries, one in (
                (specialty.kit_choice, picked(picks, "specialty-kit")),
                (origin.kit_choice, picked(picks, "origin-kit")),
            )
            if one
        ]
        kit = (*pack.starting_kit, *specialty.kit, *chosen_kit)
        items = tuple(_carried(entry, EntityId(entry.id), PLAYER_ID) for entry in kit)
        sheet = Sheet.model_validate(
            {"specialty": specialty.label, "origin": origin.label, "skills": skills_json}
        )
        return Character(
            id=slug(name, ()),
            engine=EngineId("twentyfourxx"),
            name=name,
            brief=brief,
            traits=tuple(traits),
            items=items,
            mechanics=TwentyfourxxState(
                sheets={PLAYER_ID: sheet},
                items={
                    EntityId(entry.id): ItemSheet.model_validate(marks)
                    for entry in kit
                    if (marks := _marks(entry)) is not None
                },
            ).model_dump(mode="json"),
        )


def _carried(entry: GearItem, item_id: EntityId, owner_id: EntityId) -> Entity:
    return Entity(
        id=item_id,
        kind="item",
        name=entry.label,
        brief=entry.detail or entry.label,
        known=True,
        parent_id=owner_id,
    )


def _marks(entry: GearItem) -> dict[str, JsonValue] | None:
    """Default-free: plain gear gets no sheet at all, and only real marks are written."""
    marks: dict[str, JsonValue] = {}
    if entry.bulky:
        marks["bulky"] = True
    if entry.breaks > 1:
        marks["breaks"] = {"current": entry.breaks, "maximum": entry.breaks}
    return marks or None


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


def _validate(packs: Mapping[str, Pack], state: Game) -> None:
    check_packs(packs, state)
    validate_rooms(state.world)
    game = mechanics_of(state.world, TwentyfourxxState)
    if stray := sorted(set(game.sheets) - set(state.world.entities)):
        raise ValueError(f"mechanics.sheets names entities the world does not hold: {stray}")
    if stray := sorted(set(game.items) - {one.id for one in state.world.of_kind("item")}):
        raise ValueError(f"mechanics.items names items the world does not hold: {stray}")
    # The played character rolls their own skills, so a successor without a sheet cannot play.
    _ = sheet_of(game.sheets, state.player)


def describer(state: Game) -> EntityRenderer:
    game = mechanics_of(state.world, TwentyfourxxState)

    def describe(entity: Entity) -> str:
        sheet = game.sheets.get(entity.id) or game.items.get(entity.id)
        return "" if sheet is None else describe_rows(sheet.rows(), ())

    return describe


def advances_owed(state: Game) -> tuple[tuple[str, str], ...]:
    game = mechanics_of(state.world, TwentyfourxxState)
    return owed_notes(state, game.sheets, lambda sheet: sheet.chapters > sheet.jobs)


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
    item_id = EntityId(slug(entry.label, draft.world.all_ids()))
    with rules(draft.world, TwentyfourxxState) as game:
        paid = move_credits(draft, game, args.actor_id, -entry.cost)
        if (marks := _marks(entry)) is not None:
            game.items[item_id] = ItemSheet.model_validate(marks)
    return [*paid, draft.add(_carried(entry, item_id, args.onto_id or args.actor_id))]


_AUTHORING = (
    "24XX AUTHORING\n"
    "Actors may omit rules; describe opposition through behavior, risks, and obstacles. "
    "An actor that does roll needs a sheet in `mechanics.sheets` under its exact entity "
    "id, using only skill names the selected packs supply."
)


def build(user_packs: Path) -> Engine:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    validate = partial(_validate, packs)
    gear, ship = _gear(packs), _ship(packs)
    return Engine(
        id=EngineId("twentyfourxx"),
        title="24XX",
        instructions=f"{DIRECTOR_WORLD}\n\n{engine_text(ENGINE_DIR / 'director.md')}",
        packs=packs,
        creation=TwentyfourxxCreation(packs),
        validate=validate,
        mechanics_patch=partial(
            mechanics_patched, TwentyfourxxState, entity_maps=("sheets", "items")
        ),
        over=player_over,
        scene=rooms_scene(describer, advances_owed),
        resolvers=(TAKE_OVER, DEFEND),
        authoring_brief=lambda chosen, base, opening: rooms_brief(
            base, opening, authoring_guidance(_AUTHORING, packs, chosen)
        ),
        growth_due=rooms_growth_due,
        tools=rooms_tools(
            validate,
            *DIRECTOR_TOOLS,
            director_tool(
                "buy_gear",
                _for_sale(packs, ship),
                BuyGear,
                lambda draft, one, _rng: _buy_gear(gear, draft, one),
            ),
            director_tool("advance", ADVANCE_SPENT + GROWTH, Advance, advance),
        ),
    )
