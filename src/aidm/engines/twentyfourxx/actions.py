from collections.abc import Mapping
from random import Random
from typing import Self

from pydantic import Field, model_validator

from aidm.engines.sheets import require_sheet
from aidm.engines.tags import carriers, tag_key
from aidm.state.apply import apply_effect, require_actor_here
from aidm.state.base import PLAYER_ID, Entity, EntityId, Frozen, Slug
from aidm.state.dice import roll_pool
from aidm.state.effects import Reveal
from aidm.state.facts import Fact, entity_fact
from aidm.state.plan import Followup, Resolution
from aidm.state.world import GameState

from .mechanics import DEFAULT_FACE, HINDERED_FACE, Mechanics, Sheet

TROUBLE = 2  # 1-2 on the bad-luck die
SIGNS = 4  # 3-4 on the bad-luck die


class Attempt(Frozen):
    """One risky attempt, answered by the highest die of a pool."""

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
    helper_id: EntityId | None = Field(
        default=None,
        description="Exact id of an ally here who helps with this — they roll their own skill "
        "die into the pool. Null when nobody helps.",
    )
    helper_skill: str = Field(
        default="",
        description="The skill on the *helper's* sheet this calls on, copied exactly as it is "
        "written there. Empty when none of theirs applies: they roll the bare d6.",
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
    """The SRD's standalone bad-luck test, for a beat where nothing is attempted."""

    actor_id: EntityId = Field(
        description="Exact id of the actor whose luck is tested: the player, or an actor here."
    )
    subject: str = Field(
        min_length=1,
        description="What bad luck might arrive — running out of ammo, running into guards. The "
        "engine rolls whether it does.",
    )


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


def resolve_attempt(draft: GameState, action: Attempt, rng: Random) -> Resolution:
    actor = require_actor_here(draft, action.actor_id)
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    sheet = require_sheet(draft.mechanics_as(Mechanics).sheets, actor)
    helper_sheet = _helper_sheet(draft, actor, action, facts)
    known = _known_tags(draft, actor)
    _refuse_unless_ready(actor, action, sheet, known)

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

    followup: Followup = "settle" if outcome == "disaster" and actor.id == PLAYER_ID else "continue"
    if action.luck_test:
        tested, luck = _bad_luck(draft, actor, action.luck_test, rng)
        facts.extend(tested)
        if luck == "trouble":
            followup = "settle"
    return Resolution(facts=tuple(facts), outcome=outcome, followup=followup)


def resolve_luck_test(draft: GameState, action: LuckTest, rng: Random) -> Resolution:
    actor = require_actor_here(draft, action.actor_id)
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    tested, outcome = _bad_luck(draft, actor, action.subject, rng)
    facts.extend(tested)
    followup: Followup = "settle" if outcome == "trouble" else "continue"
    return Resolution(facts=tuple(facts), outcome=outcome, followup=followup)


def _known_tags(draft: GameState, actor: Entity) -> dict[str, str]:
    known: dict[str, str] = {}
    for carrier in carriers(draft, actor):
        for trait in carrier.traits:
            known[tag_key(trait.id)] = trait.name
            known[tag_key(trait.name)] = trait.name
    return known


def _helper_sheet(
    draft: GameState, actor: Entity, action: Attempt, facts: list[Fact]
) -> Sheet | None:
    if action.helper_id is None:
        return None
    if action.helper_id == actor.id:
        raise ValueError(
            f"{actor.name} cannot help themselves. Name the ally who does, or leave `helper_id` "
            "null."
        )
    helper = require_actor_here(draft, action.helper_id)
    facts.extend(apply_effect(draft, Reveal(entity_id=action.helper_id)))
    sheet = require_sheet(draft.mechanics_as(Mechanics).sheets, helper)
    _require_skill(helper, sheet, action.helper_skill, "helper_skill")
    return sheet


def _require_skill(actor: Entity, sheet: Sheet, skill: str, field: str) -> None:
    if skill and skill not in sheet.skills:
        written = ", ".join(sorted(sheet.skills)) or "(none)"
        raise ValueError(
            f"{actor.name} has no skill {skill!r}. Their skills are: {written}. Leave "
            f"`{field}` empty to roll the bare d6."
        )


def _refuse_unless_ready(
    actor: Entity, action: Attempt, sheet: Sheet, known: Mapping[str, str]
) -> None:
    _require_skill(actor, sheet, action.skill, "skill")
    for tag in (action.helped, action.hindered):
        if tag and tag_key(tag) not in known:
            written = ", ".join(sorted(set(known.values()))) or "(none)"
            raise ValueError(
                f"nothing in this scene is tagged {tag!r}. The tags in play are: {written}"
            )


def _bad_luck(
    draft: GameState, actor: Entity, subject: str, rng: Random
) -> tuple[list[Fact], Slug]:
    kept, rolled = roll_pool((6,), f"bad luck — {subject}", rng)
    if kept > SIGNS:
        return [rolled], "clear"
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
    return [rolled, tested], "trouble" if trouble else "signs"
