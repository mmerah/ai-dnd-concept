from collections.abc import Mapping, Sequence
from pathlib import Path
from random import Random

from pydantic import Field

from aidm.content.model import CharacterProfile, CreatedCharacter, Scenario
from aidm.engines.core import ProposalBase, action, rule
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
from aidm.engines.packs import (
    PackChoice,
    PackCreation,
    character_packs,
    find_entry,
    pack_options,
)
from aidm.engines.sheets import SheetAdvancement, SheetEngine, chapter_command
from aidm.engines.sources import SHIPPED_PACKS, PackSources
from aidm.state.creation import (
    AnyStep,
    CreationStep,
    Picks,
    TextStep,
    check_picks,
    picked,
)
from aidm.state.entities import (
    CheckedEntityId,
    Counter,
    EngineId,
    Entity,
    EntityId,
    Frozen,
)
from aidm.state.facts import Fact, MechanicEvent, explained_fact
from aidm.state.model import Game


class RestoreLuck(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or an actor here.")


class Loner3eAdvancement(SheetAdvancement):
    proposal_type = AdventureGrowth
    ledger_key = "milestones"
    text = GROWTH
    spent_why = "a milestone spent"

    def ledger(self, state: Game, subject_id: EntityId) -> Counter:
        return Mechanics.of_game(state).sheets[subject_id].milestones

    def grant(self, draft: Game, proposal: ProposalBase, rng: Random) -> tuple[Fact, ...]:
        del rng
        assert isinstance(proposal, AdventureGrowth)
        sheet = Mechanics.of_game(draft).sheets[proposal.subject_id]
        subject = draft.world.require(proposal.subject_id)
        # Sequential against the live sheet, so a rewrite may name what an earlier change wrote.
        return tuple(
            _rewrite(sheet, subject, change, proposal.why)
            if change.kind == "rewrite"
            else _gain(sheet, subject, change, proposal.why)
            for change in proposal.changes
        )


def _gain(sheet: Sheet, subject: Entity, change: Change, why: str) -> Fact:
    if change.tag in (*sheet.skills, *sheet.gear, *sheet.frailties):
        raise ValueError(f"{subject.name} already has the tag {change.tag!r}")
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
        event=MechanicEvent(
            title=f"{subject.name}: new {change.kind} {change.tag}", icon="military_tech"
        ),
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
        event=MechanicEvent(title=f"{subject.name}: {old} → {new}", icon="military_tech"),
    )


def pack_meanings(
    entries: Sequence[PackChoice], tags: Sequence[str]
) -> tuple[tuple[str, str], ...]:
    detail_of = {entry.label: entry.detail for entry in entries if entry.detail}
    return tuple((tag, detail_of[tag]) for tag in tags if tag in detail_of)


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

    def create(self, name: str, brief: str, picks: Picks, rng: Random) -> CreatedCharacter:
        del rng
        check_picks(self.steps(picks), picks)
        chosen = picked(picks, "pack")[0]
        pack = self.packs[chosen]
        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief),
            rules={
                "packs": character_packs(chosen),
                "twist_pack": chosen,
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
    pack_type = Pack
    decisions = (Conflict,)
    authoring_instructions = (
        "LONER 3E AUTHORING\n"
        "Every actor needs a rules object with a concept and any fitting skills, frailties, or "
        "gear. Loner tags are freeform descriptions: use selected pack entries when they fit and "
        "invent scenario-specific tags when they are clearer. Set packs to every selected table "
        "set the entity uses; twist_pack chooses its one Oracle table."
    )

    def __init__(self, sources: PackSources = SHIPPED_PACKS) -> None:
        super().__init__(sources)
        self.packs = sources.load(self.engine_dir / "packs", Pack)
        self.advancement = Loner3eAdvancement()
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
            self.advancement.command(),
        )

    def pack_models(self) -> Mapping[str, Pack]:
        return self.packs

    def uses_sheet(self, entity: Entity) -> bool:
        return entity.kind == "actor" or bool(entity.rules)

    def check_scenario(self, scenario: Scenario) -> None:
        if blank := sorted(
            entity.id for entity in scenario.world.of_kind("actor") if not entity.rules
        ):
            raise ValueError(f"authored Loner actors carry no `rules`: {blank}")
        super().check_scenario(scenario)

    def meanings(self, sheet: Sheet) -> tuple[tuple[str, str], ...]:
        packs = tuple(self.packs[pack_id] for pack_id in sheet.packs)
        # The concept's pack blurb is generic where the entity's own brief is not: skip it.
        return pack_meanings(
            tuple(entry for pack in packs for entry in (*pack.skills, *pack.frailties, *pack.gear)),
            (*sheet.skills, *sheet.frailties, *sheet.gear),
        )

    def twists(self, state: Game) -> tuple[tuple[str, str], ...]:
        return twist_table(self.packs, Mechanics.of_game(state).sheets[state.player_id].twist_pack)
