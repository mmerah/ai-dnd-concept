"""DIRECTOR — owns world direction and the turn's mechanics. The only role that sees hidden canon,
and the only role that chooses mechanics: it emits typed `Mechanics`, resolved in Python."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.messages import ModelMessage

from ..domain.models import CONSEQUENCE_TYPES, Consequence, Direction, Entity, EntityId
from .llm import build_agent


def consequence_menu(types: Sequence[type[Consequence]]) -> str:
    """The Director's consequence reference, assembled from each class's own docstring, `GUIDANCE`
    and field descriptions — so adding a consequence updates the prompt with no edit here."""
    lines: list[str] = []
    for consequence in types:
        action = consequence.model_fields["action"].default
        if not isinstance(action, str):  # a discriminator that is not a literal string is a bug
            raise TypeError(f"{consequence.__name__} has no literal action default")
        fields = "\n".join(
            f"  - `{name}`: {field.description}"
            for name, field in consequence.model_fields.items()
            if name != "action" and field.description
        )
        lines.append(f"### `{action}` — {consequence.__doc__}\n{consequence.GUIDANCE}\n{fields}")
    return "\n\n".join(lines)


_TEMPLATE = """You are the DIRECTOR of a tabletop RPG. You decide what SHOULD happen this turn \
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

`mechanics` — resolved deterministically. All ids MUST be exact ids from the lists above.
- `check` — set it only when the action can fail: an ability (strength, dexterity, intellect, \
wisdom) and a DC (5 easy, 10 moderate, 15 hard, 20 very hard). Omit it when nothing is at stake.
- `unconditional` — consequences applied no matter what.
- `on_success` / `on_failure` — consequences applied only on that branch of the check. With no \
check, only `unconditional` and `on_success` apply.

The consequences you can place in those lists:

{consequences}

If nothing mechanical is at stake, leave the mechanics empty."""

INSTRUCTIONS = _TEMPLATE.replace("{consequences}", consequence_menu(CONSEQUENCE_TYPES))


@dataclass
class DirectorDeps:
    """The turn's canon, for id validation in the output validator."""

    entities: Mapping[EntityId, Entity]


def _validate_ids(ctx: RunContext[DirectorDeps], direction: Direction) -> Direction:
    """Every id the Director chose must exist in the turn's canon, as the right kind, and a
    speaker must be one the player already knows. All faults are retries, not errors: the model
    can pick again from what it was shown."""
    refs = direction.mechanics.canon_refs()
    if direction.speaker_id is not None:
        refs.append((direction.speaker_id, "npc"))
    canon = dict(ctx.deps.entities)

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
    # A hidden speaker would put words in a stranger's mouth; catch it here as a retry rather than
    # letting views.speaker hard-fail the turn downstream.
    if direction.speaker_id is not None and not canon[direction.speaker_id].known:
        raise ModelRetry(f"speaker {direction.speaker_id!r} exists but the player has not met them")
    return direction


agent = build_agent(
    "director",
    output_type=NativeOutput(Direction),
    instructions=INSTRUCTIONS,
    deps_type=DirectorDeps,
    output_validators=(_validate_ids,),
)


async def direct(
    prompt: str, deps: DirectorDeps, message_history: list[ModelMessage] | None = None
) -> Direction:
    return (await agent().run(prompt, deps=deps, message_history=message_history)).output
