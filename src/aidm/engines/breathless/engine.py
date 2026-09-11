from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, other_than, picked
from aidm.core.entities import EngineId, Refusal, Slug, parse, slug
from aidm.core.facts import Fact, roll, roll_pool
from aidm.core.model import AnyCharacter
from aidm.core.play import PendingDecision, PendingOption
from aidm.core.prompt import Pairs, lines_of, sentence
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import DiceLook, Look, Panel, PanelRow
from aidm.engines.base import PLAYER_ID, banded, luck_test
from aidm.engines.breathless.tools import (
    CATCH_BREATH,
    CHANGE_STRESS,
    LOOT_CHECK,
    ROLL,
    TEST_LUCK,
    USE_MED_KIT,
    Actor,
    ChangeStress,
    LootCheck,
    Roll,
    TakeLoot,
    TestLuck,
    UseMedKit,
)
from aidm.engines.breathless.world import (
    LADDER,
    SKILLS,
    STARTING_DICE,
    STARTING_ITEM,
    STUNT_DIE,
    TAKE_LOOT,
    BreathlessCharacter,
    BreathlessGame,
    BreathlessScenario,
    BreathlessWorld,
    Die,
    Skill,
    Supply,
    Survivor,
    SurvivorSheet,
)
from aidm.engines.breathless.worldsmith import AUTHORING, HIRING, Pack, SheetDraft
from aidm.engines.hiring import DROP_ITEM, DropItem, Hiring, hiring
from aidm.engines.scenes.engine import SceneEngine


@dataclass(frozen=True, slots=True)
class Pool:
    die: Die
    label: str
    helper: tuple[Survivor, Die] | None


class BreathlessEngine(SceneEngine[Survivor, BreathlessGame, Pack]):
    id = EngineId("breathless")
    title = "BREATHLESS"
    art_style = (
        "Grim survival-horror illustration: dim, desaturated, wet surfaces, no text or lettering."
    )
    look = Look(
        palette={
            "game-bg": "#0d1818",
            "game-surface": "#162525",
            "game-surface-raised": "#203332",
            "game-text": "#e0eeea",
            "game-muted": "#a8c1bb",
            "game-border": "#35504b",
            "game-accent": "#94d5be",
            "game-wash": "rgba(148, 213, 190, .07)",
            "game-radius": "5px",
            "game-heading": "'Arial Narrow', 'Helvetica Neue', Arial, sans-serif",
        },
        dice=DiceLook(body="#5a1216", ink="#efe1d3", glow="#e0393e"),
    )
    directory = Path(__file__).parent
    game = BreathlessGame
    scenario = BreathlessScenario
    character = BreathlessCharacter
    pack = Pack
    world = BreathlessWorld
    member = Survivor

    def hiring(self) -> Hiring[BreathlessGame, Survivor]:
        return hiring(SheetDraft, self.hire_prompt, self.install_sheet)

    def master_tools(self) -> tuple[MasterTool[BreathlessGame], ...]:
        return (
            *super().master_tools(),
            master_tool("drop_item", DROP_ITEM, DropItem, self.drop_item),
            master_tool("change_stress", CHANGE_STRESS, ChangeStress, self.change_stress),
            master_tool("use_med_kit", USE_MED_KIT, UseMedKit, self.use_med_kit),
            master_tool("roll", ROLL, Roll, self.roll),
            master_tool("catch_breath", CATCH_BREATH, Actor, self.catch_breath),
            master_tool("loot_check", LOOT_CHECK, LootCheck, self.loot_check),
            master_tool("test_luck", TEST_LUCK, TestLuck, self.test_luck),
        )

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        first = self.pack_step()
        pack = self.packs.get(picked(picks, "pack"))
        if pack is None:
            return (first,)
        d10 = picked(picks, "skill-d10")
        d8 = picked(picks, "skill-d8")
        return (
            first,
            CreationStep(id="pronouns", label="Pronouns"),
            CreationStep(id="job", label="Job", hint=", ".join(pack.jobs[:3])),
            CreationStep(id="skill-d10", label="Skill at d10", options=pack.skills),
            CreationStep(id="skill-d8", label="Skill at d8", options=other_than(pack.skills, d10)),
            CreationStep(
                id="skill-d6",
                label="Skill at d6",
                options=other_than(other_than(pack.skills, d10), d8),
            ),
            CreationStep(id="item", label="Your one item", hint=", ".join(pack.weapons[:3])),
        )

    def create_character(self, name: str, brief: str, picks: Picks) -> BreathlessCharacter:
        check_picks(self.creation_steps(picks), picks)
        skills: dict[Skill, Die] = dict.fromkeys(SKILLS, 4)
        skills.update({_skill(picked(picks, f"skill-d{die}")): die for die in STARTING_DICE})
        item = picked(picks, "item")
        player = Survivor(
            id=PLAYER_ID,
            name=name,
            brief=brief,
            known=True,
            sheet=SurvivorSheet(
                pronouns=picked(picks, "pronouns"),
                job=picked(picks, "job"),
                skills=skills,
                worn=dict(skills),
                items={slug(item, ()): Supply(name=item, die=STARTING_ITEM)},
            ),
        )
        return BreathlessCharacter(id=slug(name, ()), engine=self.id, payload=player)

    def preview_character(self, character: AnyCharacter) -> Pairs:
        sheet = self.player_of(character).require_sheet()
        return (*sheet.rows(), ("Backpack", ", ".join(item.name for item in sheet.items.values())))

    def guidance(self, picks: Sequence[Slug]) -> str:
        include = {"locations", "complications", "missions"}
        return f"{AUTHORING}\n\n{self.pack_content(picks, include=include)}"

    def sheet_sections(self, state: BreathlessGame) -> Pairs:
        sheet = self.world_of(state).player.require_sheet()
        lines = [f"- {item.name}[{key}] — d{item.die}" for key, item in sheet.items.items()]
        if sheet.med_kit:
            lines.append("- med kit")
        return (("BACKPACK", lines_of(lines)),)

    def panels(self, state: BreathlessGame) -> tuple[Panel, ...]:
        sheet = self.world_of(state).player.require_sheet()
        rows = [PanelRow(label=item.name, detail=f"d{item.die}") for item in sheet.items.values()]
        if sheet.med_kit:
            rows.append(PanelRow(label="Med kit", detail="held"))
        return (Panel(title="Backpack", rows=tuple(rows)),)

    def _complications(self) -> tuple[str, ...]:
        """Always the SRD's own table: no other pack publishes one."""
        return self.srd_pack().complications

    def change_stress(self, draft: BreathlessGame, args: ChangeStress, _rng: Random) -> list[Fact]:
        return (
            self.world_of(draft).require_actor(args.actor_id).change_stress(args.amount, args.why)
        )

    def use_med_kit(self, draft: BreathlessGame, args: UseMedKit, _rng: Random) -> list[Fact]:
        return self.world_of(draft).require_actor(args.actor_id).use_med_kit()

    def hire_prompt(self, draft: BreathlessGame, member: Survivor, terms: str) -> str:
        pack = self.first_pack(draft)
        return self.render_request(
            draft,
            guidance=AUTHORING,
            intent=HIRING.format(
                name=member.name,
                brief=member.brief,
                terms=terms,
                jobs=", ".join(pack.jobs),
                weapons=", ".join(pack.weapons),
            ),
            answer=SheetDraft,
        )

    def install_sheet(self, member: Survivor, answer: SheetDraft) -> str:
        member.take_sheet(
            SurvivorSheet(
                pronouns=answer.pronouns,
                job=answer.job,
                skills=dict(answer.skills),
                worn=dict(answer.skills),
                items={slug(answer.item, ()): Supply(name=answer.item, die=STARTING_ITEM)},
            )
        )
        return answer.job

    def roll(self, draft: BreathlessGame, args: Roll, rng: Random) -> list[Fact]:
        world = self.world_of(draft)
        actor = world.require_actor(args.actor_id)
        pool = _pool(world, actor, args)

        faces = (pool.die,) if pool.helper is None else (pool.die, pool.helper[1])
        label = "+".join(f"d{face}" for face in faces)
        rolled = roll_pool(faces, f"{args.what} — {pool.label}", rng, label=label)
        result = banded(rolled.kept, "fail", "success-but", "success")

        worn_facts = _wear(actor, args, pool)
        line = _line(world, actor, args, pool, result)
        _consequence(draft, actor, pool, args, result)

        return [rolled.fact, actor.fact(line, card=line, dice=(rolled.event,)), *worn_facts]

    def catch_breath(self, draft: BreathlessGame, args: Actor, rng: Random) -> list[Fact]:
        world = self.world_of(draft)
        actor = world.require_actor(args.actor_id)
        facts = actor.catch_breath()

        rolled = roll((12,), "a new complication", rng)
        text = self._complications()[rolled.rolled[0] - 1]
        draft.note(
            f"Catching breath brings a new complication. The SRD's table suggests: {text} Bring "
            "it in through the story, or one that fits better."
        )
        return [rolled.fact, *facts]

    def answer(self, draft: BreathlessGame, chosen: PendingOption, rng: Random) -> tuple[Fact, ...]:
        if chosen.name != TAKE_LOOT:
            return super().answer(draft, chosen, rng)
        taken = parse(TakeLoot, chosen.args)
        return (self.world_of(draft).player.take_loot(taken.item, taken.granted, taken.choice),)

    def loot_check(self, draft: BreathlessGame, args: LootCheck, rng: Random) -> list[Fact]:
        item, player = args.item, self.world_of(draft).player
        sheet = player.require_sheet()
        before = sheet.loot
        rolled = roll((before,), f"scavenging — {item}", rng)
        face = rolled.rolled[0]
        sheet.step_loot()

        found: Die | None = None
        if face <= 2:
            draft.note("The scavenge turns up trouble right here; nothing is found.")
        elif face <= 4:
            draft.note("The scavenge finds nothing, and trouble is coming.")
        else:
            found = next(die for die in LADDER if face <= die)

        result = f"found {item} (d{found})" if found is not None else "nothing"
        line = f"Scavenge — d{before} → {result}"
        fact = player.fact(line, card=line, dice=(rolled.event,))
        facts = [rolled.fact, fact]

        if found is not None:
            draft.pending = PendingDecision(
                kind="loot",
                prompt=f"You found {item} (d{found}). Take it?",
                options=sheet.loot_options(item, found),
                allows_text=False,
            )
        return facts

    def test_luck(self, _draft: BreathlessGame, args: TestLuck, rng: Random) -> list[Fact]:
        return luck_test(args.question, args.die, ("fail", "success-but", "success"), rng)


def _pool(world: BreathlessWorld, actor: Survivor, args: Roll) -> Pool:
    sheet = actor.require_sheet()
    if args.skill is not None:
        helper: tuple[Survivor, Die] | None = None
        if args.helped_by is not None:
            partner = world.require_actor(args.helped_by)
            if partner is actor:
                raise Refusal(f"{actor.name} cannot help their own roll")
            helper = (partner, partner.require_sheet().worn[args.skill])
        return Pool(die=sheet.worn[args.skill], label=args.skill, helper=helper)
    if args.item_id is not None:
        item = sheet.require(args.item_id, actor.name)
        return Pool(die=item.die, label=item.name, helper=None)
    sheet.spend_stunt(actor.name)
    return Pool(die=STUNT_DIE, label="stunt", helper=None)


def _wear(actor: Survivor, args: Roll, pool: Pool) -> list[Fact]:
    if args.skill is not None:
        actor.require_sheet().wear(args.skill)
        if pool.helper is not None:
            pool.helper[0].require_sheet().wear(args.skill)
        return []
    if args.item_id is not None:
        return actor.wear_item(args.item_id)
    return []


def _line(world: BreathlessWorld, actor: Survivor, args: Roll, pool: Pool, result: str) -> str:
    prefix = "" if actor is world.player else f"{actor.name}: "
    line = f"{args.what} — {prefix}{sentence(pool.label)} d{pool.die}"
    if pool.helper is not None:
        line += f", helped by {pool.helper[0].name} (d{pool.helper[1]})"
    return f"{line} → {result}"


def _consequence(
    draft: BreathlessGame, actor: Survivor, pool: Pool, args: Roll, result: str
) -> None:
    if not (args.dangerous and result == "fail"):
        return
    for who in (actor, *((pool.helper[0],) if pool.helper else ())):
        if who.require_sheet().vulnerable:
            draft.note(
                f"{who.name} is vulnerable and this dangerous roll failed: rule "
                "whether they are taken out of the scene or dead. Death is "
                f"`kill` on {who.name}."
            )


def _skill(name: str) -> Skill:
    """`check_picks` has already held the answer to the pack's six ids, which are the SRD's."""
    return next(skill for skill in SKILLS if skill == name)
