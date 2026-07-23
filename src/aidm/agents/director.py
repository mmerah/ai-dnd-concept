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
    Kind,
    LoseCanonItem,
    Move,
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
minor item with no canon entity, by free text), `modify_hp` (delta), `move` (go to a location, by \
id — including one the player has not discovered yet, which arriving reveals).
- Each id must be the right kind of thing: `move` takes a location, the canon item actions take an \
item, `speaker_id` takes an npc.
- The player can only be moved to a location that exists. If they head somewhere the world does \
not yet contain, leave `move` out and let the narration take them toward it; the place becomes \
canon and you can move them there on a later turn.
- Use loose items only for incidental things no entity backs. If nothing mechanical is at stake, \
leave the plan empty."""


@dataclass
class DirectorDeps:
    """The turn's canon, for id validation in the output validator."""

    entities: Sequence[Entity]


def _plan_refs(plan: Plan) -> list[tuple[EntityId, Kind | None]]:
    """Each canon reference with the kind it must be. `discover` alone accepts any kind."""
    refs: list[tuple[EntityId, Kind | None]] = []
    for c in [*plan.unconditional, *plan.on_success, *plan.on_failure]:
        match c:
            case Discover(entity_id=entity_id):
                refs.append((entity_id, None))
            case GainCanonItem(entity_id=entity_id) | LoseCanonItem(entity_id=entity_id):
                refs.append((entity_id, "item"))
            case Move(entity_id=entity_id):
                refs.append((entity_id, "location"))
            case _:
                pass
    return refs


def _canon_refs(ctx: RunContext[DirectorDeps], direction: Direction) -> Direction:
    """Every id the Director chose must exist in the turn's canon, as the right kind of thing.
    Both faults are retries, not errors: the model can pick again from what it was shown."""
    refs = _plan_refs(direction.plan)
    if direction.speaker_id is not None:
        refs.append((direction.speaker_id, "npc"))
    canon = {e.id: e for e in ctx.deps.entities}

    missing = sorted({i for i, _ in refs if i not in canon})
    if missing:
        raise ModelRetry(f"unknown entity id(s): {missing}. Use only ids you were shown.")
    mismatched = sorted(
        f"{i} is a {canon[i].kind}, not a {kind}"
        for i, kind in refs
        if kind is not None and canon[i].kind != kind
    )
    if mismatched:
        raise ModelRetry(f"wrong kind of entity: {'; '.join(mismatched)}.")
    return direction


agent = build_agent(
    "director",
    output_type=NativeOutput(Direction),
    instructions=INSTRUCTIONS,
    deps_type=DirectorDeps,
    output_validators=(_canon_refs,),
)


async def direct(
    prompt: str, deps: DirectorDeps, message_history: list[ModelMessage] | None = None
) -> Direction:
    return (await agent().run(prompt, deps=deps, message_history=message_history)).output
