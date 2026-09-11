from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, chosen_option, option_of, picked
from aidm.core.entities import EngineId, Refusal, Slug, slug
from aidm.core.facts import Fact, roll, roll_pool
from aidm.core.model import AnyCharacter, Check
from aidm.core.play import DecisionOption, PendingDecision, PendingOption
from aidm.core.prompt import Pairs, lines_of, sentence
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import DiceLook, Look, Panel, PanelRow
from aidm.engines.base import PLAYER_ID, Kill, banded, luck_test
from aidm.engines.hiring import DROP_ITEM, DropItem, Hiring, hiring
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.twentyfourxx.tools import (
    CHANGE_HINDRANCES,
    DEFEND,
    GAIN_ITEM,
    JOB,
    REPAIR_ITEM,
    ROLL,
    SHIP_UPGRADE,
    SPEND,
    TAKE_LEAD,
    TEST_LUCK,
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
    Crewmate,
    CrewSheet,
    Gear,
    Kit,
    SkillDie,
    TwentyfourxxCharacter,
    TwentyfourxxGame,
    TwentyfourxxScenario,
    TwentyfourxxWorld,
    raised,
)
from aidm.engines.twentyfourxx.worldsmith import AUTHORING, HIRING, Pack, SheetDraft


@dataclass(frozen=True, slots=True)
class Pool:
    faces: tuple[int, ...]
    label: str
    die: int
    helped_by: str


class TwentyfourxxEngine(SceneEngine[Crewmate, TwentyfourxxGame, Pack]):
    id = EngineId("twentyfourxx")
    title = "24XX"
    art_style = (
        "Clean science-fiction illustration: hard light, neon on steel, lived-in "
        "technology, no text or lettering."
    )
    look = Look(
        palette={
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
        },
        dice=DiceLook(body="#101418", ink="#5ee1ff", glow="#5ee1ff"),
    )
    directory = Path(__file__).parent
    game = TwentyfourxxGame
    scenario = TwentyfourxxScenario
    character = TwentyfourxxCharacter
    pack = Pack
    world = TwentyfourxxWorld
    member = Crewmate

    def world_of(self, state: TwentyfourxxGame) -> TwentyfourxxWorld:
        return state.payload

    def hiring(self) -> Hiring[TwentyfourxxGame, Crewmate]:
        return hiring(SheetDraft, self.hire_prompt, self.install_sheet, self.hire_check)

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
            master_tool("roll", ROLL, Roll, self.roll),
            master_tool("test_luck", TEST_LUCK, TestLuck, self.test_luck),
            master_tool("job", JOB, Job, self.job),
        )

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        first = self.pack_step()
        pack = self.packs.get(picked(picks, "pack"))
        if pack is None:
            return (first,)
        steps = [
            first,
            CreationStep(id="specialty", label="Specialty", options=pack.specialties),
        ]
        specialty = option_of(pack.specialties, picked(picks, "specialty"))
        if specialty is None:
            return tuple(steps)
        if specialty.choice:
            steps.append(
                CreationStep(
                    id="specialty-choice", label="Specialty skill", options=specialty.choice
                )
            )
        if specialty.kit_choice:
            steps.append(
                CreationStep(
                    id="weapon",
                    label="Weapon",
                    options=tuple(
                        DecisionOption(id=slug(kit.name, ()), label=kit.name)
                        for kit in specialty.kit_choice
                    ),
                )
            )
        steps.append(CreationStep(id="origin", label="Origin", options=pack.origins))
        origin = option_of(pack.origins, picked(picks, "origin"))
        if origin is None:
            return tuple(steps)
        for number in range(1, origin.invents + 1):
            steps.append(
                CreationStep(id=f"trait-{number}", label=f"Trait {number}", hint=origin.detail)
            )
        if origin.choice:
            steps.append(CreationStep(id="body", label="Body", options=origin.choice))
        for number in range(1, origin.increases + 1):
            steps.append(
                CreationStep(id=f"increase-{number}", label="Skill increase", options=pack.skills)
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
            sheet=CrewSheet(
                specialty=specialty.label,
                origin=origin.label,
                traits=traits,
                skills=skills,
                items=items_from_kits(kits),
            ),
        )
        return TwentyfourxxCharacter(id=slug(name, ()), engine=self.id, payload=player)

    def preview_character(self, character: AnyCharacter) -> Pairs:
        sheet = self.player_of(character).require_sheet()
        return (*sheet.rows(), ("Gear", ", ".join(item.name for item in sheet.items.values())))

    def guidance(self, _picks: Sequence[Slug]) -> str:
        """This pack holds creation tables, not setting vocabulary: the preamble alone suffices."""
        return AUTHORING

    def sheet_sections(self, state: TwentyfourxxGame) -> Pairs:
        world = self.world_of(state)
        job = world.job
        return (
            ("GEAR", _item_lines(world.player.require_sheet().items)),
            *((("THE JOB", job),) if job else ()),
            ("THE SHIP", _item_lines(world.ship)),
        )

    def panels(self, state: TwentyfourxxGame) -> tuple[Panel, ...]:
        world = self.world_of(state)
        job = world.job
        gear_panel = Panel(
            title="Gear",
            rows=tuple(
                PanelRow(label=item.name, detail=item.notes())
                for item in world.player.require_sheet().items.values()
            ),
        )
        job_panel = (Panel(title="Job", rows=(PanelRow(label=job, detail=""),)),) if job else ()
        ship_panel = Panel(
            title="Ship",
            rows=tuple(
                PanelRow(label=function.name, detail=function.notes())
                for function in world.ship.values()
            ),
        )
        return (gear_panel, *job_panel, ship_panel)

    def resolve_skill(self, sheet: CrewSheet, wanted: str) -> str:
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
        return (
            self.world_of(draft)
            .require_actor(args.actor_id)
            .change_hindrances(args.gained, args.lost)
        )

    def gain_item(self, draft: TwentyfourxxGame, args: GainItem, _rng: Random) -> list[Fact]:
        return (
            self.world_of(draft)
            .require_actor(args.actor_id)
            .gain_item(args.name, bulky=args.bulky, breaks=args.breaks, cost=args.cost)
        )

    def repair_item(self, draft: TwentyfourxxGame, args: RepairItem, _rng: Random) -> list[Fact]:
        world = self.world_of(draft)
        actor = world.require_actor(args.actor_id)
        return actor.repair_item(world.require_gear(actor, args.item_id), args.cost)

    def spend(self, draft: TwentyfourxxGame, args: Spend, _rng: Random) -> list[Fact]:
        return self.world_of(draft).require_actor(args.actor_id).spend(args.amount, args.why)

    def take_lead(self, draft: TwentyfourxxGame, args: TakeLead, _rng: Random) -> list[Fact]:
        return self.world_of(draft).take_lead(args.entity_id)

    def ship_upgrade(self, draft: TwentyfourxxGame, args: ShipUpgrade, _rng: Random) -> list[Fact]:
        return self.world_of(draft).upgrade_ship(args.function_id)

    def defend(self, draft: TwentyfourxxGame, args: Defend, _rng: Random) -> list[Fact]:
        return self.world_of(draft).defend(args.actor_id, args.item_id, args.hindrance)

    def kill(self, draft: TwentyfourxxGame, args: Kill, rng: Random) -> list[Fact]:
        facts = super().kill(draft, args, rng)
        self._succession(draft)
        return facts

    def _succession(self, draft: TwentyfourxxGame) -> None:
        """`kill` and `roll` are the two tools that can kill the lead."""
        world = self.world_of(draft)
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
        return None if self.world_of(state).sheeted_members() else super().over(state)

    def hire_prompt(self, draft: TwentyfourxxGame, member: Crewmate, terms: str) -> str:
        return self.render_request(
            draft,
            guidance=self.first_pack(draft).hire_guidance(),
            intent=HIRING.format(name=member.name, brief=member.brief, terms=terms),
            answer=SheetDraft,
        )

    def hire_check(self, draft: TwentyfourxxGame) -> Check[SheetDraft]:
        pack = self.first_pack(draft)
        return lambda sheet: sheet.check(pack)

    def install_sheet(self, member: Crewmate, answer: SheetDraft) -> str:
        member.take_sheet(
            CrewSheet(
                specialty=answer.specialty,
                skills=dict(answer.skills),
                credits=0,
                items=items_from_kits(tuple(Kit(name=name) for name in answer.items)),
                hindrances=list(answer.hindrances),
            )
        )
        return answer.specialty

    def roll(self, draft: TwentyfourxxGame, args: Roll, rng: Random) -> list[Fact]:
        world = self.world_of(draft)
        actor = world.require_actor(args.actor_id)
        pool = self._pool(world, actor, args)
        rolled = roll_pool(
            pool.faces,
            f"{args.what} — {pool.label}",
            rng,
            label="+".join(f"d{face}" for face in pool.faces),
        )
        result = banded(rolled.kept, "disaster", "setback", "success")
        line = _line(world, actor, args, pool, result)
        facts: list[Fact] = [rolled.fact, actor.fact(line, card=line, dice=(rolled.event,))]
        facts.extend(_consequence(world, actor, args, result))
        self._succession(draft)
        return facts

    def _pool(self, world: TwentyfourxxWorld, actor: Crewmate, args: Roll) -> Pool:
        sheet = actor.require_sheet()
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

        faces = [die]
        if args.helped:
            faces.append(HELP_DIE)
        helped_by = ""
        if helper is not None:
            helper_die = helper.require_sheet().die(label)
            faces.append(helper_die)
            helped_by = f", helped by {helper.name} (d{helper_die})"

        return Pool(faces=tuple(faces), label=label, die=die, helped_by=helped_by)

    def test_luck(self, _draft: TwentyfourxxGame, args: TestLuck, rng: Random) -> list[Fact]:
        return luck_test(args.question, 6, ("trouble now", "signs of it", "nothing"), rng)

    def job(self, draft: TwentyfourxxGame, args: Job, rng: Random) -> list[Fact]:
        match args.verb:
            case "find":
                return self._find(draft, args.where, rng)
            case "take":
                return self._take(draft, args.terms)
            case "finish":
                return self._finish(draft, args.raises, rng)

    def _find(self, draft: TwentyfourxxGame, where: str, rng: Random) -> list[Fact]:
        world = self.world_of(draft)
        if world.job:
            raise Refusal(f"a job is open: {world.job}")
        rolled = roll((6,), where, rng)
        face = rolled.rolled[0]
        result = banded(
            face,
            "nothing; the player owes somebody to get in on a job",
            "a job, but something seems off",
            "a choice between two jobs",
        )
        line = f"{where} — d6 → {result}"
        return [
            rolled.fact,
            world.player.fact(line, card=line, dice=(rolled.event,)),
        ]

    def _take(self, draft: TwentyfourxxGame, terms: str) -> list[Fact]:
        return self.world_of(draft).take_job(terms)

    def _finish(self, draft: TwentyfourxxGame, raises: Sequence[Raise], rng: Random) -> list[Fact]:
        world = self.world_of(draft)
        if not world.job:
            raise Refusal("no job is open to finish")
        expected = [None, *(member.id for member in world.sheeted_members())]
        got = [raise_.actor_id for raise_ in raises]
        if unmet := _operators_unmet(expected, got):
            raise Refusal(unmet)

        facts: list[Fact] = []
        for raise_ in raises:
            actor = world.require_actor(raise_.actor_id)
            sheet = actor.require_sheet()
            facts.extend(actor.raise_skill(self.resolve_skill(sheet, raise_.skill)))

            rolled = roll((6,), f"credits earned by {actor.name}", rng)
            facts.append(rolled.fact)
            facts.extend(actor.earn(rolled.rolled[0], rolled.event))
        world.close_job()
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
        f"- {item.name}[{key}]" + (f" — {detail}" if (detail := item.notes()) else "")
        for key, item in items.items()
    )


def _line(world: TwentyfourxxWorld, actor: Crewmate, args: Roll, pool: Pool, result: str) -> str:
    line = (
        f"{args.what} — {sentence(pool.label)} d{pool.die}"
        if actor is world.player
        else f"{args.what} — {actor.name}: {sentence(pool.label)} d{pool.die}"
    )
    if args.helped:
        line += f", helped ({args.helped})"
    line += pool.helped_by
    if args.hindered:
        line += f", hindered ({args.hindered})"
    line += f" → {result}"
    return line


def _consequence(world: TwentyfourxxWorld, actor: Crewmate, args: Roll, result: str) -> list[Fact]:
    if not args.risking_death:
        return []
    if result == "disaster":
        return world.kill(actor.id)
    return actor.maim() if result == "setback" else []


def _operators_unmet(expected: Sequence[Slug | None], got: Sequence[Slug | None]) -> str:
    """The `job` `finish` refusal, or `""` when every operator is named once."""
    expected_count, got_count = Counter(expected), Counter(got)
    if got_count == expected_count:
        return ""

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
    return "`job` `finish` names the player and every living hired member once each: " + "; ".join(
        parts
    )
