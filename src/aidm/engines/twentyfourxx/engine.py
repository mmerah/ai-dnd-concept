from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, chosen_option, option_of, picked
from aidm.core.entities import EngineId, Refusal, Slug, slug
from aidm.core.facts import DiceEvent, Fact, keep_highest, roll
from aidm.core.model import Objection
from aidm.core.play import DecisionOption, PendingDecision, PendingOption
from aidm.core.prompt import lines_of
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import DiceLook, Pairs, Panel, PanelRow
from aidm.engines.base import PLAYER_ID, banded
from aidm.engines.hiring import DROP_ITEM, HIRE, HIRE_UNWRITTEN, DropItem, Hiring
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.tools import Kill
from aidm.engines.scenes.world import sentence
from aidm.engines.twentyfourxx.tools import (
    CHANGE_HINDRANCES,
    DEFEND,
    GAIN_ITEM,
    REPAIR_ITEM,
    SHIP_UPGRADE,
    SPEND,
    TAKE_LEAD,
    ChangeHindrances,
    Defend,
    GainItem,
    Job,
    Raise,
    RepairItem,
    Roll,
    ShipUpgrade,
    Spend,
    TakeLead,
    TestLuck,
)
from aidm.engines.twentyfourxx.world import (
    DEFAULT_DIE,
    HELP_DIE,
    HINDERED_DIE,
    MAIMED,
    Crewmate,
    Gear,
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


class TwentyfourxxEngine(
    Hiring[Crewmate, Crewmate, TwentyfourxxGame, SheetDraft],
    SceneEngine[Crewmate, TwentyfourxxGame, Pack],
):
    id = EngineId("twentyfourxx")
    title = "24XX"
    art_style = (
        "Clean science-fiction illustration: hard light, neon on steel, lived-in "
        "technology, no text or lettering."
    )
    dice_look = DiceLook(body="#101418", ink="#5ee1ff", glow="#5ee1ff")
    palette = {
        "game-bg": "#0f1624",
        "game-surface": "#182236",
        "game-surface-raised": "#22314b",
        "game-text": "#e3edf9",
        "game-muted": "#afc0da",
        "game-border": "#354968",
        "game-accent": "#91c8ff",
        "game-wash": "rgba(145, 200, 255, .08)",
        "game-radius": "10px",
        "game-heading": "'SFMono-Regular', Consolas, 'Liberation Mono', monospace",
    }
    directory = Path(__file__).parent
    game = TwentyfourxxGame
    scenario = TwentyfourxxScenario
    character = TwentyfourxxCharacter
    cast = Crewmate
    pack = Pack
    world_type = TwentyfourxxWorld
    hire_answer = SheetDraft
    unwritten = {**SceneEngine.unwritten, HIRE: HIRE_UNWRITTEN}

    def master_tools(self) -> tuple[MasterTool[TwentyfourxxGame], ...]:
        return (
            *super().master_tools(),
            master_tool(
                "change_hindrances", CHANGE_HINDRANCES, ChangeHindrances, self.change_hindrances
            ),
            master_tool("gain_item", GAIN_ITEM, GainItem, self.gain_item),
            master_tool("drop_item", DROP_ITEM, DropItem, self.drop_item),
            master_tool("repair_item", REPAIR_ITEM, RepairItem, self.repair_item),
            master_tool("spend", SPEND, Spend, self.spend),
            master_tool("take_lead", TAKE_LEAD, TakeLead, self.take_lead),
            master_tool("ship_upgrade", SHIP_UPGRADE, ShipUpgrade, self.ship_upgrade),
            master_tool("defend", DEFEND, Defend, self.defend),
            master_tool(
                "roll",
                "Call this when the outcome of an action matters. The engine picks the dice, "
                "rolls them, and reads the result.",
                Roll,
                self.roll,
            ),
            master_tool(
                "test_luck",
                "Call this to ask about the world's bad luck when nobody acts. The engine "
                "rolls one d6 and reads it.",
                TestLuck,
                self.test_luck,
            ),
            master_tool(
                "job",
                "Call this to look for work with `find`, to record agreed work with `take`, "
                "and to close the job with `finish`. With `find` the engine rolls the SRD's "
                "d6. With `finish` it raises one skill for each operator and pays each of "
                "them d6 credits.",
                Job,
                self.job,
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
                items=items_from_kits(kits),
            ),
        )
        return TwentyfourxxCharacter(id=slug(name, ()), engine=self.id, payload=player)

    def guidance(self, _picks: Sequence[Slug]) -> str:
        """This pack holds creation tables, not setting vocabulary: the preamble alone suffices."""
        return AUTHORING

    def sheet_sections(self, state: TwentyfourxxGame) -> Pairs:
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

    def change_hindrances(
        self, draft: TwentyfourxxGame, args: ChangeHindrances, _rng: Random
    ) -> list[Fact]:
        return draft.payload.require_actor(args.actor_id).change_hindrances(args.gained, args.lost)

    def gain_item(self, draft: TwentyfourxxGame, args: GainItem, _rng: Random) -> list[Fact]:
        return draft.payload.require_actor(args.actor_id).gain_item(
            args.name, bulky=args.bulky, breaks=args.breaks, cost=args.cost
        )

    def drop_item(self, draft: TwentyfourxxGame, args: DropItem, _rng: Random) -> list[Fact]:
        return draft.payload.require_actor(args.actor_id).drop_item(args.item_id)

    def repair_item(self, draft: TwentyfourxxGame, args: RepairItem, _rng: Random) -> list[Fact]:
        world = draft.payload
        actor = world.require_actor(args.actor_id)
        return actor.repair_item(world.require_gear(actor, args.item_id), args.cost)

    def spend(self, draft: TwentyfourxxGame, args: Spend, _rng: Random) -> list[Fact]:
        return draft.payload.require_actor(args.actor_id).spend(args.amount, args.why)

    def take_lead(self, draft: TwentyfourxxGame, args: TakeLead, _rng: Random) -> list[Fact]:
        return draft.payload.take_lead(args.entity_id)

    def ship_upgrade(self, draft: TwentyfourxxGame, args: ShipUpgrade, _rng: Random) -> list[Fact]:
        return draft.payload.upgrade_ship(args.function_id)

    def defend(self, draft: TwentyfourxxGame, args: Defend, _rng: Random) -> list[Fact]:
        return draft.payload.defend(args.actor_id, args.item_id, args.hindrance)

    def kill(self, draft: TwentyfourxxGame, args: Kill, _rng: Random) -> list[Fact]:
        facts = super().kill(draft, args, _rng)
        self._succession(draft)
        return facts

    def _succession(self, draft: TwentyfourxxGame) -> None:
        """`kill` and `roll` are the two tools that can kill the lead."""
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
                    name="take_lead",
                    args={"entity_id": member.id},
                )
                for member in members
            ),
            allows_text=False,
        )

    def over(self, state: TwentyfourxxGame) -> str | None:
        """A dead lead with a hired member alive is a succession, not an ending."""
        return None if state.payload.sheeted_members() else super().over(state)

    def hireable(self, draft: TwentyfourxxGame, entity_id: Slug) -> Crewmate:
        return draft.payload.require_hireable(entity_id)

    def hire_prompt(self, draft: TwentyfourxxGame, member: Crewmate, terms: str) -> str:
        return self.render_request(
            draft,
            guidance=self._pack(draft).hire_guidance(),
            intent=HIRING.format(name=member.name, brief=member.brief, terms=terms),
            answer=SheetDraft,
        )

    def hire_bar(self, draft: TwentyfourxxGame) -> Objection[SheetDraft]:
        pack = self._pack(draft)
        return lambda sheet: sheet.refusal(pack)

    def install_sheet(self, member: Crewmate, answer: SheetDraft) -> str:
        member.sheet = Sheet(
            specialty=answer.specialty,
            skills=dict(answer.skills),
            credits=0,
            items=items_from_kits(tuple(Kit(name=name) for name in answer.items)),
            hindrances=list(answer.hindrances),
        )
        return answer.specialty

    def _pack(self, draft: TwentyfourxxGame) -> Pack:
        return self.packs[draft.packs[0]]

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

        result = banded(face, "disaster", "setback", "success")
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

        facts: list[Fact] = [dice_fact, actor.fact(line, card=line, dice=(event,))]

        if args.risking_death and result == "disaster":
            facts.extend(world.kill(actor.id))
        elif args.risking_death and result == "setback" and MAIMED not in sheet.hindrances:
            sheet.hindrances.append(MAIMED)
            trace = f"{actor.mention} is maimed"
            facts.append(actor.fact(trace, card="Maimed"))
        self._succession(draft)

        return facts

    def test_luck(self, _draft: TwentyfourxxGame, args: TestLuck, rng: Random) -> list[Fact]:
        rolled, dice_fact = roll((6,), args.question, rng)
        face = rolled[0]
        result = banded(face, "trouble now", "signs of it", "nothing")
        trace = f"{args.question} — d6 [{face}] -> {result}"
        return [dice_fact, Fact(trace=trace)]

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
        result = banded(
            face,
            "nothing; the player owes somebody to get in on a job",
            "a job, but something seems off",
            "a choice between two jobs",
        )
        line = f"{where} — d6 → {result}"
        return [
            dice_fact,
            world.player.fact(
                line, card=line, dice=(DiceEvent(label="d6", faces=(6,), rolled=rolled),)
            ),
        ]

    def _take(self, draft: TwentyfourxxGame, terms: str) -> list[Fact]:
        world = draft.payload
        if world.job:
            raise Refusal(f"a job is open: {world.job}")
        world.job = terms
        return [world.player.fact(f"the job is taken: {terms}", card=f"Job taken\n{terms}")]

    def _finish(self, draft: TwentyfourxxGame, raises: Sequence[Raise], rng: Random) -> list[Fact]:
        world = draft.payload
        if not world.job:
            raise Refusal("no job is open to finish")
        expected = [None, *(member.id for member in world.sheeted_members())]
        got = [raise_.actor_id for raise_ in raises]
        expected_count, got_count = Counter(expected), Counter(got)
        if got_count != expected_count:

            def named(actor_id: Slug | None) -> str:
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
            try:
                new_die = raised(sheet.skills.get(label))
            except Refusal as maxed:
                raise Refusal(
                    f"{actor.name}'s {label} is already at d12; raise another skill for them"
                ) from maxed
            sheet.skills[label] = new_die
            trace = f"{actor.mention} — {label} rises to d{new_die}"
            facts.append(actor.fact(trace, card=f"Job done: {label} d{new_die}"))

            rolled, dice_fact = roll((6,), f"credits earned by {actor.name}", rng)
            gained = rolled[0]
            sheet.credits += gained
            facts.append(dice_fact)
            facts.append(
                actor.fact(
                    f"{actor.mention} earns ₡{gained} -> ₡{sheet.credits}",
                    card=f"+₡{gained} -> ₡{sheet.credits}",
                    dice=(DiceEvent(label="d6", faces=(6,), rolled=rolled),),
                )
            )
        world.job = ""
        return facts


def items_from_kits(kits: Sequence[Kit]) -> dict[Slug, Gear]:
    taken: list[str] = []
    items: dict[Slug, Gear] = {}
    for kit in kits:
        key = slug(kit.name, taken)
        taken.append(key)
        items[key] = Gear(name=kit.name, bulky=kit.bulky, breaks=kit.breaks, harmless=kit.harmless)
    return items


def _item_lines(items: Mapping[Slug, Gear]) -> str:
    return lines_of(
        f"- {item.name}[{key}]" + (f" — {detail}" if (detail := item.detail()) else "")
        for key, item in items.items()
    )
