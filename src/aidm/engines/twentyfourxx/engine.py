from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import ClassVar, NamedTuple

from aidm.core.creation import (
    CreationStep,
    Picks,
    chosen_option,
    option_of,
    picked,
)
from aidm.core.entities import EngineId, Refusal, Slug, slug
from aidm.core.facts import Fact, roll
from aidm.core.model import AnyCharacter, Generation, WorldsmithAnswer
from aidm.core.play import DecisionOption, PendingDecision, PendingOption
from aidm.core.prompt import Sections, lines_of, section_if, sentence
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import Panel, PanelRow, Rows
from aidm.engines.base import PLAYER_ID
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.seam import Written
from aidm.engines.tools import (
    HIRE,
    HIRE_PENDING,
    HIRE_TOOL,
    HIRE_UNWRITTEN,
    NO_HIRE_TARGET,
    SIGNED_ON,
    SIGNS_ON,
    Hire,
    Kill,
)
from aidm.engines.twentyfourxx.tools import (
    ASK_WORLD,
    CHANGE_HINDRANCES,
    DEFEND,
    DROP_ITEM,
    GAIN_ITEM,
    JOB,
    REPAIR_ITEM,
    ROLL,
    SHIP_UPGRADE,
    SPEND,
    TAKE_LEAD,
    AskWorld,
    ChangeHindrances,
    Defend,
    DropItem,
    GainItem,
    Helper,
    Job,
    Raise,
    RepairItem,
    Roll,
    ShipUpgrade,
    Spend,
    Staked,
    TakeLead,
)
from aidm.engines.twentyfourxx.world import (
    DEFAULT_DIE,
    HELP_DIE,
    HINDERED_DIE,
    SHIP_IDS,
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
from aidm.engines.twentyfourxx.worldsmith import (
    AUTHORING,
    HIRING,
    SKILL_COUNT,
    Origin,
    SheetProposal,
    Specialty,
    TwentyfourxxBody,
    TwentyfourxxHead,
    TwentyfourxxPack,
)


@dataclass(frozen=True, slots=True)
class DicePool:
    faces: tuple[int, ...]
    label: str
    die: int
    helped_by: str


class Helping(NamedTuple):
    who: Crewmate
    terms: Helper


class TwentyfourxxEngine(SceneEngine[Crewmate, TwentyfourxxWorld, TwentyfourxxPack]):
    id = EngineId("twentyfourxx")
    title = "24XX"
    authoring = AUTHORING
    art_style = (
        "Clean science-fiction illustration: hard light, neon on steel, lived-in "
        "technology, no text or lettering."
    )
    directory = Path(__file__).parent
    game = TwentyfourxxGame
    scenario = TwentyfourxxScenario
    character = TwentyfourxxCharacter
    pack = TwentyfourxxPack
    head = TwentyfourxxHead
    body = TwentyfourxxBody
    world = TwentyfourxxWorld
    member = Crewmate
    unwritten: ClassVar[dict[Slug, Fact]] = {**SceneEngine.unwritten, HIRE: HIRE_UNWRITTEN}

    def __init__(self, written: Path) -> None:
        super().__init__(written)
        srd = self.packs.srd()
        if len(srd.skills) != SKILL_COUNT:
            raise ValueError(
                f"the {self.id!r} srd pack lists {len(srd.skills)} skills, not {SKILL_COUNT}"
            )
        if not srd.starting_kit:
            raise ValueError(f"the {self.id!r} srd pack has no starting kit")

    def hire(self, draft: TwentyfourxxGame, args: Hire, _rng: Random) -> list[Fact]:
        member = draft.world.require_hireable(args.target_id)
        draft.generation = Generation(operation=HIRE, detail=args.terms, target=member.id)
        trace = HIRE_PENDING.format(name=member.name, terms=args.terms)
        return [Fact(trace=trace)]

    async def write_hire(
        self, draft: TwentyfourxxGame, request: Generation, worldsmith: WorldsmithAnswer
    ) -> Written:
        if request.target is None:
            raise Refusal(NO_HIRE_TARGET)
        member = draft.world.require_hireable(request.target)
        packs = self.packs.played(draft.pack_id)
        lines = [pack.specialty_lines() for pack in packs]
        lines.append(f"Skills: {', '.join(option.label for option in self.packs.srd().skills)}")
        prompt = self.render_request(
            draft,
            guidance="\n".join(lines),
            intent=HIRING.format(name=member.name, brief=member.brief, terms=request.detail),
            answer=SheetProposal,
        )
        answer = await worldsmith(prompt, SheetProposal, lambda sheet: sheet.check(packs))
        summary = member.sign_on(
            answer.specialty,
            answer.skills,
            items_from_kits(tuple(Kit(name=name) for name in answer.items)),
            answer.hindrances,
        )
        world = draft.world
        facts = world.join(member) if member.id not in world.party else []
        trace = SIGNS_ON.format(who=member.mention, summary=summary)
        card = SIGNS_ON.format(who=member.name, summary=summary)
        facts.append(member.fact(trace, card=card))
        return Written(tuple(facts), SIGNED_ON.format(name=member.name))

    async def advance(
        self, draft: TwentyfourxxGame, request: Generation, worldsmith: WorldsmithAnswer
    ) -> Written:
        if request.operation == HIRE:
            return await self.write_hire(draft, request, worldsmith)
        return await super().advance(draft, request, worldsmith)

    def master_tools(self) -> tuple[MasterTool[TwentyfourxxGame], ...]:
        return (
            *super().master_tools(),
            master_tool("hire", HIRE_TOOL, Hire, self.hire),
            master_tool(
                "change_hindrances", CHANGE_HINDRANCES, ChangeHindrances, self.change_hindrances
            ),
            master_tool("gain_item", GAIN_ITEM, GainItem, self.gain_item),
            master_tool("drop_item", DROP_ITEM, DropItem, self.drop_item),
            master_tool("repair_item", REPAIR_ITEM, RepairItem, self.repair_item),
            master_tool("spend", SPEND, Spend, self.spend),
            master_tool(
                "take_lead", TAKE_LEAD, TakeLead, lambda d, a, _: d.world.take_lead(a.actor_id)
            ),
            master_tool("ship_upgrade", SHIP_UPGRADE, ShipUpgrade, self.ship_upgrade),
            master_tool("defend", DEFEND, Defend, self.defend),
            master_tool("roll", ROLL, Roll, self.roll),
            master_tool("ask_world", ASK_WORLD, AskWorld, self.ask_world),
            master_tool("job", JOB, Job, self.job),
        )

    def creation_steps(self, pack_id: Slug, picks: Picks) -> tuple[CreationStep, ...]:
        specialties, origins = self._offered(pack_id)
        # The rules fix the seventeen skills; a pack adds specialties and origins, not skills.
        skills = self.packs.srd().skills
        steps = [CreationStep(id="specialty", label="Specialty", options=specialties)]
        specialty = option_of(specialties, picked(picks, "specialty"))
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
        steps.append(CreationStep(id="origin", label="Origin", options=origins))
        origin = option_of(origins, picked(picks, "origin"))
        if origin is None:
            return tuple(steps)
        steps.extend(
            CreationStep(id=f"trait-{number}", label=f"Trait {number}", hint=origin.detail)
            for number in range(1, origin.invents + 1)
        )
        if origin.choice:
            steps.append(CreationStep(id="body", label="Body", options=origin.choice))
        steps.extend(
            CreationStep(
                id=f"increase-{number}",
                label="Skill increase",
                options=skills,
                allows_text=True,
            )
            for number in range(1, origin.increases + 1)
        )
        return tuple(steps)

    def build_character(
        self, name: str, brief: str, pack_id: Slug, picks: Picks
    ) -> TwentyfourxxCharacter:
        offered_specialties, offered_origins = self._offered(pack_id)
        specialty = chosen_option(offered_specialties, picked(picks, "specialty"))
        origin = chosen_option(offered_origins, picked(picks, "origin"))

        skills: dict[str, SkillDie] = dict(specialty.skills)
        if specialty.choice:
            picked_skills = chosen_option(specialty.choice, picked(picks, "specialty-choice"))
            skills.update(picked_skills.skills)
        for number in range(1, origin.increases + 1):
            typed = picked(picks, f"increase-{number}")
            option = option_of(self.packs.srd().skills, typed)
            label = (
                option.label if option is not None else self._match_skill(skills, typed) or typed
            )
            skills[label] = raised(skills.get(label))

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

        kits = [*self.packs.srd().starting_kit, *specialty.kit]
        if weapon is not None:
            kits.append(weapon)
        if body is not None and body.kit is not None:
            kits.append(body.kit)
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
        return self.sheet_character(name, player)

    def preview_character(self, character: AnyCharacter) -> Rows:
        sheet = self.player_of(character).require_sheet()
        return (*sheet.rows(), ("Gear", sheet.gear_text()))

    def sheet_sections(self, state: TwentyfourxxGame) -> Sections:
        world = state.world
        job = world.job
        return (
            ("GEAR", _item_lines(world.player.require_sheet().items)),
            *section_if("THE JOB", job),
            ("THE SHIP", _item_lines(world.ship)),
        )

    def panels(self, state: TwentyfourxxGame) -> tuple[Panel, ...]:
        world = state.world
        job = world.job
        job_panel = (Panel(title="Job", rows=(PanelRow(label=job, detail=""),)),) if job else ()
        ship_panel = Panel(
            title="Ship",
            rows=tuple(
                PanelRow(label=function.name, detail=function.notes())
                for function in world.ship.values()
            ),
        )
        return (*job_panel, ship_panel)

    def resolve_skill(self, sheet: CrewSheet, wanted: str) -> str:
        if (match := self._match_skill(sheet.skills, wanted)) is not None:
            return match
        known = ", ".join(sorted(sheet.skills)) or "none"
        listed = ", ".join(option.label for option in self.packs.srd().skills)
        raise Refusal(
            f"{wanted!r} is not a skill on the sheet ({known}) or in the rules ({listed})"
        )

    def _match_skill(self, known: Mapping[str, SkillDie], wanted: str) -> str | None:
        folded = wanted.casefold()
        for key in known:
            if key.casefold() == folded:
                return key
        for option in self.packs.srd().skills:
            if option.label.casefold() == folded:
                return option.label
        return None

    def change_hindrances(
        self, draft: TwentyfourxxGame, args: ChangeHindrances, _rng: Random
    ) -> list[Fact]:
        world = draft.world
        world.check_unnamed(*args.gained)
        return world.require_actor(args.actor_id).change_hindrances(args.gained, args.lost)

    def gain_item(self, draft: TwentyfourxxGame, args: GainItem, _rng: Random) -> list[Fact]:
        world = draft.world
        world.check_unnamed(args.name)
        return world.require_actor(args.actor_id).gain_item(
            args.name, bulky=args.bulky, breaks=args.breaks, cost=args.cost
        )

    def drop_item(self, draft: TwentyfourxxGame, args: DropItem, _rng: Random) -> list[Fact]:
        actor = draft.world.require_actor(args.actor_id)
        return actor.require_sheet().drop_item(args.item_id, actor)

    def repair_item(self, draft: TwentyfourxxGame, args: RepairItem, _rng: Random) -> list[Fact]:
        world = draft.world
        actor = world.require_actor(args.actor_id)
        return actor.repair_item(world.require_gear(actor, args.item_id), args.cost)

    def spend(self, draft: TwentyfourxxGame, args: Spend, _rng: Random) -> list[Fact]:
        world = draft.world
        world.check_unnamed(args.why)
        return world.require_actor(args.actor_id).spend(args.amount, args.why)

    def ship_upgrade(self, draft: TwentyfourxxGame, args: ShipUpgrade, _rng: Random) -> list[Fact]:
        return draft.world.upgrade_ship(args.function_id)

    def defend(self, draft: TwentyfourxxGame, args: Defend, _rng: Random) -> list[Fact]:
        world = draft.world
        world.check_unnamed(args.hindrance)
        return world.defend(args.actor_id, args.item_id, args.hindrance)

    def kill(self, draft: TwentyfourxxGame, args: Kill, rng: Random) -> list[Fact]:
        facts = super().kill(draft, args, rng)
        self._succession(draft)
        return facts

    def _offered(self, pack_id: Slug) -> tuple[tuple[Specialty, ...], tuple[Origin, ...]]:
        played = self.packs.played(pack_id)
        return (
            tuple(option for pack in played for option in pack.specialties),
            tuple(option for pack in played for option in pack.origins),
        )

    def _succession(self, draft: TwentyfourxxGame) -> None:
        """`kill` and `roll` are the two tools that can kill the lead."""
        world = draft.world
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
                    args={"actor_id": member.id},
                )
                for member in members
            ),
            allows_text=False,
        )

    def over(self, state: TwentyfourxxGame) -> str | None:
        """A dead lead with a hired member alive is a succession, not an ending."""
        return None if state.world.sheeted_members() else super().over(state)

    def roll(self, draft: TwentyfourxxGame, args: Roll, rng: Random) -> list[Fact]:
        world = draft.world
        actor = world.require_actor(args.actor_id)
        helper = args.helped_by
        world.check_unnamed(
            args.what,
            args.helped,
            args.hindered,
            args.risk,
            args.hindrance,
            *(() if helper is None else (helper.hindered, helper.risk, helper.hindrance)),
        )
        helping = None if helper is None else Helping(world.require_actor(helper.actor_id), helper)
        pool = self._pool(actor, helping, args)

        staked: list[tuple[Crewmate, Staked]] = [(actor, args)]
        if helping is not None:
            staked.append(helping)

        claims: list[tuple[Crewmate, Slug, str]] = [
            (who, terms.defend_with_id, terms.hindrance)
            for who, terms in staked
            if terms.defend_with_id is not None
        ]
        world.check_defenses(claims)

        label = "+".join(f"d{face}" for face in pool.faces)
        rolled = roll(
            pool.faces, f"{args.what} — {pool.label}", rng, label=label, highlight_kept=True
        )
        result = _banded(rolled.kept, "disaster", "setback", "success")

        line = f"{args.what} — {actor.card_line(sentence(pool.label))} d{pool.die}"
        if args.helped:
            line += f", helped ({args.helped})"
        line += pool.helped_by
        if args.hindered:
            line += f", hindered ({args.hindered})"
        if helping is not None and helping.terms.risk:
            terms = helping.terms
            line += f", {helping.who.name} risking {_staked(terms.risk, deadly=terms.deadly)}"
        if args.risk:
            line += f", risking {_staked(args.risk, deadly=args.deadly)}"
        line += f" → {result}"

        facts = [rolled.fact, actor.fact(line, card=line, dice=(rolled.event,))]
        if result != "success":
            disaster = result == "disaster"
            # Hits land helper-first, the reverse of the actor-first claims above.
            for who, stake in reversed(staked):
                if not stake.risk:
                    continue
                facts.extend(
                    world.take_hit(
                        who,
                        stake.defend_with_id,
                        stake.risk,
                        stake.hindrance,
                        disaster=disaster,
                        deadly=stake.deadly,
                    )
                )
        self._succession(draft)
        return facts

    def _pool(self, actor: Crewmate, helping: Helping | None, args: Roll) -> DicePool:
        sheet = actor.require_sheet()
        if helping is not None and helping.who is actor:
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
        if helping is not None:
            who, terms = helping
            if terms.hindered:
                helper_die = HINDERED_DIE
                hindered_note = f", hindered ({terms.hindered})"
            else:
                helper_die = who.require_sheet().die(label)
                hindered_note = ""
            faces.append(helper_die)
            helped_by = f", helped by {who.name} (d{helper_die}{hindered_note})"

        return DicePool(faces=tuple(faces), label=label, die=die, helped_by=helped_by)

    def ask_world(self, _draft: TwentyfourxxGame, args: AskWorld, rng: Random) -> list[Fact]:
        rolled = roll((6,), args.question, rng)
        result = _banded(rolled.face, "trouble now", "signs of it", "nothing")
        # The dice trace; the answer itself is never told.
        return [rolled.fact, Fact(trace=f"{args.question} — d6 [{rolled.face}] → {result}")]

    def job(self, draft: TwentyfourxxGame, args: Job, rng: Random) -> list[Fact]:
        match args.verb:
            case "find":
                return self._find(draft, args.where, rng)
            case "take":
                world = draft.world
                world.check_unnamed(args.terms)
                return world.take_job(args.terms)
            case "finish":
                return self._finish(draft, args.raises, rng)

    def _find(self, draft: TwentyfourxxGame, where: str, rng: Random) -> list[Fact]:
        world = draft.world
        world.check_unnamed(where)
        if world.job:
            raise Refusal(f"a job is open: {world.job}")
        rolled = roll((6,), where, rng)
        face = rolled.face
        result = _banded(
            face,
            "nothing; the player owes somebody to get in on a job",
            "a job, but something seems off",
            "a choice between two jobs",
        )
        line = f"{where} — d6 → {result}"
        return [rolled.fact, world.player.fact(line, card=line, dice=(rolled.event,))]

    def _finish(self, draft: TwentyfourxxGame, raises: Sequence[Raise], rng: Random) -> list[Fact]:
        world = draft.world
        if not world.job:
            raise Refusal("no job is open to finish")
        world.check_unnamed(*(raise_.skill for raise_ in raises))
        expected = sorted((world.player.id, *(member.id for member in world.sheeted_members())))
        given = sorted(world.require_actor(raise_.actor_id).id for raise_ in raises)
        if given != expected:
            raise Refusal(
                "`job` `finish` names the player and every living hired member once each: "
                f"expected {', '.join(expected)}; given {', '.join(given) or '(nobody)'}"
            )

        facts: list[Fact] = []
        for raise_ in raises:
            actor = world.require_actor(raise_.actor_id)
            sheet = actor.require_sheet()
            skill = self._match_skill(sheet.skills, raise_.skill) or raise_.skill
            facts.extend(actor.raise_skill(skill))

            rolled = roll((6,), f"credits earned by {actor.name}", rng)
            facts.append(rolled.fact)
            facts.extend(actor.earn(rolled.face, rolled.event))
        world.close_job()
        return facts


def items_from_kits(kits: Sequence[Kit]) -> dict[Slug, Gear]:
    taken: list[str] = list(SHIP_IDS)
    items: dict[Slug, Gear] = {}
    for kit in kits:
        key = slug(kit.name, taken)
        taken.append(key)
        items[key] = Gear(**kit.model_dump())
    return items


def _item_lines(items: Mapping[Slug, Gear]) -> str:
    return lines_of(
        f"- {item.name}[{key}]" + (f" — {detail}" if (detail := item.notes()) else "")
        for key, item in items.items()
    )


def _staked(risk: str, *, deadly: bool) -> str:
    return f"{risk} (deadly)" if deadly else risk


def _banded(face: int, low: str, mid: str, high: str) -> str:
    return low if face <= 2 else mid if face <= 4 else high
