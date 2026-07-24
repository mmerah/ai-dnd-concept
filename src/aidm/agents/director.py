"""DIRECTOR — owns world direction and the turn's mechanics."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.messages import ModelMessage

from ..domain.models import CONSEQUENCE_TYPES, Consequence, Direction, Entity, EntityId
from .llm import build_agent
from .prompts.director import TEMPLATE


def consequence_menu(types: Sequence[type[Consequence]]) -> str:
    """Consequence reference assembled from each class's own docstring, `GUIDANCE`
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


INSTRUCTIONS = TEMPLATE.replace("{consequences}", consequence_menu(CONSEQUENCE_TYPES))


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
