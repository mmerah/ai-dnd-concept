from collections.abc import Mapping
from random import Random
from typing import Literal

from pydantic import Field

from aidm.engines.actions import Action
from aidm.engines.loader import Engine
from aidm.engines.sheets import require_sheet
from aidm.engines.tags import carriers, tag_key
from aidm.state.apply import apply_effect, require_actor_here
from aidm.state.base import PLAYER_ID, Entity, EntityId, Slug
from aidm.state.dice import roll_pool
from aidm.state.effects import Reveal
from aidm.state.facts import Fact, entity_fact
from aidm.state.plan import Branched, Flow, Resolution
from aidm.state.world import GameState

from .mechanics import DEFAULT_FACE, HINDERED_FACE, Mechanics, Sheet, TwentyfourxxEffect

TROUBLE = 2  # 1-2 on the bad-luck die
SIGNS = 4  # 3-4 on the bad-luck die


class Attempt(Action):
    """One risky attempt, answered by the highest die of a pool."""

    outcomes = frozenset[Slug]({"disaster", "setback", "success"})

    act: Literal["attempt"] = "attempt"
    actor_id: EntityId = Field(
        description="Exact id of the actor attempting this: the player, or an actor here."
    )
    goal: str = Field(
        min_length=1,
        description="What the actor is trying to do and what they risk by trying, in one line.",
    )
    skill: str = Field(
        default="",
        description="The skill on the actor's sheet this calls on, copied exactly as it is "
        "written there. Empty when none of theirs applies: they roll the bare d6.",
    )
    helped: str = Field(
        default="",
        description="One tag in the scene that makes this easier — a trait on the actor, on "
        "what they carry, on where they stand, or on who stands there with them — copied "
        "exactly. Empty when nothing helps; you cannot invent one.",
    )
    hindered: str = Field(
        default="",
        description="One tag in the scene that makes this harder, copied the same way. Empty "
        "when nothing hinders.",
    )
    luck_test: str = Field(
        default="",
        description="What bad luck might arrive alongside this — running out of ammo, running "
        "into guards. The engine rolls whether it does. Empty for no test.",
    )

    def resolve(self, engine: Engine, draft: GameState, rng: Random) -> Resolution:
        del engine
        return resolve_attempt(draft, self, rng)


class TurnPlan(Branched[TwentyfourxxEffect, Attempt]):
    action: Attempt | None = Field(
        default=None,
        description="The one attempt this turn resolves, or null when nothing the player does "
        "is risky enough to roll.",
    )


def outcome_for(kept: int) -> Slug:
    if kept <= 2:
        return "disaster"
    if kept <= 4:
        return "setback"
    return "success"


def pool_faces(sheet: Sheet, action: Attempt) -> tuple[int, ...]:
    """Hindrance drops the die to a d4; help adds one d6, and never more than one."""
    base = HINDERED_FACE if action.hindered else sheet.face(action.skill)
    return (base, DEFAULT_FACE) if action.helped else (base,)


def resolve_attempt(draft: GameState, action: Attempt, rng: Random) -> Resolution:
    actor = require_actor_here(draft, action.actor_id)
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    sheet = require_sheet(draft.mechanics_as(Mechanics).sheets, actor)
    known = _known_tags(draft, actor)
    _refuse_unless_ready(actor, action, sheet, known)

    faces = pool_faces(sheet, action)
    kept, rolled = roll_pool(faces, f"{action.goal} — {action.skill or 'no skill'}", rng)
    facts.append(rolled)

    outcome = outcome_for(kept)
    facts.append(
        entity_fact(
            actor,
            "attempt_resolved",
            f"{action.goal} -> {outcome}",
            {"outcome": outcome, "kept": kept, "skill": action.skill, "faces": list(faces)},
        )
    )

    flow: Flow = (
        "yield-to-player" if outcome == "disaster" and actor.id == PLAYER_ID else "continue"
    )
    if action.luck_test:
        tested, trouble = _bad_luck(draft, actor, action.luck_test, rng)
        facts.extend(tested)
        if trouble:
            flow = "yield-to-player"
    return Resolution(facts=tuple(facts), outcome=outcome, flow=flow)


def _known_tags(draft: GameState, actor: Entity) -> dict[str, str]:
    known: dict[str, str] = {}
    for carrier in carriers(draft, actor):
        for trait in carrier.traits:
            known[tag_key(trait.id)] = trait.name
            known[tag_key(trait.name)] = trait.name
    return known


def _refuse_unless_ready(
    actor: Entity, action: Attempt, sheet: Sheet, known: Mapping[str, str]
) -> None:
    if action.skill and action.skill not in sheet.skills:
        written = ", ".join(sorted(sheet.skills)) or "(none)"
        raise ValueError(
            f"{actor.name} has no skill {action.skill!r}. Their skills are: {written}. Leave "
            "`skill` empty to roll the bare d6."
        )
    for tag in (action.helped, action.hindered):
        if tag and tag_key(tag) not in known:
            written = ", ".join(sorted(set(known.values()))) or "(none)"
            raise ValueError(
                f"nothing in this scene is tagged {tag!r}. The tags in play are: {written}"
            )


def _bad_luck(
    draft: GameState, actor: Entity, subject: str, rng: Random
) -> tuple[list[Fact], bool]:
    kept, rolled = roll_pool((6,), f"bad luck — {subject}", rng)
    if kept > SIGNS:
        return [rolled], False
    trouble = kept <= TROUBLE
    note = (
        f"Bad luck has caught up with them: {subject} — the narration showed it arriving this "
        "turn. Develop it next: what it costs, what it changes."
        if trouble
        else f"Bad luck is circling: signs of {subject} showed this turn. Let the scene warn of "
        "it before it bites."
    )
    draft.world.pending_notes = (*draft.world.pending_notes, note)
    label = "trouble" if trouble else "signs of it"
    tested = entity_fact(
        actor,
        "luck_tested",
        f"bad luck — {subject}: {label}",
        {"subject": subject, "trouble": trouble},
    )
    return [rolled, tested], trouble
