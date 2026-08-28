from collections.abc import Mapping, Sequence
from pathlib import Path
from random import Random
from typing import ClassVar

from pydantic import Field

from aidm.content.model import CharacterProfile, CreatedCharacter
from aidm.engines.core import (
    ADVANCE_TOOL,
    Engine,
    EntityRules,
    NoRules,
    action,
    advances_owed,
    chapter_command,
    counter_fact,
    describe_rows,
    party_member,
    rule,
    rules,
)
from aidm.engines.loner3e.rules import (
    GROWTH,
    AdventureGrowth,
    Change,
    Conflict,
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
    EngineId,
    Entity,
    Frozen,
    Kind,
)
from aidm.state.facts import Fact, MechanicEvent, explained_fact
from aidm.state.model import Game


class RestoreLuck(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or an actor here.")


def advance(draft: Game, proposal: AdventureGrowth, rng: Random) -> tuple[Fact, ...]:
    """One advance per adventure a party member played: the tags it rewrote or grew."""
    del rng
    subject = party_member(draft, proposal.subject_id)
    with rules(subject, Sheet) as sheet:
        if sheet.chapters.current <= sheet.milestones.current:
            raise ValueError(f"{subject.name} has no advance owed")
        # Sequential against the live sheet, so a rewrite may name what an earlier change wrote.
        granted = tuple(
            _rewrite(sheet, subject, change)
            if change.kind == "rewrite"
            else _gain(sheet, subject, change)
            for change in proposal.changes
        )
        sheet.milestones.current += 1
        spent = counter_fact(
            draft, subject, "milestones", sheet.milestones, 1, "a milestone spent", "military_tech"
        )
    return (*granted, spent)


def _gain(sheet: Sheet, subject: Entity, change: Change) -> Fact:
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
        change.why,
        event=MechanicEvent(
            title=f"{subject.name}: new {change.kind} {change.tag}", icon="military_tech"
        ),
    )


def _rewrite(sheet: Sheet, subject: Entity, change: Change) -> Fact:
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
        change.why,
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


class Loner3eEngine(Engine):
    id = EngineId("loner3e")
    badge = ("LONER 3E", "teal-7")
    engine_dir = Path(__file__).parent
    # SRD "Everything is a Character": a thing that resists plays by the one sheet an actor does.
    rules_types: ClassVar[Mapping[Kind, type[EntityRules]]] = {
        "actor": Sheet,
        "item": Sheet,
        "location": NoRules,
    }
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
                "Record that the current adventure has ended.", "the adventure has ended", Sheet
            ),
            rule("advance", ADVANCE_TOOL + GROWTH, AdventureGrowth, advance),
        )

    def pack_models(self) -> Mapping[str, Pack]:
        return self.packs

    def describe(self, entity: Entity) -> str:
        # An item is described only once play has written rules on it; before that it is scenery.
        if entity.kind != "actor" and not entity.rules:
            return ""
        sheet = Sheet.model_validate(entity.rules)
        return describe_rows(sheet.rows(), self.meanings(sheet))

    def owed_notes(self, state: Game) -> tuple[str, ...]:
        return advances_owed(state, Sheet, lambda sheet: sheet.milestones)

    def meanings(self, sheet: Sheet) -> tuple[tuple[str, str], ...]:
        packs = tuple(self.packs[pack_id] for pack_id in sheet.packs)
        # The concept's pack blurb is generic where the entity's own brief is not: skip it.
        return pack_meanings(
            tuple(entry for pack in packs for entry in (*pack.skills, *pack.frailties, *pack.gear)),
            (*sheet.skills, *sheet.frailties, *sheet.gear),
        )

    def twists(self, state: Game) -> tuple[tuple[str, str], ...]:
        return twist_table(self.packs, Sheet.model_validate(state.player.rules).twist_pack)
