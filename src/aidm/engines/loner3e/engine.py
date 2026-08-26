from pathlib import Path
from random import Random

from pydantic import Field

from aidm.content.model import CharacterProfile, CreatedCharacter
from aidm.engines.core import (
    ProposalBase,
    SheetAdvancement,
    SheetEngine,
    action,
    chapter_command,
    rule,
)
from aidm.engines.loner3e.rules import (
    GROWTH,
    AdventureGrowth,
    Change,
    Conflict,
    Mechanics,
    Pack,
    Question,
    Sheet,
    apply_restore_luck,
    resolve_question,
    twist_table,
)
from aidm.engines.packs import PackCreation, find_entry, load_packs, pack_options, pack_paths
from aidm.state.creation import (
    AnyStep,
    CreationStep,
    Picks,
    TextStep,
    check_picks,
    picked,
)
from aidm.state.entities import (
    PLAYER_ID,
    CheckedEntityId,
    Counter,
    EngineId,
    Entity,
    EntityId,
    Frozen,
)
from aidm.state.facts import Fact, explained_fact
from aidm.state.model import Game


class RestoreLuck(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or an actor here.")


class Loner3eAdvancement(SheetAdvancement):
    proposal_type = AdventureGrowth
    ledger_key = "milestones"
    occasion = "finishes an adventure"
    offer_text = GROWTH
    spent_why = "a milestone spent"

    def ledger(self, state: Game, subject_id: EntityId) -> Counter:
        return Mechanics.of_game(state).sheets[subject_id].milestones

    def grant(
        self, draft: Game, subject_id: EntityId, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        del rng
        assert isinstance(proposal, AdventureGrowth)
        sheet = Mechanics.of_game(draft).sheets[subject_id]
        subject = draft.world.require(subject_id)
        # Sequential against the live sheet, so a rewrite may name what an earlier change wrote.
        return tuple(
            _rewrite(sheet, subject, change, proposal.why)
            if change.kind == "rewrite"
            else _gain(sheet, subject, change, proposal.why)
            for change in proposal.changes
        )


def _gain(sheet: Sheet, subject: Entity, change: Change, why: str) -> Fact:
    if change.kind == "skill":
        sheet.skills = (*sheet.skills, change.tag)
    elif change.kind == "gear":
        sheet.gear = (*sheet.gear, change.tag)
    else:
        sheet.frailties = (*sheet.frailties, change.tag)
    return explained_fact(
        subject,
        f"{change.kind}_gained",
        f"{subject.name} gained {change.kind} {change.tag}",
        why,
        narrate=False,
    )


def _rewrite(sheet: Sheet, subject: Entity, change: Change, why: str) -> Fact:
    old, new = change.tag, change.into
    if old in sheet.skills:
        sheet.skills = _swapped(sheet.skills, old, new)
    elif old in sheet.frailties:
        sheet.frailties = _swapped(sheet.frailties, old, new)
    elif old in sheet.gear:
        sheet.gear = _swapped(sheet.gear, old, new)
    else:
        raise ValueError(f"{subject.name} carries no tag {old!r} to rewrite")
    return explained_fact(
        subject,
        "tag_rewritten",
        f"{subject.name} rewrote {old} as {new}",
        why,
        narrate=False,
    )


def _swapped(tags: tuple[str, ...], old: str, new: str) -> tuple[str, ...]:
    return tuple(new if tag == old else tag for tag in tags)


class Loner3eCreation(PackCreation[Pack]):
    def steps_for(self, pack: Pack, picks: Picks) -> tuple[AnyStep, ...]:
        del picks
        return (
            TextStep(
                id="concept",
                prompt="Write a one-line concept",
                hint=", ".join(entry.label for entry in pack.concepts[:3]),
            ),
            CreationStep(
                id="skills", prompt="Choose two skills", options=pack_options(pack.skills), choose=2
            ),
            CreationStep(
                id="frailty", prompt="Choose a frailty", options=pack_options(pack.frailties)
            ),
            CreationStep(
                id="gear",
                prompt="Choose two pieces of gear",
                options=pack_options(pack.gear),
                choose=2,
            ),
        )

    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        check_picks(self.steps(picks), picks)
        pack = self.packs[picked(picks, "pack")[0]]
        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief),
            rules={
                "pack": picked(picks, "pack")[0],
                "concept": picked(picks, "concept")[0],
                "skills": [
                    find_entry(pack.skills, skill).label for skill in picked(picks, "skills")
                ],
                "frailties": [find_entry(pack.frailties, picked(picks, "frailty")[0]).label],
                "gear": [find_entry(pack.gear, gear).label for gear in picked(picks, "gear")],
            },
        )


class Loner3eEngine(SheetEngine[Sheet]):
    id = EngineId("loner3e")
    badge = ("LONER 3E", "teal-7")
    engine_dir = Path(__file__).parent
    sheet_type = Sheet
    mechanics_type = Mechanics
    decisions = (Conflict,)

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.advancement = Loner3eAdvancement(self.engine_dir)
        self.creation = Loner3eCreation(self.packs)
        self.director_commands = (
            rule(
                "roll_question",
                "Roll Chance against Risk for one closed dramatic question.",
                Question,
                lambda draft, one, rng: resolve_question(draft, one, rng, self.twists(draft)),
            ),
            action(
                "restore_luck",
                "Restore an actor's luck after a conflict ends.",
                RestoreLuck,
                lambda draft, one: apply_restore_luck(draft, one.actor_id),
            ),
            chapter_command(
                "Record that the current adventure has ended.", "the adventure has ended"
            ),
        )

    def validate(self, state: Game) -> None:
        super().validate(state)
        if (chosen := Mechanics.of_game(state).sheets[PLAYER_ID].pack) not in self.packs:
            raise ValueError(f"this game plays the {chosen!r} table set, which is not installed")

    def twists(self, state: Game) -> tuple[tuple[str, str], ...]:
        """The player's own table set: an NPC sheet is seeded with the default and never selects."""
        return twist_table(self.packs, Mechanics.of_game(state).sheets[PLAYER_ID].pack)
