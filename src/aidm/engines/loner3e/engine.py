from collections.abc import Mapping, Sequence
from pathlib import Path
from random import Random

from pydantic import Field

from aidm.content.io import engine_text
from aidm.content.model import Character, CharacterProfile
from aidm.engines.core import (
    ADVANCE_TOOL,
    Engine,
    EntityRules,
    NoRules,
    PackCreation,
    advances_owed,
    chapter_tool,
    describe_rows,
    director_tool,
    find_entry,
    load_packs,
    party_member,
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
from aidm.engines.world import CORE_TOOLS
from aidm.state.creation import CreationStep, Picks, check_picks, numbered_steps, picked
from aidm.state.entities import (
    CheckedEntityId,
    EngineId,
    Entity,
    Frozen,
    Kind,
    Slug,
    slug,
)
from aidm.state.facts import Fact, MechanicEvent, entity_fact
from aidm.state.model import Game
from aidm.state.play import DecisionOption

ENGINE_DIR = Path(__file__).parent
# SRD "Everything is a Character": a thing that resists plays by the one sheet an actor does.
RULES_TYPES: Mapping[Kind, type[EntityRules]] = {
    "actor": Sheet,
    "item": Sheet,
    "location": NoRules,
}


class RestoreLuck(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or an actor here.")


def advance(draft: Game, proposal: AdventureGrowth, rng: Random) -> tuple[Fact, ...]:
    """One advance per adventure a party member played: the tags it rewrote or grew."""
    del rng
    subject = party_member(draft, proposal.subject_id)
    with rules(subject, Sheet) as sheet:
        if sheet.chapters <= sheet.milestones:
            raise ValueError(f"{subject.name} has no advance owed")
        # Sequential against the live sheet, so a rewrite may name what an earlier change wrote.
        granted = tuple(
            _rewrite(sheet, subject, change)
            if change.kind == "rewrite"
            else _gain(sheet, subject, change)
            for change in proposal.changes
        )
        sheet.milestones += 1
        spent = entity_fact(
            subject,
            "milestone_spent",
            f"{draft.label(subject)} milestones -> {sheet.milestones} (a milestone spent)",
            event=MechanicEvent(
                title=f"{subject.name}: milestone {sheet.milestones} spent", icon="military_tech"
            ),
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
    return entity_fact(
        subject,
        f"{change.kind}_gained",
        f"{subject.name} gained {change.kind} {change.tag} ({change.why})",
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
    return entity_fact(
        subject,
        "tag_rewritten",
        f"{subject.name} rewrote {old} as {new} ({change.why})",
        event=MechanicEvent(title=f"{subject.name}: {old} → {new}", icon="military_tech"),
    )


def pack_meanings(
    entries: Sequence[DecisionOption], tags: Sequence[str]
) -> tuple[tuple[str, str], ...]:
    detail_of = {entry.label: entry.detail for entry in entries if entry.detail}
    return tuple((tag, detail_of[tag]) for tag in tags if tag in detail_of)


def _swapped(tags: tuple[str, ...], old: str, new: str) -> tuple[str, ...]:
    return tuple(new if tag == old else tag for tag in tags)


class Loner3eCreation(PackCreation[Pack]):
    def steps_for(self, pack: Pack, picks: Picks) -> tuple[CreationStep, ...]:
        return (
            CreationStep(
                id="concept",
                prompt="Write a one-line concept",
                hint=", ".join(entry.label for entry in pack.concepts[:3]),
            ),
            *numbered_steps("skill", "Choose skill", 2, pack.skills, distinct_from=picks),
            CreationStep(id="frailty", prompt="Choose a frailty", options=pack.frailties),
            *numbered_steps("gear", "Choose gear", 2, pack.gear, distinct_from=picks),
        )

    def create(self, name: str, brief: str, picks: Picks) -> Character:
        check_picks(self.steps(picks), picks)
        chosen = picked(picks, "pack")
        pack = self.packs[chosen]
        return Character(
            id=slug(name, ()),
            profile=CharacterProfile(name=name, brief=brief),
            rules={
                "twist_pack": chosen,
                "concept": picked(picks, "concept"),
                "skills": [
                    find_entry(pack.skills, picked(picks, f"skill-{one}")).label for one in (1, 2)
                ],
                "frailties": [find_entry(pack.frailties, picked(picks, "frailty")).label],
                "gear": [
                    find_entry(pack.gear, picked(picks, f"gear-{one}")).label for one in (1, 2)
                ],
            },
        )


def _checks(state: Game) -> None:
    # Every actor rolls by a sheet: one nobody wrote is refused, not given a blank one.
    for actor in state.world.of_kind("actor"):
        if not actor.rules:
            raise ValueError(f"{actor.id!r} has no rules; a Loner actor needs a sheet")
        twist_pack = Sheet.model_validate(actor.rules).twist_pack
        if twist_pack not in state.packs:
            raise ValueError(f"{actor.id!r} rolls twists from {twist_pack!r}, which is unselected")


def meanings(
    packs: Mapping[str, Pack], selected: Sequence[Slug], sheet: Sheet
) -> tuple[tuple[str, str], ...]:
    chosen = tuple(packs[pack_id] for pack_id in selected)
    # The concept's pack blurb is generic where the entity's own brief is not: skip it.
    return pack_meanings(
        tuple(entry for pack in chosen for entry in (*pack.skills, *pack.frailties, *pack.gear)),
        (*sheet.skills, *sheet.frailties, *sheet.gear),
    )


def _describe(packs: Mapping[str, Pack], state: Game, entity: Entity) -> str:
    # An item is described only once play has written rules on it; before that it is scenery.
    if entity.kind != "actor" and not entity.rules:
        return ""
    sheet = Sheet.model_validate(entity.rules)
    return describe_rows(sheet.rows(), meanings(packs, state.packs, sheet))


def twists(packs: Mapping[str, Pack], state: Game) -> tuple[tuple[str, str], ...]:
    return twist_table(packs, Sheet.model_validate(state.player.rules).twist_pack)


def build(user_packs: Path) -> Engine:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    return Engine(
        id=EngineId("loner3e"),
        badge=("LONER 3E", "teal-7"),
        director_instructions=engine_text(ENGINE_DIR / "director.md"),
        rules_types=RULES_TYPES,
        packs=packs,
        creation=Loner3eCreation(packs),
        checks=_checks,
        describe=lambda state, entity: _describe(packs, state, entity),
        decisions=(Conflict,),
        owed_notes=lambda state: advances_owed(state, Sheet, lambda sheet: sheet.milestones),
        authoring_instructions=(
            "LONER 3E AUTHORING\n"
            "Every actor needs a rules object with a concept and any fitting skills, frailties, or "
            "gear. Loner tags are freeform descriptions: use selected pack entries when they fit "
            "and invent scenario-specific tags when they are clearer. twist_pack names one "
            "selected table set; its Oracle twists are rolled from it."
        ),
        director_tools=(
            *CORE_TOOLS,
            director_tool(
                "roll_question",
                "Roll Chance against Risk for one closed dramatic question.",
                Question,
                lambda draft, one, rng: resolve_question(draft, one, rng, twists(packs, draft)),
            ),
            director_tool(
                "restore_luck",
                "Restore an actor's luck after a conflict ends.",
                RestoreLuck,
                lambda draft, one, _rng: apply_restore_luck(draft, one.actor_id),
            ),
            chapter_tool(
                "Record that the current adventure has ended.", "the adventure has ended", Sheet
            ),
            director_tool("advance", ADVANCE_TOOL + GROWTH, AdventureGrowth, advance),
        ),
    )
