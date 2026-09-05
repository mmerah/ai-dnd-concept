from collections.abc import Sequence
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, chosen_option, option_of, picked
from aidm.core.entities import EngineId, EntityId, Refusal, Slug, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.model import AnyCharacter
from aidm.core.play import DecisionOption
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import Panel, PanelRow, Rows, Sections, lines_of
from aidm.engines.base import CHANGE_WORLD, PLAYER_ID, Person, keep_highest, sentence
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.tools import NEXT_SCENE, NextScene
from aidm.engines.twentyfourxx.tools import (
    ChangeHindrances,
    ChangeWorld,
    Defend,
    DropItem,
    FindJob,
    FinishJob,
    GainItem,
    RepairItem,
    Roll,
    Spend,
    TakeJob,
    TestLuck,
    WorldChange,
    outcome,
)
from aidm.engines.twentyfourxx.world import (
    DEFAULT_DIE,
    HELP_DIE,
    HINDERED_DIE,
    MAIMED,
    Item,
    Kit,
    Operator,
    SkillDie,
    TwentyfourxxCharacter,
    TwentyfourxxGame,
    TwentyfourxxScenario,
    TwentyfourxxWorld,
    raised,
)
from aidm.engines.twentyfourxx.worldsmith import AUTHORING, Pack


class TwentyfourxxEngine(SceneEngine[Person, Operator, TwentyfourxxGame, Pack]):
    id = EngineId("twentyfourxx")
    title = "24XX"
    art_style = (
        "Clean science-fiction illustration: hard light, neon on steel, lived-in "
        "technology, no text or lettering."
    )
    directory = Path(__file__).parent
    game = TwentyfourxxGame
    scenario = TwentyfourxxScenario
    character = TwentyfourxxCharacter
    cast = Person
    pack = Pack
    world_type = TwentyfourxxWorld

    def master_tools(self) -> tuple[MasterTool[TwentyfourxxGame], ...]:
        return (
            master_tool("change_world", CHANGE_WORLD, ChangeWorld, self.change_world),
            master_tool("next_scene", NEXT_SCENE, NextScene, self.next_scene),
            master_tool(
                "attempt",
                "Roll for something whose outcome matters. Name `helped` with why circumstances "
                "help — an ally who pitches in counts, named in it: the SRD gives them their own "
                "die, but here it is the d6 of circumstance, because an NPC carries no dice. Name "
                "`hindered` with why the player is hindered, when they are.",
                Roll,
                self.attempt,
            ),
            master_tool(
                "test_luck",
                "Roll a d6 to test the world's bad luck, where nobody is acting.",
                TestLuck,
                self.test_luck,
            ),
            master_tool(
                "defend",
                "Break a carried item to turn a hit into a hindrance instead of taking it "
                "outright; word the harm yourself.",
                Defend,
                self.defend,
            ),
            master_tool(
                "find_job",
                "The player looks for work: the SRD's d6. Narrate the job the roll allows; "
                "`spend` ₡1 is the re-roll; `take_job` when they agree.",
                FindJob,
                self.find_job,
            ),
            master_tool(
                "take_job",
                "The player agrees to work: record the job's terms as agreed. Refused while a "
                "job is open.",
                TakeJob,
                self.take_job,
            ),
            master_tool(
                "finish_job",
                "The job is done, by the story and the player's own words: raise the skill it "
                "called on and pay out its credits; the job then closes.",
                FinishJob,
                self.finish_job,
            ),
        )

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        first = self.pack_step()
        pack = self.packs.get(picked(picks, "pack"))
        if pack is None:
            return (first,)
        steps = [
            first,
            CreationStep(id="specialty", prompt="Specialty", options=pack.specialties),
        ]
        specialty = option_of(pack.specialties, picked(picks, "specialty"))
        if specialty is None:
            return tuple(steps)
        if specialty.choice:
            steps.append(
                CreationStep(
                    id="specialty-choice", prompt="Specialty skill", options=specialty.choice
                )
            )
        if specialty.kit_choice:
            steps.append(
                CreationStep(
                    id="weapon",
                    prompt="Weapon",
                    options=tuple(
                        DecisionOption(id=slug(kit.name, ()), label=kit.name)
                        for kit in specialty.kit_choice
                    ),
                )
            )
        steps.append(CreationStep(id="origin", prompt="Origin", options=pack.origins))
        origin = option_of(pack.origins, picked(picks, "origin"))
        if origin is None:
            return tuple(steps)
        for number in range(1, origin.invents + 1):
            steps.append(
                CreationStep(id=f"trait-{number}", prompt=f"Trait {number}", hint=origin.detail)
            )
        if origin.choice:
            steps.append(CreationStep(id="body", prompt="Body", options=origin.choice))
        for number in range(1, origin.increases + 1):
            steps.append(
                CreationStep(id=f"increase-{number}", prompt="Skill increase", options=pack.skills)
            )
        return tuple(steps)

    def create_character(self, name: str, brief: str, picks: Picks) -> TwentyfourxxCharacter:
        check_picks(self.creation_steps(picks), picks)
        pack = self.packs[picked(picks, "pack")]
        specialty = chosen_option(pack.specialties, picked(picks, "specialty"))
        origin = chosen_option(pack.origins, picked(picks, "origin"))

        skills: dict[str, SkillDie] = dict(specialty.skills)
        if specialty.choice:
            chosen = chosen_option(specialty.choice, picked(picks, "specialty-choice"))
            skills.update(chosen.skills)
        for number in range(1, origin.increases + 1):
            option = chosen_option(pack.skills, picked(picks, f"increase-{number}"))
            skills[option.label] = raised(skills.get(option.label))

        weapon: Kit | None = None
        if specialty.kit_choice:
            wanted = picked(picks, "weapon")
            weapon = next(
                (kit for kit in specialty.kit_choice if slug(kit.name, ()) == wanted), None
            )
            if weapon is None:
                raise Refusal(f"{wanted!r} is not one of the weapons on offer")

        traits = tuple(picked(picks, f"trait-{number}") for number in range(1, origin.invents + 1))
        if origin.choice:
            body = chosen_option(origin.choice, picked(picks, "body"))
            traits = (*traits, body.label)

        kits = pack.starting_kit + specialty.kit + ((weapon,) if weapon is not None else ())
        sheet = Operator(
            id=PLAYER_ID,
            name=name,
            brief=brief,
            known=True,
            specialty=specialty.label,
            origin=origin.label,
            traits=traits,
            skills=skills,
            items=starting_items(kits),
        )
        return TwentyfourxxCharacter(id=slug(name, ()), engine=self.id, payload=sheet)

    def preview_character(self, character: AnyCharacter) -> Rows:
        sheet = self.player_of(character)
        return (*sheet.rows(), ("Gear", ", ".join(item.name for item in sheet.items.values())))

    def guidance(self, picks: Sequence[Slug]) -> str:
        """This pack holds creation tables, not setting vocabulary: the preamble alone suffices."""
        return AUTHORING

    def sheet_sections(self, state: TwentyfourxxGame) -> Sections:
        lines = [
            f"- {item.name}[{key}]" + (f" — {detail}" if (detail := item.detail()) else "")
            for key, item in state.payload.player.items.items()
        ]
        job = state.payload.job
        return (("GEAR", lines_of(lines)), *((("THE JOB", job),) if job else ()))

    def panels(self, state: TwentyfourxxGame) -> tuple[Panel, ...]:
        rows = tuple(
            PanelRow(label=item.name, detail=item.detail())
            for item in state.payload.player.items.values()
        )
        job = state.payload.job
        job_panel = Panel(title="Job", rows=(PanelRow(label=job, detail=""),))
        return (Panel(title="Gear", rows=rows), *((job_panel,) if job else ()))

    def resolve_skill(self, player: Operator, wanted: str) -> str:
        folded = wanted.casefold()
        for key in player.skills:
            if key.casefold() == folded:
                return key
        labels: list[str] = []
        for pack in self.packs.values():
            for option in pack.skills:
                if option.label.casefold() == folded:
                    return option.label
                if option.label not in labels:
                    labels.append(option.label)
        sheet = ", ".join(sorted(player.skills)) or "none"
        raise Refusal(
            f"{wanted!r} is not a skill on the sheet ({sheet}) or in the packs "
            f"({', '.join(labels)})"
        )

    def apply_change(self, world: TwentyfourxxWorld, change: WorldChange) -> list[Fact]:
        player = world.player
        match change:
            case ChangeHindrances():
                return player.change_hindrances(change.gained, change.lost)
            case GainItem():
                return player.gain_item(
                    change.name, bulky=change.bulky, breaks=change.breaks, cost=change.cost
                )
            case DropItem():
                return player.drop_item(change.item_id)
            case RepairItem():
                return player.repair_item(change.item_id, change.cost)
            case Spend():
                return player.spend(change.amount, change.why)
            case _:
                return self.shared_change(world, change)

    def change_world(self, draft: TwentyfourxxGame, args: ChangeWorld, _rng: Random) -> list[Fact]:
        return self.apply_change(draft.payload, args.change)

    def attempt(self, draft: TwentyfourxxGame, args: Roll, rng: Random) -> list[Fact]:
        world = draft.payload
        player = world.player

        if args.skill:
            label = self.resolve_skill(player, args.skill)
            die = player.die(label)
        else:
            label = "unskilled"
            die = DEFAULT_DIE
        if args.hindered:
            die = HINDERED_DIE

        reason = f"{args.what} — {label}"
        die_label = f"d{die}+d{HELP_DIE}" if args.helped else f"d{die}"
        if args.helped:
            face, event, dice_fact = keep_highest((die, HELP_DIE), reason, rng, label=die_label)
        else:
            rolled, dice_fact = roll((die,), reason, rng)
            face = rolled[0]
            event = DiceEvent(label=die_label, faces=(die,), rolled=rolled)

        result = outcome(face)
        shown = ", ".join(str(value) for value in event.rolled)
        trace = f"{args.what} — {label} {die_label} [{shown}] -> {result}"
        card = f"{args.what} — {sentence(label)} {die_label} → {result}"
        qualifiers = "; ".join(
            part
            for part in (
                f"helped — {args.helped}" if args.helped else "",
                f"hindered — {args.hindered}" if args.hindered else "",
            )
            if part
        )
        if qualifiers:
            card = f"{card} ({qualifiers})"

        facts: list[Fact] = [dice_fact, player.fact("attempted", trace, card=card, dice=(event,))]

        if args.risking_death and result == "disaster":
            facts.extend(world.kill(player.id))
        elif args.risking_death and result == "setback" and MAIMED not in player.hindrances:
            player.hindrances.append(MAIMED)
            trace = f"{player.label} is maimed"
            facts.append(player.fact("hindrances_changed", trace, card="Maimed"))

        return facts

    def find_job(self, draft: TwentyfourxxGame, args: FindJob, rng: Random) -> list[Fact]:
        world = draft.payload
        if world.job:
            raise Refusal(f"a job is open: {world.job}")
        rolled, dice_fact = roll((6,), args.where, rng)
        face = rolled[0]
        if face <= 2:
            result = "nothing; the player owes somebody to get in on a job"
        elif face <= 4:
            result = "a job, but something seems off"
        else:
            result = "a choice between two jobs"
        trace = f"{args.where} — d6 [{face}] -> {result}"
        card = f"{args.where} — d6 → {result}"
        return [
            dice_fact,
            world.player.fact(
                "job_sought",
                trace,
                card=card,
                dice=(DiceEvent(label="d6", faces=(6,), rolled=rolled),),
            ),
        ]

    def take_job(self, draft: TwentyfourxxGame, args: TakeJob, _rng: Random) -> list[Fact]:
        world = draft.payload
        if world.job:
            raise Refusal(f"a job is open: {world.job}")
        world.job = args.terms
        return [
            world.player.fact(
                "job_taken",
                f"the job is taken: {args.terms}",
                card=f"Job taken\n{args.terms}",
            )
        ]

    def finish_job(self, draft: TwentyfourxxGame, args: FinishJob, rng: Random) -> list[Fact]:
        world = draft.payload
        if not world.job:
            raise Refusal("no job is open to finish")
        player = world.player
        label = self.resolve_skill(player, args.skill)
        new_die = raised(player.skills.get(label))
        player.skills[label] = new_die
        trace = f"{player.label} — {label} rises to d{new_die}"
        raise_fact = player.fact("skill_raised", trace, card=f"Job done: {label} d{new_die}")

        rolled, dice_fact = roll((6,), "credits earned", rng)
        gained = rolled[0]
        player.credits += gained
        credit_fact = player.fact(
            "credits_gained",
            f"{player.label} earns ₡{gained} -> ₡{player.credits}",
            card=f"+₡{gained} -> ₡{player.credits}",
            dice=(DiceEvent(label="d6", faces=(6,), rolled=rolled),),
        )
        world.job = ""
        return [raise_fact, dice_fact, credit_fact]

    def test_luck(self, _draft: TwentyfourxxGame, args: TestLuck, rng: Random) -> list[Fact]:
        rolled, dice_fact = roll((6,), args.question, rng)
        face = rolled[0]
        if face <= 2:
            result = "trouble now"
        elif face <= 4:
            result = "signs of it"
        else:
            result = "nothing"
        trace = f"{args.question} — d6 [{face}] -> {result}"
        return [dice_fact, Fact(kind="luck_tested", trace=trace)]

    def defend(self, draft: TwentyfourxxGame, args: Defend, _rng: Random) -> list[Fact]:
        player = draft.payload.player
        item = player.require_item(args.item_id)
        if item.broken:
            raise Refusal(f"{item.name} is already broken")
        if args.hindrance in player.hindrances:
            raise Refusal(f"{args.hindrance!r} is already among the player's hindrances")
        item.broken_times += 1
        player.hindrances.append(args.hindrance)
        card = f"{item.name} breaks — {args.hindrance}"
        trace = f"{player.label} breaks {item.name} — {args.hindrance}"
        return [player.fact("item_broken", trace, card=card)]


def starting_items(kits: Sequence[Kit]) -> dict[EntityId, Item]:
    taken: list[str] = []
    items: dict[EntityId, Item] = {}
    for kit in kits:
        key = slug(kit.name, taken)
        taken.append(key)
        items[EntityId(key)] = Item(name=kit.name, bulky=kit.bulky, breaks=kit.breaks)
    return items
