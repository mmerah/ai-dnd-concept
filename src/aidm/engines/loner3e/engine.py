from pathlib import Path
from random import Random

from aidm.core.creation import (
    CreationStep,
    Picks,
    chosen_option,
    other_than,
    picked,
)
from aidm.core.entities import EngineId, Refusal, Slug
from aidm.core.facts import Fact, roll
from aidm.core.model import AnyCharacter
from aidm.core.play import PendingDecision
from aidm.core.prompt import Sections
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import Rows
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.tools import (
    CHANGE_TAGS,
    DEFEAT_NOTE,
    DRIVE,
    RESTORE_LUCK,
    ROLL,
    SPEND_LUCK,
    TWIST_NOTE,
    ChangeTags,
    Drive,
    RestoreLuck,
    Roll,
    SpendLuck,
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
from aidm.engines.loner3e.worldsmith import (
    AUTHORING,
    Loner3eBody,
    Loner3eHead,
    Loner3ePack,
)
from aidm.engines.scenes.engine import SceneEngine


class Loner3eEngine(SceneEngine[Loner3eCast, Loner3eWorld, Loner3ePack]):
    id = EngineId("loner3e")
    title = "LONER 3E"
    authoring = AUTHORING
    art_style = "Painterly illustration, muted colours, no text or lettering."
    directory = Path(__file__).parent
    scenario = Loner3eScenario
    character = Loner3eCharacter
    pack = Loner3ePack
    head = Loner3eHead
    body = Loner3eBody
    world = Loner3eWorld
    member = Loner3eCast

    def __init__(self, written: Path) -> None:
        super().__init__(written)
        srd = self.packs.srd()  # always the SRD's own table: no other pack publishes one
        if srd.twist_subjects is None or srd.twist_actions is None:
            raise ValueError("the SRD table set has no twist columns")
        self.twists: Rows = tuple(zip(srd.twist_subjects, srd.twist_actions, strict=True))

    def master_tools(self) -> tuple[MasterTool[Loner3eGame], ...]:
        return (
            *super().master_tools(),
            master_tool("change_tags", CHANGE_TAGS, ChangeTags, self.change_tags),
            master_tool("drive", DRIVE, Drive, self.drive),
            master_tool("restore_luck", RESTORE_LUCK, RestoreLuck, self.restore_luck),
            master_tool("roll", ROLL, Roll, self.roll),
            master_tool("spend_luck", SPEND_LUCK, SpendLuck, self.spend_luck),
        )

    def creation_steps(self, pack_id: Slug, picks: Picks) -> tuple[CreationStep, ...]:
        played = self.packs.played(pack_id)
        concepts = tuple(entry for pack in played for entry in pack.concepts)
        skills = tuple(option for pack in played for option in pack.skills)
        frailties = tuple(option for pack in played for option in pack.frailties)
        gear = tuple(option for pack in played for option in pack.gear)
        return (
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

    def build_character(
        self, name: str, brief: str, pack_id: Slug, picks: Picks
    ) -> Loner3eCharacter:
        steps = self.creation_steps(pack_id, picks)
        # The steps already carry the SRD's options and the chosen pack's.
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
        return self.sheet_character(name, sheet)

    def player_of(self, character: AnyCharacter) -> Loner3eCast:
        return self.player_as(character, Loner3eCast)

    def master_sections(self, state: Loner3eGame) -> Sections:
        packs = self.packs.played(state.pack_id)
        # The concept's pack blurb is generic where the entity's own brief is not: skip it.
        entries = tuple(
            entry for pack in packs for entry in (*pack.skills, *pack.frailties, *pack.gear)
        )
        spelled: dict[str, str] = {}
        for member in state.world.here():
            spelled.update(
                pack_meanings(
                    entries,
                    (*member.tagged("skill"), *member.tagged("frailty"), *member.tagged("gear")),
                )
            )
        lines = "\n".join(f"- {tag}: {detail}" for tag, detail in spelled.items())
        glossary = (("WHAT THE TAGS IN PLAY MEAN", lines),) if spelled else ()
        return (
            *super().master_sections(state),
            *glossary,
        )

    def change_tags(self, draft: Loner3eGame, args: ChangeTags, _rng: Random) -> list[Fact]:
        world = draft.world
        world.check_unnamed(*args.gained)
        actor = world.require_living_here(args.actor_id)
        return actor.change_tags(args.kind, args.gained, args.lost)

    def drive(self, draft: Loner3eGame, args: Drive, _rng: Random) -> list[Fact]:
        world = draft.world
        world.check_unnamed(args.goal, args.motive, args.nemesis)
        actor = world.require_living_here(args.actor_id)
        return actor.drive(goal=args.goal, motive=args.motive, nemesis=args.nemesis)

    def restore_luck(self, draft: Loner3eGame, args: RestoreLuck, _rng: Random) -> list[Fact]:
        actor = draft.world.require_living_here(args.actor_id)
        # Already full and undefeated is a quiet no-op: `adjust` writes no fact for a zero delta.
        return actor.recover("the conflict is behind them")

    def spend_luck(self, draft: Loner3eGame, args: SpendLuck, _rng: Random) -> list[Fact]:
        if not self.packs.require(draft.pack_id).spends_luck:
            raise Refusal("this pack does not spend luck")
        world = draft.world
        world.check_unnamed(args.why)
        actor = world.require_living_here(args.actor_id)
        return actor.spend_luck(args.amount, args.why)

    def roll(self, draft: Loner3eGame, args: Roll, rng: Random) -> list[Fact]:
        world = draft.world
        world.check_unnamed(args.what, args.edge)
        actor = world.require_living_here(args.actor_id)
        opponent = None
        if args.target_id is not None:
            opponent = world.require_living_here(args.target_id)
        world.check_conflict(actor, opponent)

        chance_faces, risk_faces = args.faces()
        chance = roll(
            chance_faces, f"{args.question} — chance", rng, label="Chance", highlight_kept=True
        )
        risk = roll(risk_faces, f"{args.question} — risk", rng, label="Risk", highlight_kept=True)

        outcome = outcome_for(chance.kept, risk.kept)
        line = _oracle_line(args, opponent, outcome)
        exchange: list[Fact] = []
        effects: tuple[str, ...] = ()
        if opponent is not None:
            facts, loser = world.strike(actor, opponent, outcome)
            exchange, effects = _absorbed(facts)
            if loser:
                draft.note(DEFEAT_NOTE.format(name=loser))
            elif PLAYER_ID in (actor.id, opponent.id):
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
        subject, action = twist_pairing(subject_face, action_face, self.twists)
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
