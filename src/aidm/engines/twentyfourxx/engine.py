from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import NamedTuple

from aidm.core.creation import (
    CreationStep,
    Picks,
    chosen_option,
    option_of,
    picked,
)
from aidm.core.entities import EngineId, Refusal, Slug, slug, tag_of
from aidm.core.facts import Fact, roll
from aidm.core.model import AnyCharacter, Commission, WorldsmithAnswer
from aidm.core.play import DecisionOption, PendingDecision, PendingOption
from aidm.core.prompt import Sections, lines_of, section_if, sentence
from aidm.core.tools import tool
from aidm.core.views import Panel, PanelRow, PlayerView, Rows
from aidm.engines.base import (
    PLAYER_ID,
    character_panel,
    here_panel,
    party_panel,
    party_section,
    trail_panel,
)
from aidm.engines.engine import Operation, Written
from aidm.engines.hiring import (
    HIRE,
    HIRE_UNWRITTEN,
    Hire,
    file_hire,
    hire_target,
    signed_on,
)
from aidm.engines.packs import unique_options
from aidm.engines.scenes.engine import MOVE_ON, SceneEngine
from aidm.engines.tools import Kill
from aidm.engines.twentyfourxx.pack import (
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
from aidm.engines.twentyfourxx.tools import (
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
    scenario = TwentyfourxxScenario
    character = TwentyfourxxCharacter
    pack = TwentyfourxxPack
    head = TwentyfourxxHead
    body = TwentyfourxxBody
    world = TwentyfourxxWorld
    member = Crewmate

    def operations(self) -> Mapping[Slug, Operation[TwentyfourxxWorld]]:
        return {**super().operations(), HIRE: Operation(self.write_hire, HIRE_UNWRITTEN)}

    def __init__(self, player_packs: Path) -> None:
        super().__init__(player_packs)
        srd = self.packs.srd()
        if len(srd.skills) != SKILL_COUNT:
            raise ValueError(
                f"the {self.id!r} srd pack lists {len(srd.skills)} skills, not {SKILL_COUNT}"
            )
        if not srd.starting_kit:
            raise ValueError(f"the {self.id!r} srd pack has no starting kit")

    @tool
    def hire(self, draft: TwentyfourxxGame, args: Hire, _rng: Random) -> list[Fact]:
        """Call this when the player hires a character here to work. The player can also hire a
        character who already travels with the player. The worldsmith writes the sheet of that
        character at the end of the turn. Nothing more happens this turn. Give a sheet only to a
        character hired to work. Do not give a sheet to a character who only travels along."""
        return file_hire(draft, args.target_id, args.terms)

    async def write_hire(
        self, draft: TwentyfourxxGame, commission: Commission, worldsmith: WorldsmithAnswer
    ) -> Written:
        member = hire_target(draft.world, commission)
        packs = self.packs.played(draft.pack_id)
        lines = [pack.specialty_lines() for pack in packs]
        lines.append(f"Skills: {', '.join(option.name for option in self.packs.srd().skills)}")
        prompt = self.render_commission(
            draft,
            guidance="\n".join(lines),
            intent=HIRING.format(name=member.name, brief=member.brief, terms=commission.detail),
            answer_model=SheetProposal,
        )
        answer = await worldsmith(prompt, SheetProposal, lambda sheet: sheet.check(packs))
        summary = member.sign_on(
            answer.specialty,
            answer.skills,
            items_from_kits(tuple(Kit(name=name) for name in answer.items)),
            answer.hindrances,
        )
        return signed_on(draft.world, member, summary)

    def creation_steps(self, pack_id: Slug, picks: Picks) -> tuple[CreationStep, ...]:
        specialties, origins = self._offered(pack_id)
        # The rules fix the seventeen skills: a pack adds specialties and origins only.
        skills = self.packs.srd().skills
        steps = [CreationStep(id="specialty", name="Specialty", options=specialties)]
        specialty = option_of(specialties, picked(picks, "specialty"))
        if specialty is None:
            return tuple(steps)
        if specialty.choice:
            steps.append(
                CreationStep(
                    id="specialty-choice", name="Specialty skill", options=specialty.choice
                )
            )
        if specialty.kit_choice:
            steps.append(
                CreationStep(
                    id="weapon",
                    name="Weapon",
                    options=tuple(
                        DecisionOption(id=slug(kit.name, ()), name=kit.name)
                        for kit in specialty.kit_choice
                    ),
                )
            )
        steps.append(CreationStep(id="origin", name="Origin", options=origins))
        origin = option_of(origins, picked(picks, "origin"))
        if origin is None:
            return tuple(steps)
        steps.extend(
            CreationStep(id=f"trait-{number}", name=f"Trait {number}", hint=origin.brief)
            for number in range(1, origin.invents + 1)
        )
        if origin.choice:
            steps.append(CreationStep(id="body", name="Body", options=origin.choice))
        steps.extend(
            CreationStep(
                id=f"increase-{number}",
                name="Skill increase",
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
            skill = option.name if option is not None else self._match_skill(skills, typed) or typed
            if (new_die := raised(skills.get(skill))) is None:
                raise Refusal("the skill is already at d12")
            skills[skill] = new_die

        weapon: Kit | None = None
        if specialty.kit_choice:
            wanted = picked(picks, "weapon")
            weapon = next(
                (kit for kit in specialty.kit_choice if slug(kit.name, ()) == wanted), None
            )
            if weapon is None:
                raise Refusal(f"{wanted!r} is not a weapon on offer")

        traits = tuple(picked(picks, f"trait-{number}") for number in range(1, origin.invents + 1))
        body = None
        if origin.choice:
            body = chosen_option(origin.choice, picked(picks, "body"))
            traits = (*traits, body.name)

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
                specialty=specialty.name,
                origin=origin.name,
                traits=traits,
                skills=skills,
                items=items_from_kits(kits),
            ),
        )
        return self.sheet_character(name, player)

    def player_of(self, character: AnyCharacter) -> Crewmate:
        return self.player_as(character, Crewmate)

    def preview_character(self, character: AnyCharacter) -> Rows:
        sheet = self.player_of(character).require_sheet()
        return (*sheet.rows(), ("Gear", sheet.gear_text()))

    def master_sections(self, state: TwentyfourxxGame) -> Sections:
        world = state.world
        scene = world.scene
        return (
            ("SCENE", f"{scene.title}\n{scene.situation}"),
            *section_if("WHAT THIS SCENE IS ABOUT", scene.focus),
            ("YOU PLAY FOR", world.player.line(rows=world.player.rows())),
            ("GEAR", _item_lines(world.player.require_sheet().items)),
            *section_if("THE JOB", world.job),
            ("THE SHIP", _item_lines(world.ship)),
            ("HERE WITH THE PLAYER", world.here_lines()),
            *party_section(world.members()),
            ("HIDDEN HERE (the player has not found these)", world.hidden_lines()),
            *section_if("THE ARC (the player has not found this)", world.arc),
            *self.packs.rules_section(state.pack_id),
        )

    def player_view(self, state: TwentyfourxxGame) -> PlayerView:
        world = state.world
        player = world.player
        job = world.job
        job_panel = (Panel(title="Job", rows=(PanelRow(name=job, brief=""),)),) if job else ()
        ship_panel = Panel(
            title="Ship",
            rows=tuple(
                PanelRow(name=function.name, brief=function.notes())
                for function in world.ship.values()
            ),
        )
        return PlayerView(
            premise=state.scenario.premise,
            player=player.subject(),
            scene_title=world.scene.title,
            situation=world.scene.situation,
            panels=(
                character_panel(world.sheet_rows()),
                *job_panel,
                ship_panel,
                *world.scene_panel(),
                *party_panel(world.members()),
                here_panel(other.subject() for other in world.others()),
                trail_panel(scene.title for scene in world.scenes),
            ),
            decision=state.pending,
            action=MOVE_ON if world.scene.way_offered else None,
            ending=self.ending(state),
        )

    def resolve_skill(self, sheet: CrewSheet, wanted: str) -> str:
        if (match := self._match_skill(sheet.skills, wanted)) is not None:
            return match
        known = ", ".join(sorted(sheet.skills)) or "none"
        listed = ", ".join(option.name for option in self.packs.srd().skills)
        raise Refusal(
            f"{wanted!r} is not a skill on the sheet ({known}) or in the rules ({listed})"
        )

    def _match_skill(self, known: Mapping[str, SkillDie], wanted: str) -> str | None:
        folded = _folded(wanted)
        names = (*known, *(option.name for option in self.packs.srd().skills))
        return next((name for name in names if _folded(name) == folded), None)

    @tool
    def change_hindrances(
        self, draft: TwentyfourxxGame, args: ChangeHindrances, _rng: Random
    ) -> list[Fact]:
        """The actor gains hindrances, loses hindrances, or does both."""
        world = draft.world
        world.check_unnamed(*args.gained)
        actor = world.require_actor(args.actor_id)
        return actor.change_hindrances(args.gained, args.lost, leads=actor is world.player)

    @tool
    def gain_item(self, draft: TwentyfourxxGame, args: GainItem, _rng: Random) -> list[Fact]:
        """The actor gains an item and pays for it."""
        world = draft.world
        world.check_unnamed(args.name)
        actor = world.require_actor(args.actor_id)
        return actor.gain_item(
            args.name,
            bulky=args.bulky,
            breaks=args.breaks,
            cost=args.cost,
            leads=actor is world.player,
        )

    @tool
    def drop_item(self, draft: TwentyfourxxGame, args: DropItem, _rng: Random) -> list[Fact]:
        """The actor loses an item permanently."""
        actor = draft.world.require_actor(args.actor_id)
        return actor.require_sheet().drop_item(args.item_id, actor)

    @tool
    def repair_item(self, draft: TwentyfourxxGame, args: RepairItem, _rng: Random) -> list[Fact]:
        """The actor repairs a broken item."""
        world = draft.world
        actor = world.require_actor(args.actor_id)
        return actor.repair_item(
            world.require_gear(actor, args.item_id), args.cost, leads=actor is world.player
        )

    @tool
    def spend(self, draft: TwentyfourxxGame, args: Spend, _rng: Random) -> list[Fact]:
        """The actor pays credits for a thing that is not an item and not a repair."""
        world = draft.world
        world.check_unnamed(args.why)
        actor = world.require_actor(args.actor_id)
        return actor.spend(args.amount, args.why, leads=actor is world.player)

    @tool
    def take_lead(self, draft: TwentyfourxxGame, args: TakeLead, _rng: Random) -> list[Fact]:
        """A hired member takes the lead after the player dies."""
        return draft.world.take_lead(args.actor_id)

    @tool
    def ship_upgrade(self, draft: TwentyfourxxGame, args: ShipUpgrade, _rng: Random) -> list[Fact]:
        """The player upgrades one ship function."""
        return draft.world.upgrade_ship(args.function_id)

    @tool
    def defend(self, draft: TwentyfourxxGame, args: Defend, _rng: Random) -> list[Fact]:
        """A carried item or a ship function breaks. The hit becomes a hindrance."""
        world = draft.world
        world.check_unnamed(args.hindrance)
        return world.defend(args.actor_id, args.item_id, args.hindrance)

    @tool
    def kill(self, draft: TwentyfourxxGame, args: Kill, rng: Random) -> list[Fact]:
        """A character here dies. If that character is the lead, the crew choose a new lead."""
        facts = super().kill(draft, args, rng)
        self._succession(draft)
        return facts

    def _offered(self, pack_id: Slug) -> tuple[tuple[Specialty, ...], tuple[Origin, ...]]:
        played = self.packs.played(pack_id)
        return (
            unique_options(option for pack in played for option in pack.specialties),
            unique_options(option for pack in played for option in pack.origins),
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
                    name=member.name,
                    brief=member.brief,
                    tool_name="take_lead",
                    args={"actor_id": member.id},
                )
                for member in members
            ),
            allows_text=False,
        )

    def ending(self, state: TwentyfourxxGame) -> str | None:
        """A dead lead with a hired member alive is a succession, not an ending."""
        return None if state.world.sheeted_members() else super().ending(state)

    @tool
    def roll(self, draft: TwentyfourxxGame, args: Roll, rng: Random) -> list[Fact]:
        """Call this when the result of an action is important. The engine selects the dice,
        rolls the dice, and reads the result."""
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

        led = actor.card_line(sentence(pool.label), leads=actor is world.player)
        line = f"{args.what} — {led} d{pool.die}"
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
            helper_die = HINDERED_DIE if terms.hindered else HELP_DIE
            hindered_note = f", hindered ({terms.hindered})" if terms.hindered else ""
            faces.append(helper_die)
            helped_by = f", helped by {who.name} (d{helper_die}{hindered_note})"

        return DicePool(faces=tuple(faces), label=label, die=die, helped_by=helped_by)

    @tool
    def ask_world(self, _draft: TwentyfourxxGame, args: AskWorld, rng: Random) -> list[Fact]:
        """Call this to ask about bad luck in the world when no character acts. The engine
        rolls one d6 and reads the die."""
        rolled = roll((6,), args.question, rng)
        result = _banded(rolled.face, "trouble now", "signs of it", "nothing")
        # The dice trace; the answer itself is never told.
        return [rolled.fact, Fact(trace=f"{args.question} — d6 [{rolled.face}] → {result}")]

    @tool
    def job(self, draft: TwentyfourxxGame, args: Job, rng: Random) -> list[Fact]:
        """Call this with `find` to look for work, with `take` to record agreed work, and with
        `finish` to close the job. With `find` the engine rolls the d6 of the SRD. With
        `finish` the engine raises one skill for each operator, then pays each operator d6
        credits."""
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
            leads = actor is world.player
            facts.extend(actor.raise_skill(skill, leads=leads))

            rolled = roll((6,), f"credits earned by {actor.name}", rng)
            facts.append(rolled.fact)
            facts.extend(actor.earn(rolled.face, rolled.event, leads=leads))
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
        f"- {tag_of(item.name, key)}" + (f" — {detail}" if (detail := item.notes()) else "")
        for key, item in items.items()
    )


def _staked(risk: str, *, deadly: bool) -> str:
    return f"{risk} (deadly)" if deadly else risk


def _folded(name: str) -> str:
    return " ".join(name.split()).casefold()


def _banded(face: int, low: str, mid: str, high: str) -> str:
    return low if face <= 2 else mid if face <= 4 else high
