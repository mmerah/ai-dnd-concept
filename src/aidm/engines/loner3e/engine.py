import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from functools import partial
from pathlib import Path
from random import Random

from pydantic import Field

from aidm.content.io import engine_text
from aidm.engines.core import CharacterCreation, Engine, load_packs
from aidm.engines.loner3e.rules import (
    GROWTH,
    Actor,
    AdventureGrowth,
    Change,
    Pack,
    Question,
    actor_sheet,
    apply_restore_luck,
    close_conflicts,
    resolve_question,
    twist_table,
)
from aidm.engines.loner3e.state import (
    ActorSheet,
    Loner3eCharacter,
    Loner3eState,
    LonerSheet,
)
from aidm.kernel.views import CreationPreview
from aidm.kits.scenes.state import Entity, SceneState, entity_fact
from aidm.kits.scenes.tools import scene_tools
from aidm.kits.scenes.views import SheetRows
from aidm.state.creation import CreationStep, Picks, check_picks, picked
from aidm.state.entities import (
    DEAD,
    PLAYER_ID,
    CheckedEntityId,
    EngineId,
    EntityId,
    Frozen,
    Slug,
    slug,
)
from aidm.state.facts import Fact
from aidm.state.model import Character, Game, Scenario
from aidm.state.play import DecisionOption
from aidm.state.tools import NoArgs, master_tool

ENGINE_DIR = Path(__file__).parent


class RestoreLuck(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or an actor here.")


ADVANCE_SPENT = "Spend one advance a party member has earned, when the player asks for it. "


def party(state: Game) -> tuple[EntityId, ...]:
    return (state.world.player_id, *state.world.companions)


def check_packs(packs: Mapping[str, Pack], state: Game) -> None:
    if missing := sorted(set(state.packs) - set(packs)):
        raise ValueError(f"the game names packs not installed: {missing}")


def find_entry(entries: Sequence[DecisionOption], chosen: str) -> DecisionOption:
    return next(entry for entry in entries if entry.id == chosen)


def party_member(draft: Game, subject_id: EntityId) -> Actor:
    """An advance is a party member's own: nobody else's sheet is an engine's to grow."""
    subject = draft.world.require(subject_id)
    if subject_id not in party(draft):
        raise ValueError(f"{subject.name} is not in the party")
    return subject


def advances_owed(state: Game) -> tuple[tuple[str, str], ...]:
    """Chapters played standing above the ledger of advances taken, one note each."""
    # An advance mid-suspension could invalidate the frozen call an open decision holds.
    if state.pending is not None:
        return ()
    owed = [
        f"- {state.world.require(one).name} has an advance owed; call advance only when the "
        "player asks for it."
        for one in party(state)
        if _advance_owed(state, one)
    ]
    return (("ADVANCES OWED", "\n".join(owed)),) if owed else ()


def complete_chapter(draft: Game) -> tuple[Fact, ...]:
    """Only those who played the chapter are credited with it: nobody is owed one they missed."""
    ending = "the adventure has ended"
    for member_id in party(draft):
        sheet = draft.world.require(member_id).sheet
        if isinstance(sheet, ActorSheet):
            sheet.chapters += 1
    return (Fact(kind="chapter_completed", trace=ending, told=True, card=ending),)


def advance(draft: Game, proposal: AdventureGrowth, rng: Random) -> tuple[Fact, ...]:
    """One advance per adventure a party member played: the tags it rewrote or grew."""
    del rng
    subject: Actor = party_member(draft, proposal.subject_id)
    sheet = actor_sheet(subject)
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
        f"{draft.world.label(subject)} milestones -> {sheet.milestones} (a milestone spent)",
        card=f"{subject.name}: milestone {sheet.milestones} spent",
    )
    return (*granted, spent)


def _gain(sheet: ActorSheet, subject: Actor, change: Change) -> Fact:
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
        card=f"{subject.name}: new {change.kind} {change.tag}",
    )


def _rewrite(sheet: ActorSheet, subject: Actor, change: Change) -> Fact:
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
        card=f"{subject.name}: {old} → {new}",
    )


def pack_meanings(
    entries: Sequence[DecisionOption], tags: Sequence[str]
) -> tuple[tuple[str, str], ...]:
    detail_of = {entry.label: entry.detail for entry in entries if entry.detail}
    return tuple((tag, detail_of[tag]) for tag in tags if tag in detail_of)


def _swapped(tags: tuple[str, ...], old: str, new: str) -> tuple[str, ...]:
    return tuple(new if tag == old else tag for tag in tags)


def other_than(options: Sequence[DecisionOption], taken: str) -> tuple[DecisionOption, ...]:
    return tuple(option for option in options if option.id != taken)


def pack_options(packs: Mapping[str, Pack]) -> tuple[DecisionOption, ...]:
    return tuple(DecisionOption(id=key, label=one.name) for key, one in packs.items())


class Loner3eCreation(CharacterCreation):
    def __init__(self, packs: Mapping[str, Pack]) -> None:
        self.packs = packs

    def steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        first = CreationStep(
            id="pack", prompt="Choose a character table set", options=pack_options(self.packs)
        )
        pack = self.packs.get(picked(picks, "pack"))
        if pack is None:
            return (first,)
        return (
            first,
            CreationStep(
                id="concept",
                prompt="Write a one-line concept",
                hint=", ".join(entry.label for entry in pack.concepts[:3]),
            ),
            CreationStep(id="skill-1", prompt="Choose skill 1", options=pack.skills),
            CreationStep(
                id="skill-2",
                prompt="Choose skill 2",
                options=other_than(pack.skills, picked(picks, "skill-1")),
            ),
            CreationStep(id="frailty", prompt="Choose a frailty", options=pack.frailties),
            CreationStep(id="gear-1", prompt="Choose gear 1", options=pack.gear),
            CreationStep(
                id="gear-2",
                prompt="Choose gear 2",
                options=other_than(pack.gear, picked(picks, "gear-1")),
            ),
        )

    def create(self, name: str, brief: str, picks: Picks) -> Character:
        check_picks(self.steps(picks), picks)
        chosen = picked(picks, "pack")
        pack = self.packs[chosen]
        sheet = ActorSheet(
            concept=picked(picks, "concept"),
            skills=tuple(
                find_entry(pack.skills, picked(picks, f"skill-{one}")).label for one in (1, 2)
            ),
            frailties=(find_entry(pack.frailties, picked(picks, "frailty")).label,),
            gear=tuple(find_entry(pack.gear, picked(picks, f"gear-{one}")).label for one in (1, 2)),
        )
        return Character(
            id=slug(name, ()),
            engine=EngineId("loner3e"),
            name=name,
            brief=brief,
            payload=Loner3eCharacter(sheet=sheet, twist_pack=chosen),
        )

    def preview(self, character: Character) -> CreationPreview:
        return CreationPreview(rows=character.payload.sheet.rows())


def new_game(scenario: Scenario, character: Character) -> Loner3eState:
    """The player is added by code and never authored, so no scenario can claim their id."""
    canon = deepcopy(scenario.payload.world)
    if PLAYER_ID in canon.cast:
        raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
    cast: dict[EntityId, Entity[LonerSheet]] = dict(canon.cast)
    cast[PLAYER_ID] = Entity[LonerSheet](
        id=PLAYER_ID,
        kind="actor",
        name=character.name,
        brief=character.brief,
        known=True,
        sheet=character.payload.sheet,
    )
    opening = canon.opening.model_copy(update={"present": (PLAYER_ID, *canon.opening.present)})
    world = SceneState[LonerSheet](
        cast=cast,
        current=opening,
        threads=canon.threads,
        player_id=PLAYER_ID,
        source=canon.source,
    )
    return Loner3eState(world=world, twist_pack=character.payload.twist_pack)


def _validate(packs: Mapping[str, Pack], state: Game) -> None:
    check_packs(packs, state)
    world = state.world
    # Every actor rolls by a sheet: one nobody wrote is refused, not given a blank one.
    for one in world.cast.values():
        if one.kind == "actor" and not isinstance(one.sheet, ActorSheet):
            raise ValueError(f"{one.id!r} has no sheet; a Loner actor needs one")
    twist_pack = state.payload.twist_pack
    if twist_pack is not None and twist_pack not in state.packs:
        raise ValueError(f"twists roll from {twist_pack!r}, which is unselected")


def meanings(
    packs: Mapping[str, Pack], selected: Sequence[Slug], sheet: ActorSheet
) -> tuple[tuple[str, str], ...]:
    chosen = tuple(packs[pack_id] for pack_id in selected)
    # The concept's pack blurb is generic where the entity's own brief is not: skip it.
    return pack_meanings(
        tuple(entry for pack in chosen for entry in (*pack.skills, *pack.frailties, *pack.gear)),
        (*sheet.skills, *sheet.frailties, *sheet.gear),
    )


def sheet_rows(state: Game) -> SheetRows:
    def rows(entity_id: EntityId) -> tuple[tuple[str, str], ...]:
        sheet = state.world.require(entity_id).sheet
        return () if sheet is None else sheet.rows()

    return rows


def engine_sections(packs: Mapping[str, Pack], state: Game) -> tuple[tuple[str, str], ...]:
    """A glossary of the tags in play, plus any advance the party is owed. The sheets themselves
    are already on the entity lines."""
    glossary: dict[str, str] = {}
    for one in state.world.here():
        if isinstance(sheet := one.sheet, ActorSheet):
            glossary.update(meanings(packs, state.packs, sheet))
    lines = "\n".join(f"- {tag}: {detail}" for tag, detail in glossary.items())
    spelled = (("WHAT THE TAGS IN PLAY MEAN", lines),) if glossary else ()
    return (*spelled, *advances_owed(state))


def _advance_owed(state: Game, entity_id: EntityId) -> bool:
    sheet = state.world.require(entity_id).sheet
    return isinstance(sheet, ActorSheet) and sheet.chapters > sheet.milestones


def twists(packs: Mapping[str, Pack], state: Game) -> tuple[tuple[str, str], ...]:
    return twist_table(packs, state.payload.twist_pack or state.packs[0])


_AUTHORING = (
    "LONER 3E AUTHORING\n"
    "Every actor needs an `actor` sheet with a concept and any fitting skills, frailties, or "
    "gear. Anything that can resist without a will of its own takes an `item` sheet, which is "
    "luck alone. Loner tags are freeform descriptions: use selected pack entries when they fit "
    "and invent scenario-specific tags when they are clearer. Only a pack tag carries a meaning "
    "the game master can look up, so an invented tag that does not say what it does needs one "
    "sentence in that entity's `description`: positions are judged from it."
)


def guidance(packs: Mapping[str, Pack], selected_ids: Sequence[Slug]) -> str:
    """The packs are the setting's vocabulary, so the worldsmith reads the ones this game selected.
    Defaults restate rules the guidance already carries; dropping them halves the prompt."""
    selected = {
        one: packs[one].model_dump(mode="json", exclude_defaults=True) for one in selected_ids
    }
    return f"{_AUTHORING}\n\nSELECTED PACK CONTENT\n{json.dumps(selected)}"


def player_over(state: Game) -> str | None:
    return "You died." if state.world.player.trait(DEAD) is not None else None


def build(user_packs: Path) -> Engine:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    return Engine(
        id=EngineId("loner3e"),
        title="LONER 3E",
        instructions=engine_text(ENGINE_DIR / "rules.md"),
        packs=pack_options(packs),
        guidance=partial(guidance, packs),
        creation=Loner3eCreation(packs),
        validate=partial(_validate, packs),
        new_game=new_game,
        sheet_rows=sheet_rows,
        sections=partial(engine_sections, packs),
        over=player_over,
        scene_closed=close_conflicts,
        tools=scene_tools(
            master_tool(
                "roll_question",
                "Roll Chance against Risk for one closed dramatic question.",
                Question,
                lambda draft, one, rng: resolve_question(draft, one, rng, twists(packs, draft)),
            ),
            master_tool(
                "restore_luck",
                "Restore an actor's luck after a conflict ends.",
                RestoreLuck,
                lambda draft, one, _rng: apply_restore_luck(draft, one.actor_id),
            ),
            master_tool(
                "complete_chapter",
                "Record that the current adventure has ended.",
                NoArgs,
                lambda draft, _args, _rng: complete_chapter(draft),
            ),
            master_tool("advance", ADVANCE_SPENT + GROWTH, AdventureGrowth, advance),
        ),
    )
