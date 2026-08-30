from collections.abc import Mapping, Sequence
from functools import partial
from pathlib import Path
from random import Random

from pydantic import Field

from aidm.content.io import engine_text
from aidm.content.model import Character
from aidm.engines.core import (
    ADVANCE_SPENT,
    Engine,
    EntityRenderer,
    Mechanics,
    PackCreation,
    authoring_guidance,
    check_packs,
    describe_rows,
    find_entry,
    load_packs,
    mechanics_merged,
    mechanics_of,
    party_member,
    rules,
    sheet_of,
)
from aidm.engines.loner3e.rules import (
    GROWTH,
    AdventureGrowth,
    Change,
    Loner3eState,
    Pack,
    Question,
    Sheet,
    apply_restore_luck,
    resolve_question,
    twist_table,
)
from aidm.state.creation import CreationStep, Picks, check_picks, numbered_steps, picked
from aidm.state.entities import (
    PLAYER_ID,
    CheckedEntityId,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    Slug,
    slug,
)
from aidm.state.facts import Fact, entity_fact
from aidm.state.model import Game
from aidm.state.play import DecisionOption
from aidm.state.threads import ADVANCE_THREAD
from aidm.state.tools import NoArgs, director_tool
from aidm.world.authoring import rooms_brief, rooms_growth_due
from aidm.world.scene import rooms_scene
from aidm.world.succession import TAKE_OVER, player_over
from aidm.world.tools import (
    ADD_TRAIT,
    DIRECTOR_WORLD,
    GAIN_IMPROVISED_ITEM,
    JOIN_PARTY,
    LEAVE_PARTY,
    MOVE,
    REMOVE_TRAIT,
    REVEAL,
    UNLOCK_EXIT,
    kill_tool,
)
from aidm.world.topology import validate_rooms

ENGINE_DIR = Path(__file__).parent


class RestoreLuck(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or an actor here.")


def complete_chapter(draft: Game) -> tuple[Fact, ...]:
    """Only those who played the chapter are credited with it: nobody is owed one they missed."""
    ending = "the adventure has ended"
    with rules(draft.world, Loner3eState) as game:
        for member_id in (draft.player_id, *draft.world.party):
            sheet = game.sheets.get(member_id)
            if sheet is not None:
                sheet.chapters += 1
    return (Fact(kind="chapter_completed", trace=ending, told=True, card=ending),)


def advance(draft: Game, proposal: AdventureGrowth, rng: Random) -> tuple[Fact, ...]:
    """One advance per adventure a party member played: the tags it rewrote or grew."""
    del rng
    with rules(draft.world, Loner3eState) as game:
        subject = party_member(draft, proposal.subject_id)
        sheet = sheet_of(game.sheets, subject)
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
            card=f"{subject.name}: milestone {sheet.milestones} spent",
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
        card=f"{subject.name}: new {change.kind} {change.tag}",
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
        card=f"{subject.name}: {old} → {new}",
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
        sheet = Sheet(
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
            mechanics=Loner3eState(sheets={PLAYER_ID: sheet}, twist_pack=chosen).model_dump(
                mode="json"
            ),
        )


def _validate(packs: Mapping[str, Pack], state: Game) -> None:
    check_packs(packs, state)
    validate_rooms(state.world)
    game = mechanics_of(state.world, Loner3eState)
    if stray := sorted(set(game.sheets) - set(state.world.entities)):
        raise ValueError(f"mechanics.sheets names entities the world does not hold: {stray}")
    # Every actor rolls by a sheet: one nobody wrote is refused, not given a blank one.
    for actor in state.world.of_kind("actor"):
        if actor.id not in game.sheets:
            raise ValueError(f"{actor.id!r} has no sheet; a Loner actor needs one")
    if game.twist_pack is not None and game.twist_pack not in state.packs:
        raise ValueError(f"twists roll from {game.twist_pack!r}, which is unselected")


def meanings(
    packs: Mapping[str, Pack], selected: Sequence[Slug], sheet: Sheet
) -> tuple[tuple[str, str], ...]:
    chosen = tuple(packs[pack_id] for pack_id in selected)
    # The concept's pack blurb is generic where the entity's own brief is not: skip it.
    return pack_meanings(
        tuple(entry for pack in chosen for entry in (*pack.skills, *pack.frailties, *pack.gear)),
        (*sheet.skills, *sheet.frailties, *sheet.gear),
    )


def describer(packs: Mapping[str, Pack], state: Game) -> EntityRenderer:
    """One parse of the blob per scene; an entity without a sheet is scenery, not mechanics."""
    game = mechanics_of(state.world, Loner3eState)

    def describe(entity: Entity) -> str:
        sheet = game.sheets.get(entity.id)
        if sheet is None:
            return ""
        return describe_rows(sheet.rows(), meanings(packs, state.packs, sheet))

    return describe


def advances_owed(state: Game) -> tuple[tuple[str, str], ...]:
    """Chapters played standing above the ledger of advances taken, one note each."""
    # An advance mid-suspension could invalidate the frozen call an open decision holds.
    if state.pending is not None:
        return ()
    game = mechanics_of(state.world, Loner3eState)
    owed = [
        f"- {state.world.require(one).name} has an advance owed; call advance only when the "
        "player asks for it."
        for one in (state.player_id, *state.world.party)
        if (sheet := game.sheets.get(one)) is not None and sheet.chapters > sheet.milestones
    ]
    return (("ADVANCES OWED", "\n".join(owed)),) if owed else ()


def sheet_rows(state: Game) -> tuple[tuple[str, str], ...]:
    return sheet_of(mechanics_of(state.world, Loner3eState).sheets, state.player).rows()


def twists(packs: Mapping[str, Pack], state: Game) -> tuple[tuple[str, str], ...]:
    chosen = mechanics_of(state.world, Loner3eState).twist_pack
    return twist_table(packs, chosen or state.packs[0])


_AUTHORING = (
    "LONER 3E AUTHORING\n"
    "Every actor needs a sheet in `mechanics.sheets` under its exact entity id, with a "
    "concept and any fitting skills, frailties, or gear. Loner tags are freeform "
    "descriptions: use selected pack entries when they fit and invent scenario-specific "
    "tags when they are clearer. twist_pack names one selected table set; its Oracle "
    "twists are rolled from it."
)


def build(user_packs: Path) -> Engine:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    validate = partial(_validate, packs)
    describe = partial(describer, packs)
    return Engine(
        id=EngineId("loner3e"),
        title="LONER 3E",
        instructions=f"{DIRECTOR_WORLD}\n\n{engine_text(ENGINE_DIR / 'director.md')}",
        packs=packs,
        creation=Loner3eCreation(packs),
        validate=validate,
        over=player_over,
        scene=rooms_scene(describe, advances_owed),
        sheet_rows=sheet_rows,
        mechanics_merge=partial(mechanics_merged, Loner3eState),
        mechanics_without=_without,
        resolvers=(TAKE_OVER,),
        authoring_brief=lambda chosen, base, opening: rooms_brief(
            base, opening, authoring_guidance(_AUTHORING, packs, chosen)
        ),
        growth_due=rooms_growth_due,
        tools=(
            REVEAL,
            MOVE,
            GAIN_IMPROVISED_ITEM,
            ADD_TRAIT,
            REMOVE_TRAIT,
            kill_tool(validate),
            UNLOCK_EXIT,
            JOIN_PARTY,
            LEAVE_PARTY,
            ADVANCE_THREAD,
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
            director_tool(
                "complete_chapter",
                "Record that the current adventure has ended.",
                NoArgs,
                lambda draft, _args, _rng: complete_chapter(draft),
            ),
            director_tool("advance", ADVANCE_SPENT + GROWTH, AdventureGrowth, advance),
        ),
    )


def _without(blob: Mechanics, entity_id: EntityId) -> Mechanics:
    game = Loner3eState.model_validate(blob)
    _ = game.sheets.pop(entity_id, None)
    return game.model_dump(mode="json")
