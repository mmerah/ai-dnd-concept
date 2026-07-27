"""DIRECTOR — owns world direction and the turn's mechanics."""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.messages import ModelMessage

from ..domain.models import (
    CONSEQUENCE_TYPES,
    PLAYER_ID,
    ActorEntity,
    Consequence,
    Damage,
    Direction,
    Entity,
    EntityId,
    GiveItem,
    Heal,
    Ref,
    RollCheck,
    RollDice,
)
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
    """The turn's canon and the player's location, for id and co-location validation."""

    entities: Mapping[EntityId, Entity]
    location: EntityId


def _flat(consequences: Sequence[Consequence]) -> Iterator[Consequence]:
    for consequence in consequences:
        yield consequence
        yield from _flat(consequence.children())


def _refs_used(consequence: Consequence) -> tuple[str, ...]:
    """The bound-value names a consequence reads (only Damage/Heal, via a Ref amount)."""
    if isinstance(consequence, (Damage, Heal)) and isinstance(consequence.amount, Ref):
        return (consequence.amount.ref,)
    return ()


def _check_refs(consequences: Sequence[Consequence]) -> None:
    """Every Ref must name a value a `roll_dice` bound and can reach: a bind is visible to later
    consequences in its own sequence but never escapes its RollCheck branch, since only one branch
    runs. Scoping lexically here turns a cross-branch leak into a retry, not a resolve-time fail."""

    def walk(items: Sequence[Consequence], bound: set[str]) -> None:
        scope = set(bound)  # sequence-level binds accumulate, visible to later siblings
        for c in items:
            for name in _refs_used(c):
                if name not in scope:
                    raise ModelRetry(f"reference {name!r} was never rolled by a roll_dice first")
            match c:
                case RollDice(bind=bind, then=then):
                    walk(then, scope | {bind})  # `then` sees the new bind
                    scope.add(bind)  # so do later siblings in this same sequence
                case RollCheck(on_success=on_success, on_failure=on_failure):
                    walk(on_success, scope)  # each branch is its own scope; a bind cannot escape it
                    walk(on_failure, scope)
                case _:
                    pass

    walk(consequences, set())


def _validate_ids(ctx: RunContext[DirectorDeps], direction: Direction) -> Direction:
    """Every id the Director chose must exist in the turn's canon, as the right kind; a speaker must
    be one the player already knows; every Ref must resolve to an earlier roll. All faults are
    retries, not errors: the model can pick again from what it was shown."""
    refs = direction.canon_refs()
    if direction.speaker_id is not None:
        refs.append((direction.speaker_id, "actor"))
    canon = dict(ctx.deps.entities)

    # The player is an actor in canon now, so naming them where someone else is meant passes the
    # kind check below. Caught here as a retry rather than a dropped turn in the resolver.
    if direction.speaker_id == PLAYER_ID:
        raise ModelRetry("speaker_id must be an actor the player addresses, never the player")
    if any(isinstance(c, GiveItem) and c.actor_id == PLAYER_ID for c in _flat(direction.mechanics)):
        raise ModelRetry("give_item must name another actor: the player already holds the item")

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
    # A hidden or absent speaker would put words in a stranger's mouth; catch it here as a retry
    # rather than letting views.speaker hard-fail the turn downstream.
    speaker = canon.get(direction.speaker_id) if direction.speaker_id is not None else None
    if speaker is not None and not speaker.known:
        raise ModelRetry(f"speaker {direction.speaker_id!r} exists but the player has not met them")
    if isinstance(speaker, ActorEntity) and speaker.location_id != ctx.deps.location:
        raise ModelRetry(f"speaker {direction.speaker_id!r} is not at the player's location")
    _check_refs(direction.mechanics)
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
