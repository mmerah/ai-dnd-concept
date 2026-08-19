from random import Random
from typing import Self

from pydantic import Field, model_validator

from aidm.engines.counters import adjust, spend
from aidm.engines.sheets import require_sheet
from aidm.state.actions import require_actor_here, reveal
from aidm.state.base import Entity, EntityId, Frozen, Slug
from aidm.state.dice import roll_pool
from aidm.state.facts import Fact, entity_fact
from aidm.state.resolution import Resolution
from aidm.state.world import Game

from .mechanics import DEFAULT_FACE, HINDERED_FACE, Mechanics, Sheet

TROUBLE = 2  # 1-2 on the bad-luck die
SIGNS = 4  # 3-4 on the bad-luck die


class Attempt(Frozen):
    actor_id: EntityId = Field(
        description="Exact id of the actor attempting this: the player, or an actor here."
    )
    goal: str = Field(
        min_length=1,
        description="What the actor is trying to do and what they risk by trying, in one line.",
    )
    skill: str = Field(
        default="",
        description="The skill on the actor's sheet this calls on, or empty for none.",
    )
    helped: str = Field(
        default="",
        description="The circumstance that makes this easier — a skill, a piece of gear, the "
        "ground they hold, an ally's presence — in a few words. Empty when nothing does, and "
        "never alongside `helper_id`.",
    )
    helper_id: EntityId | None = Field(
        default=None,
        description="Exact id of an ally here who helps with this — they roll their own skill "
        "die into the pool. Null when nobody helps.",
    )
    helper_skill: str = Field(
        default="",
        description="The skill on the *helper's* sheet this calls on, or empty for none.",
    )
    hindered: str = Field(
        default="",
        description="The circumstance that makes this harder, in a few words. Empty when "
        "nothing does.",
    )
    luck_test: str = Field(
        default="",
        description="What bad luck might arrive alongside this. Empty for no test.",
    )

    @model_validator(mode="after")
    def _one_help_die(self) -> Self:
        if self.helper_id is not None and self.helped:
            raise ValueError(
                "help is one die: name the ally in `helper_id` or the circumstance in `helped`, "
                "never both"
            )
        if self.helper_skill and self.helper_id is None:
            raise ValueError(
                "`helper_skill` is the skill of the ally in `helper_id`; name them too"
            )
        return self


class LuckTest(Frozen):
    actor_id: EntityId = Field(
        description="Exact id of the actor whose luck is tested: the player, or an actor here."
    )
    subject: str = Field(
        min_length=1,
        description="What bad luck might arrive — running out of ammo, running into guards.",
    )


def apply_change_credits(draft: Game, actor_id: EntityId, amount: int) -> list[Fact]:
    if amount == 0:
        raise ValueError("changing credits moves the pool; zero moves nothing")
    actor = require_actor_here(draft, actor_id)
    facts = reveal(draft, actor.id)
    credits = require_sheet(Mechanics.of(draft).sheets, actor).credits
    if amount > 0:
        return [*facts, *adjust(actor, "credits", credits, amount, "paid")]
    # `spend`, not a negative adjust: an overdraw is refused, not clamped.
    return [*facts, *spend(actor, "credits", credits, -amount)]


def outcome_for(kept: int) -> Slug:
    if kept <= 2:
        return "disaster"
    if kept <= 4:
        return "setback"
    return "success"


def pool_faces(sheet: Sheet, action: Attempt, helper: Sheet | None) -> tuple[int, ...]:
    """Hindrance drops the die to a d4; help adds one die at most — the helper's own, or a d6."""
    base = HINDERED_FACE if action.hindered else sheet.face(action.skill)
    if helper is not None:
        return (base, helper.face(action.helper_skill))
    return (base, DEFAULT_FACE) if action.helped else (base,)


def resolve_attempt(draft: Game, action: Attempt, rng: Random) -> Resolution:
    actor = require_actor_here(draft, action.actor_id)
    facts = reveal(draft, action.actor_id)
    sheet = require_sheet(Mechanics.of(draft).sheets, actor)
    helper_sheet = _helper_sheet(draft, actor, action, facts)
    _require_skill(actor, sheet, action.skill, "skill")

    faces = pool_faces(sheet, action, helper_sheet)
    kept, rolled = roll_pool(faces, f"{action.goal} — {action.skill or 'no skill'}", rng)
    facts.append(rolled)

    outcome = outcome_for(kept)
    facts.append(
        entity_fact(
            actor,
            "attempt_resolved",
            f"{action.goal} -> {outcome}",
            {
                "outcome": outcome,
                "kept": kept,
                "skill": action.skill,
                "faces": list(faces),
                "helper": action.helper_id,
            },
        )
    )

    if action.luck_test:
        facts.extend(_bad_luck(draft, actor, action.luck_test, rng))
    return Resolution(facts=tuple(facts))


def resolve_luck_test(draft: Game, action: LuckTest, rng: Random) -> Resolution:
    actor = require_actor_here(draft, action.actor_id)
    facts = reveal(draft, action.actor_id)
    facts.extend(_bad_luck(draft, actor, action.subject, rng))
    return Resolution(facts=tuple(facts))


def _helper_sheet(draft: Game, actor: Entity, action: Attempt, facts: list[Fact]) -> Sheet | None:
    if action.helper_id is None:
        return None
    if action.helper_id == actor.id:
        raise ValueError(
            f"{actor.name} cannot help themselves. Name the ally who does, or leave `helper_id` "
            "null."
        )
    helper = require_actor_here(draft, action.helper_id)
    facts.extend(reveal(draft, action.helper_id))
    sheet = require_sheet(Mechanics.of(draft).sheets, helper)
    _require_skill(helper, sheet, action.helper_skill, "helper_skill")
    return sheet


def _require_skill(actor: Entity, sheet: Sheet, skill: str, field: str) -> None:
    if skill and skill not in sheet.skills:
        written = ", ".join(sorted(sheet.skills)) or "(none)"
        raise ValueError(
            f"{actor.name} has no skill {skill!r}. Their skills are: {written}. Leave "
            f"`{field}` empty to roll the bare d6."
        )


def _bad_luck(draft: Game, actor: Entity, subject: str, rng: Random) -> list[Fact]:
    kept, rolled = roll_pool((6,), f"bad luck — {subject}", rng)
    if kept > SIGNS:
        return [rolled]
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
    return [rolled, tested]
