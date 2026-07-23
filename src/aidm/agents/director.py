"""DIRECTOR — owns world direction and the turn's mechanical plan. The only role that sees hidden
canon, and now the only role that chooses mechanics: it emits a typed plan, resolved in Python."""

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.messages import ModelMessage

from ..domain.models import (
    Direction,
    Discover,
    Entity,
    EntityId,
    GainCanonItem,
    LoseCanonItem,
    Plan,
)
from .llm import build_agent

INSTRUCTIONS = """You are the DIRECTOR of a tabletop RPG. You decide what SHOULD happen this turn \
and lay out the mechanics. You never write prose for the player.

You alone are shown what exists but the player does not know yet. Use it: when something already \
in the world answers what the player is after, steer them to it. Always prefer existing canon to \
anything new, and never invent a named person, place or item yourself.

Every entity is shown as `name[id=...]`. Wherever a field below asks for an id, use the exact id \
from the brackets — for known and unrevealed entities alike, never the name.

`intent` — 1-3 sentences for the Narrator: what the player attempted and what is at stake. Never \
state outcomes, numbers or dice; the Narrator learns the result elsewhere.

`tone` — a few words of mood for the Narrator. Atmosphere only, never outcomes: "tense and \
hushed", not "they find the map".

`speaker_id` — the id of the NPC the player is addressing, or null if none. It must be an id the \
player already knows; never one they have not met.

`plan` — the mechanics, resolved deterministically. All ids MUST be exact ids from the lists above.
- `check` — set it only when the action can fail: an ability (strength, dexterity, intellect, \
wisdom) and a DC (5 easy, 10 moderate, 15 hard, 20 very hard). Omit it when nothing is at stake.
- `unconditional` — consequences applied no matter what.
- `on_success` / `on_failure` — consequences applied only on that branch of the check. With no \
check, only `unconditional` and `on_success` apply.
- Consequences: `discover` (reveal an existing entity by id), `gain_canon_item` / \
`lose_canon_item` (an item that exists in canon, by id), `gain_loose_item` / `lose_loose_item` (a \
minor item with no canon entity, by free text), `modify_hp` (delta), `move` (a location name).
- Use canon item consequences for anything in the lists; use loose items only for incidental \
things no entity backs. If nothing mechanical is at stake, leave the plan empty."""


@dataclass
class DirectorDeps:
    """The turn's canon, for id validation in the output validator."""

    entities: Sequence[Entity]


def _plan_ids(plan: Plan) -> set[EntityId]:
    return {
        c.entity_id
        for c in [*plan.unconditional, *plan.on_success, *plan.on_failure]
        if isinstance(c, Discover | GainCanonItem | LoseCanonItem)
    }


def _canon_ids(ctx: RunContext[DirectorDeps], direction: Direction) -> Direction:
    """Every id the Director chose must exist in the turn's canon."""
    referenced = _plan_ids(direction.plan)
    if direction.speaker_id is not None:
        referenced.add(direction.speaker_id)
    missing = referenced - {e.id for e in ctx.deps.entities}
    if missing:
        raise ModelRetry(f"unknown entity id(s): {sorted(missing)}. Use only ids you were shown.")
    return direction


agent = build_agent(
    "director",
    output_type=NativeOutput(Direction),
    instructions=INSTRUCTIONS,
    deps_type=DirectorDeps,
    output_validators=(_canon_ids,),
)


async def direct(
    prompt: str, deps: DirectorDeps, message_history: list[ModelMessage] | None = None
) -> Direction:
    return (await agent().run(prompt, deps=deps, message_history=message_history)).output
