from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, chosen_option, option_of, picked
from aidm.core.entities import EngineId, EntityId, Refusal, Slug, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.model import Generation, WorldsmithAnswer
from aidm.core.play import DecisionOption, PendingDecision, PendingOption
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import Panel, PanelRow, Sections, lines_of
from aidm.engines.base import (
    CHANGE_WORLD,
    HIRE,
    HIRE_TOOL,
    PLAYER_ID,
    Hire,
    hire_target,
    keep_highest,
    sentence,
)
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.tools import NEXT_SCENE, NextScene
from aidm.engines.twentyfourxx.tools import (
    ChangeHindrances,
    ChangeWorld,
    Defend,
    DropItem,
    GainItem,
    Job,
    Raise,
    RepairItem,
    Roll,
    ShipUpgrade,
    Spend,
    TakeLead,
    TestLuck,
    WorldChange,
    outcome,
)
from aidm.engines.twentyfourxx.world import (
    DEFAULT_DIE,
    HELP_DIE,
    HINDERED_DIE,
    MAIMED,
    Crewmate,
    Item,
    Kit,
    Sheet,
    SkillDie,
    TwentyfourxxCharacter,
    TwentyfourxxGame,
    TwentyfourxxScenario,
    TwentyfourxxWorld,
    raised,
)
from aidm.engines.twentyfourxx.worldsmith import AUTHORING, HIRING, Pack, SheetDraft


class TwentyfourxxEngine(SceneEngine[Crewmate, Crewmate, TwentyfourxxGame, Pack]):
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
    cast = Crewmate
    pack = Pack
    world_type = TwentyfourxxWorld
    operations = (*SceneEngine.operations, HIRE)

    def master_tools(self) -> tuple[MasterTool[TwentyfourxxGame], ...]:
        return (
            master_tool("change_world", CHANGE_WORLD, ChangeWorld, self.change_world),
            master_tool("next_scene", NEXT_SCENE, NextScene, self.next_scene),
            master_tool(
                "roll",
                "Roll for something whose outcome matters. Name `helped` with why circumstances "
                "help, when they do. Name `hindered` with why the actor is hindered, when they "
                "are. `helped_by` names a hired crew member who rolls their own die beside the "
                "actor's; `actor_id` when a hired member acts instead of the player.",
                Roll,
                self.roll,
            ),
            master_tool(
                "test_luck",
                "Roll a d6 to test the world's bad luck, where nobody is acting.",
                TestLuck,
                self.test_luck,
            ),
            master_tool(
                "job",
                "`find` rolls the SRD's d6 for work — narrate the job it allows, `spend` ₡1 for "
                "a re-roll; `take` records the job's terms once agreed, refused while one is "
                "already open; `finish` closes it: raise the skill it called on for the player "
                "and every living hired member, and pay out its credits.",
                Job,
                self.job,
            ),
            master_tool("hire", HIRE_TOOL, Hire, self.hire),
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
        body = None
        if origin.choice:
            body = chosen_option(origin.choice, picked(picks, "body"))
            traits = (*traits, body.label)

        kits = (
            pack.starting_kit
            + specialty.kit
            + ((weapon,) if weapon is not None else ())
            + ((body.kit,) if body is not None and body.kit is not None else ())
        )
        player = Crewmate(
            id=PLAYER_ID,
            name=name,
            brief=brief,
            known=True,
            sheet=Sheet(
                specialty=specialty.label,
                origin=origin.label,
                traits=traits,
                skills=skills,
                items=starting_items(kits),
            ),
        )
        return TwentyfourxxCharacter(id=slug(name, ()), engine=self.id, payload=player)

    def guidance(self, picks: Sequence[Slug]) -> str:
        """This pack holds creation tables, not setting vocabulary: the preamble alone suffices."""
        return AUTHORING

    def sheet_sections(self, state: TwentyfourxxGame) -> Sections:
        world = state.payload
        job = world.job
        return (
            ("GEAR", _item_lines(world.player.dice().items)),
            *((("THE JOB", job),) if job else ()),
            ("THE SHIP", _item_lines(world.ship)),
        )

    def panels(self, state: TwentyfourxxGame) -> tuple[Panel, ...]:
        world = state.payload
        job = world.job
        job_panel = (Panel(title="Job", rows=(PanelRow(label=job, detail=""),)),) if job else ()
        ship_panel = Panel(
            title="Ship",
            rows=tuple(
                PanelRow(label=function.name, detail=function.detail())
                for function in world.ship.values()
            ),
        )
        return (*job_panel, ship_panel)

    def resolve_skill(self, sheet: Sheet, wanted: str) -> str:
        folded = wanted.casefold()
        for key in sheet.skills:
            if key.casefold() == folded:
                return key
        labels: list[str] = []
        for pack in self.packs.values():
            for option in pack.skills:
                if option.label.casefold() == folded:
                    return option.label
                if option.label not in labels:
                    labels.append(option.label)
        known = ", ".join(sorted(sheet.skills)) or "none"
        raise Refusal(
            f"{wanted!r} is not a skill on the sheet ({known}) or in the packs "
            f"({', '.join(labels)})"
        )

    def apply_change(self, world: TwentyfourxxWorld, change: WorldChange) -> list[Fact]:
        match change:
            case ChangeHindrances():
                return world.require_actor(change.actor_id).change_hindrances(
                    change.gained, change.lost
                )
            case GainItem():
                return world.require_actor(change.actor_id).gain_item(
                    change.name, bulky=change.bulky, breaks=change.breaks, cost=change.cost
                )
            case DropItem():
                return world.require_actor(change.actor_id).drop_item(change.item_id)
            case RepairItem():
                actor = world.require_actor(change.actor_id)
                return actor.repair_item(world.require_gear(actor, change.item_id), change.cost)
            case Spend():
                return world.require_actor(change.actor_id).spend(change.amount, change.why)
            case TakeLead():
                return world.take_lead(change.entity_id)
            case ShipUpgrade():
                return world.upgrade_ship(change.function_id)
            case Defend():
                return world.defend(change.actor_id, change.item_id, change.hindrance)
            case _:
                return self.shared_change(world, change)

    def change_world(self, draft: TwentyfourxxGame, args: ChangeWorld, _rng: Random) -> list[Fact]:
        facts = self.apply_change(draft.payload, args.change)
        self._succession(draft)
        return facts

    def _succession(self, draft: TwentyfourxxGame) -> None:
        """Sits on the draft: `apply_change` sees only the world; the decision is the game's."""
        world = draft.payload
        if world.player.alive or not (members := world.sheeted_members()):
            return
        draft.pending = PendingDecision(
            kind="succession",
            prompt="Who leads now?",
            options=tuple(
                PendingOption(
                    id=member.id,
                    label=member.name,
                    detail=member.brief,
                    name="change_world",
                    args={"change": {"verb": "take_lead", "entity_id": member.id}},
                )
                for member in members
            ),
            allows_text=False,
        )

    def over(self, state: TwentyfourxxGame) -> str | None:
        """A dead lead with a hired member alive is a succession, not an ending."""
        return None if state.payload.sheeted_members() else super().over(state)

    async def advance(
        self, draft: TwentyfourxxGame, request: Generation, worldsmith: WorldsmithAnswer
    ) -> tuple[tuple[Fact, ...], str | None]:
        if request.operation != HIRE:
            return await super().advance(draft, request, worldsmith)
        world = draft.payload
        member = world.require_hireable(hire_target(request))
        pack = self.packs[draft.packs[0]]
        prompt = self.render_request(
            draft,
            guidance=pack.hire_guidance(),
            intent=HIRING.format(name=member.name, brief=member.brief, terms=request.brief),
            answer=SheetDraft,
        )
        answer = await worldsmith(prompt, SheetDraft, lambda sheet: sheet.refusal(pack))
        specialty = answer.specialty
        member.sheet = Sheet(
            specialty=specialty,
            skills=dict(answer.skills),
            credits=0,
            items=starting_items(tuple(Kit(name=name) for name in answer.items)),
            hindrances=list(answer.hindrances),
        )
        return world.sign_on(member, specialty)

    def roll(self, draft: TwentyfourxxGame, args: Roll, rng: Random) -> list[Fact]:
        world = draft.payload
        actor = world.require_actor(args.actor_id)
        sheet = actor.dice()
        helper = None
        if args.helped_by is not None:
            helper = world.require_actor(args.helped_by)
            if helper is actor:
                raise Refusal(f"{actor.name} cannot help their own roll")

        if args.skill:
            label = self.resolve_skill(sheet, args.skill)
            die = sheet.die(label)
        else:
            label = "unskilled"
            die = DEFAULT_DIE
        if args.hindered:
            die = HINDERED_DIE

        pool = [die]
        if args.helped:
            pool.append(HELP_DIE)
        helped_by_clause = ""
        if helper is not None:
            helper_die = helper.dice().die(label)
            pool.append(helper_die)
            helped_by_clause = f", helped by {helper.name} (d{helper_die})"

        reason = f"{args.what} — {label}"
        if len(pool) == 1:
            rolled, dice_fact = roll((die,), reason, rng)
            face = rolled[0]
            event = DiceEvent(label=f"d{die}", faces=(die,), rolled=rolled)
        else:
            die_label = "+".join(f"d{face}" for face in pool)
            face, event, dice_fact = keep_highest(pool, reason, rng, label=die_label)

        result = outcome(face)
        line = (
            f"{args.what} — {sentence(label)} d{die}"
            if actor is world.player
            else f"{args.what} — {actor.name}: {sentence(label)} d{die}"
        )
        if args.helped:
            line += f", helped ({args.helped})"
        line += helped_by_clause
        if args.hindered:
            line += f", hindered ({args.hindered})"
        line += f" → {result}"

        facts: list[Fact] = [dice_fact, actor.fact("attempted", line, card=line, dice=(event,))]

        if args.risking_death and result == "disaster":
            facts.extend(world.kill(actor.id))
        elif args.risking_death and result == "setback" and MAIMED not in sheet.hindrances:
            sheet.hindrances.append(MAIMED)
            trace = f"{actor.label} is maimed"
            facts.append(actor.fact("hindrances_changed", trace, card="Maimed"))
        self._succession(draft)

        return facts

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

    def job(self, draft: TwentyfourxxGame, args: Job, rng: Random) -> list[Fact]:
        match args.verb:
            case "find":
                return self._find(draft, args.where, rng)
            case "take":
                return self._take(draft, args.terms)
            case "finish":
                return self._finish(draft, args.raises, rng)

    def _find(self, draft: TwentyfourxxGame, where: str, rng: Random) -> list[Fact]:
        world = draft.payload
        if world.job:
            raise Refusal(f"a job is open: {world.job}")
        rolled, dice_fact = roll((6,), where, rng)
        face = rolled[0]
        if face <= 2:
            result = "nothing; the player owes somebody to get in on a job"
        elif face <= 4:
            result = "a job, but something seems off"
        else:
            result = "a choice between two jobs"
        line = f"{where} — d6 → {result}"
        return [
            dice_fact,
            world.player.fact(
                "job_sought",
                line,
                card=line,
                dice=(DiceEvent(label="d6", faces=(6,), rolled=rolled),),
            ),
        ]

    def _take(self, draft: TwentyfourxxGame, terms: str) -> list[Fact]:
        world = draft.payload
        if world.job:
            raise Refusal(f"a job is open: {world.job}")
        world.job = terms
        return [
            world.player.fact("job_taken", f"the job is taken: {terms}", card=f"Job taken\n{terms}")
        ]

    def _finish(self, draft: TwentyfourxxGame, raises: Sequence[Raise], rng: Random) -> list[Fact]:
        world = draft.payload
        if not world.job:
            raise Refusal("no job is open to finish")
        expected = [None, *(member.id for member in world.sheeted_members())]
        got = [raise_.actor_id for raise_ in raises]
        expected_count, got_count = Counter(expected), Counter(got)
        if got_count != expected_count:

            def named(actor_id: EntityId | None) -> str:
                return "the player" if actor_id is None else actor_id

            missing = sorted(named(actor_id) for actor_id in set(expected) - set(got))
            extra = sorted(named(actor_id) for actor_id in set(got) - set(expected))
            repeated = sorted(
                named(actor_id)
                for actor_id, count in got_count.items()
                if count > 1 and actor_id in expected_count
            )
            parts = [
                part
                for part in (
                    f"missing {', '.join(missing)}" if missing else "",
                    f"extra {', '.join(extra)}" if extra else "",
                    f"repeated {', '.join(repeated)}" if repeated else "",
                )
                if part
            ]
            raise Refusal(
                "`job` `finish` names the player and every living hired member once each: "
                + "; ".join(parts)
            )

        facts: list[Fact] = []
        for raise_ in raises:
            actor = world.require_actor(raise_.actor_id)
            sheet = actor.dice()
            label = self.resolve_skill(sheet, raise_.skill)
            new_die = raised(sheet.skills.get(label))
            sheet.skills[label] = new_die
            trace = f"{actor.label} — {label} rises to d{new_die}"
            facts.append(actor.fact("skill_raised", trace, card=f"Job done: {label} d{new_die}"))

            rolled, dice_fact = roll((6,), f"credits earned by {actor.name}", rng)
            gained = rolled[0]
            sheet.credits += gained
            facts.append(dice_fact)
            facts.append(
                actor.fact(
                    "credits_gained",
                    f"{actor.label} earns ₡{gained} -> ₡{sheet.credits}",
                    card=f"+₡{gained} -> ₡{sheet.credits}",
                    dice=(DiceEvent(label="d6", faces=(6,), rolled=rolled),),
                )
            )
        world.job = ""
        return facts


def starting_items(kits: Sequence[Kit]) -> dict[EntityId, Item]:
    taken: list[str] = []
    items: dict[EntityId, Item] = {}
    for kit in kits:
        key = slug(kit.name, taken)
        taken.append(key)
        items[EntityId(key)] = Item(name=kit.name, bulky=kit.bulky, breaks=kit.breaks)
    return items


def _item_lines(items: Mapping[EntityId, Item]) -> str:
    return lines_of(
        f"- {item.name}[{key}]" + (f" — {detail}" if (detail := item.detail()) else "")
        for key, item in items.items()
    )
