from pathlib import Path
from random import Random

from aidm.core.creation import (
    CreationStep,
    Picks,
    check_picks,
    chosen_option,
    other_than,
    picked,
    picked_many,
)
from aidm.core.entities import EngineId, Slug, slug
from aidm.core.facts import Fact, roll, roll_pool
from aidm.core.model import PackSelection
from aidm.core.play import PendingDecision
from aidm.core.prompt import Sections
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import DiceLook, Look, Rows
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.tools import (
    CHANGE_TAGS,
    DRIVE,
    RESTORE_LUCK,
    ROLL,
    ChangeTags,
    Drive,
    RestoreLuck,
    Roll,
)
from aidm.engines.loner3e.world import (
    DIE_FACE,
    Loner3eCast,
    Loner3eCharacter,
    Loner3eGame,
    Loner3eScenario,
    Loner3eWorld,
    Outcome,
    outcome_for,
    pack_meanings,
    twist_pairing,
)
from aidm.engines.loner3e.worldsmith import AUTHORING, Pack
from aidm.engines.scenes.engine import SUPPLEMENTS, SceneEngine

TWIST_NOTE = (
    "A twist has just interrupted the scene: {subject} / {action}. The narration showed it "
    "arriving. Develop it this turn. Say what it set in motion, what it costs, and what it "
    "changes."
)
DEFEAT_NOTE = (
    "{name} has run out of luck and lost this conflict. Roll nothing more for it. Say how it "
    "ends for them: taken, severely injured, broken off, cornered, or conceding. Write any "
    "lasting mark with `change_tags`, as a `condition`. Then let the story move on. They are "
    "marked defeated and take no new conflict until `restore_luck` says it is behind them."
)


class Loner3eEngine(SceneEngine[Loner3eCast, Loner3eGame, Pack]):
    id = EngineId("loner3e")
    title = "LONER 3E"
    art_style = "Painterly illustration, muted colours, no text or lettering."
    look = Look(
        palette={
            "game-bg": "#14121e",
            "game-surface": "#201c2d",
            "game-surface-raised": "#2c263c",
            "game-text": "#eee7f4",
            "game-muted": "#bdb0ce",
            "game-border": "#443951",
            "game-accent": "#c5a4ed",
            "game-wash": "rgba(197, 164, 237, .09)",
            "game-radius": "18px",
        },
        dice=DiceLook(body="#efe4c8", ink="#7a2e2e", glow="#c89b5a"),
    )
    directory = Path(__file__).parent
    game = Loner3eGame
    scenario = Loner3eScenario
    character = Loner3eCharacter
    pack = Pack
    world = Loner3eWorld
    member = Loner3eCast

    def __init__(self) -> None:
        super().__init__()
        self.twist_table()  # fails at start, not mid-scene

    def world_of(self, state: Loner3eGame) -> Loner3eWorld:
        return state.payload

    def master_tools(self) -> tuple[MasterTool[Loner3eGame], ...]:
        return (
            *super().master_tools(),
            master_tool("change_tags", CHANGE_TAGS, ChangeTags, self.change_tags),
            master_tool("drive", DRIVE, Drive, self.drive),
            master_tool("restore_luck", RESTORE_LUCK, RestoreLuck, self.restore_luck),
            master_tool("roll", ROLL, Roll, self.roll),
        )

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        chosen = self.chosen_packs(picks)
        concepts = tuple(entry for pack in chosen for entry in pack.concepts)
        skills = tuple(option for pack in chosen for option in pack.skills)
        frailties = tuple(option for pack in chosen for option in pack.frailties)
        gear = tuple(option for pack in chosen for option in pack.gear)
        return (
            *self.supplement_steps(),
            CreationStep(
                id="concept",
                label="Write a one-line concept",
                hint=", ".join(entry.label for entry in concepts[:3]),
            ),
            CreationStep(id="goal", label="What does your character want?"),
            CreationStep(id="motive", label="Why do they want it?"),
            CreationStep(id="skill-1", label="Choose skill 1", options=skills),
            CreationStep(
                id="skill-2",
                label="Choose skill 2",
                options=other_than(skills, picked(picks, "skill-1")),
            ),
            CreationStep(id="frailty", label="Choose a frailty", options=frailties),
            CreationStep(id="gear-1", label="Choose gear 1", options=gear),
            CreationStep(
                id="gear-2",
                label="Choose gear 2",
                options=other_than(gear, picked(picks, "gear-1")),
            ),
        )

    def create_character(self, name: str, brief: str, picks: Picks) -> Loner3eCharacter:
        steps = self.creation_steps(picks)
        check_picks(steps, picks)
        packs = self.select_packs(picked_many(picks, SUPPLEMENTS))
        # The steps already carry the options pooled across the picked packs.
        by_id = {step.id: step for step in steps}

        def taken(step_id: Slug) -> str:
            return chosen_option(by_id[step_id].options, picked(picks, step_id)).label

        sheet = Loner3eCast(
            id=PLAYER_ID,
            name=name,
            brief=brief,
            known=True,
            concept=picked(picks, "concept"),
            tags={
                "skill": [taken(f"skill-{slot}") for slot in (1, 2)],
                "frailty": [taken("frailty")],
                "gear": [taken(f"gear-{slot}") for slot in (1, 2)],
            },
            goal=picked(picks, "goal"),
            motive=picked(picks, "motive"),
        )
        return Loner3eCharacter(id=slug(name, ()), engine=self.id, packs=packs, payload=sheet)

    def guidance(self, selection: PackSelection | None) -> str:
        """Defaults restate rules the guidance already carries; dropping them halves the prompt."""
        chosen = self.selected(selection)
        return f"{AUTHORING}\n\n{self.pack_content(chosen, exclude_defaults=True)}"

    def glossary(self, state: Loner3eGame) -> Sections:
        packs = self.selected_packs(state)
        spelled: dict[str, str] = {}
        for member in self.world_of(state).here():
            spelled.update(self._meanings(packs, member))
        lines = "\n".join(f"- {tag}: {detail}" for tag, detail in spelled.items())
        return (("WHAT THE TAGS IN PLAY MEAN", lines),) if spelled else ()

    def _meanings(self, packs: tuple[Pack, ...], sheet: Loner3eCast) -> Rows:
        # The concept's pack blurb is generic where the entity's own brief is not: skip it.
        return pack_meanings(
            tuple(entry for pack in packs for entry in (*pack.skills, *pack.frailties, *pack.gear)),
            (*sheet.tagged("skill"), *sheet.tagged("frailty"), *sheet.tagged("gear")),
        )

    def twist_table(self) -> Rows:
        """Always the SRD's own table: no other pack publishes one."""
        srd = self.srd_pack()
        if srd.twist_subjects is None or srd.twist_actions is None:
            raise ValueError("the SRD table set has no twist columns")
        return tuple(zip(srd.twist_subjects, srd.twist_actions, strict=True))

    def leaving(self, draft: Loner3eGame) -> list[Fact]:
        """A scene ends its conflicts so nobody carries a spent pool or a defeat on; the dead
        keep theirs."""
        world = self.world_of(draft)
        return [
            fact
            for member in (world.player, *world.cast.values())
            if member.alive
            for fact in member.recover("the scene is over")
        ]

    def change_tags(self, draft: Loner3eGame, args: ChangeTags, _rng: Random) -> list[Fact]:
        actor = self.world_of(draft).require_living_here(args.entity_id)
        return actor.change_tags(args.kind, args.gained, args.lost)

    def drive(self, draft: Loner3eGame, args: Drive, _rng: Random) -> list[Fact]:
        actor = self.world_of(draft).require_living_here(args.entity_id)
        return actor.drive(goal=args.goal, motive=args.motive, nemesis=args.nemesis)

    def restore_luck(self, draft: Loner3eGame, args: RestoreLuck, _rng: Random) -> list[Fact]:
        actor = self.world_of(draft).require_living_here(args.entity_id)
        facts = actor.reveal()
        # Already full and undefeated is a quiet no-op: `adjust` writes no fact for a zero delta.
        facts.extend(actor.recover("the conflict is behind them"))
        return facts

    def roll(self, draft: Loner3eGame, args: Roll, rng: Random) -> list[Fact]:
        world = self.world_of(draft)
        actor = world.require_living_here(args.actor_id)
        reveals = actor.reveal()
        opponent = None
        if args.opponent_id is not None:
            opponent = world.require_living_here(args.opponent_id)
            reveals.extend(opponent.reveal())
        world.check_conflict(actor, opponent)

        chance_faces, risk_faces = args.faces()
        chance = roll_pool(chance_faces, f"{args.question} — chance", rng, label="Chance")
        risk = roll_pool(risk_faces, f"{args.question} — risk", rng, label="Risk")

        outcome = outcome_for(chance.kept, risk.kept)
        line = _oracle_line(args, opponent, outcome)
        exchange: list[Fact] = []
        effects: tuple[str, ...] = ()
        if opponent is not None:
            struck = world.strike(actor, opponent, outcome)
            exchange, effects = _absorbed(struck.facts)
            if struck.loser:
                draft.note(DEFEAT_NOTE.format(name=struck.loser))
            else:
                draft.pending = PendingDecision(
                    kind="conflict",
                    prompt=world.conflict_prompt(actor, opponent),
                    options=(),
                    allows_text=True,
                )
        # SRD: the Twist Counter skips Harm & Luck, so a tied conflict roll never ticks it.
        tied = chance.kept == risk.kept and opponent is None
        twist_facts = self._twist(draft, actor, rng) if tied and world.tick_twist() else []
        return [
            *reveals,
            chance.fact,
            risk.fact,
            # The question is master-authored and may name unrevealed canon: never told.
            Fact(trace=f"asked: {args.question}"),
            actor.fact(line, card="\n".join((line, *effects)), dice=(chance.event, risk.event)),
            *exchange,
            *twist_facts,
        ]

    def _twist(self, draft: Loner3eGame, actor: Loner3eCast, rng: Random) -> list[Fact]:
        """The SRD's table is rolled here so the dice trace; the model only reads the pairing."""
        rolled = roll((DIE_FACE, DIE_FACE), "twist — subject, action", rng, label="Twist")
        subject_face, action_face = rolled.event.rolled
        subject, action = twist_pairing(subject_face, action_face, self.twist_table())
        draft.note(TWIST_NOTE.format(subject=subject.upper(), action=action.upper()))
        # Echo the unnamed SRD intrusion in the call that rolled it without adding canon.
        due = actor.fact(
            f"a twist interrupts the scene: {subject} / {action}",
            card=f"Twist — {subject} / {action}",
            dice=(rolled.event,),
        )
        return [rolled.fact, due]


def _oracle_line(args: Roll, opponent: Loner3eCast | None, outcome: Outcome) -> str:
    footing = args.position + (f" ({args.edge})" if args.edge else "")
    against = f" against {opponent.name}" if opponent is not None else ""
    return f"{args.what}{against} — oracle, {footing}: {outcome.wording}"


def _absorbed(exchange: list[Fact]) -> tuple[list[Fact], tuple[str, ...]]:
    """The exchange reads as lines inside the Oracle card, so it shows no cards of its own."""
    lines = tuple(fact.card for fact in exchange if fact.told and fact.card)
    return [fact.model_copy(update={"card": ""}) for fact in exchange], lines
