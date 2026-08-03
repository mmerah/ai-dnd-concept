from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel

from .base import PLAYER_ID, ActorEntity, EntityId, Frozen, Kind
from .world import GameState


class ConsequenceBase(Frozen):
    GUIDANCE: ClassVar[str] = ""

    def check(self) -> str | None:
        return None


@dataclass(frozen=True, slots=True)
class Reference:
    kind: Kind | None
    present: bool = False


type Branches[T] = Callable[[T], Iterable[Sequence[T]]]
type StaticCheck[T] = Callable[[GameState, T], str | None]


def consequence_menu(types: Sequence[type[ConsequenceBase]]) -> str:
    lines: list[str] = []
    for consequence in types:
        action = consequence.model_fields["action"].default
        summary = consequence.__doc__
        if not isinstance(action, str) or summary is None:
            raise TypeError(f"{consequence.__name__} has incomplete prompt documentation")
        fields = "\n".join(
            f"  - `{name}`: {field.description}"
            for name, field in consequence.model_fields.items()
            if name != "action" and field.description
        )
        lines.append(f"### `{action}` — {summary}\n{consequence.GUIDANCE}\n{fields}")
    return "\n\n".join(lines)


def walk_consequences[T](consequences: Sequence[T], branches: Branches[T]) -> Iterator[T]:
    for consequence in consequences:
        yield consequence
        for branch in branches(consequence):
            yield from walk_consequences(branch, branches)


def consequence_references(
    consequence: BaseModel,
) -> tuple[tuple[EntityId, Reference], ...]:
    references: list[tuple[EntityId, Reference]] = []
    for name, field in type(consequence).model_fields.items():
        marker = next((item for item in field.metadata if isinstance(item, Reference)), None)
        if marker is None:
            continue
        value: object = getattr(consequence, name)
        if value is None:
            continue
        if not isinstance(value, str):
            raise TypeError(
                f"{type(consequence).__name__}.{name} is marked Reference "
                f"but holds a {type(value).__name__}"
            )
        references.append((EntityId(value), marker))
    return tuple(references)


def check_proposal[T: ConsequenceBase](
    state: GameState,
    consequences: Sequence[T],
    speaker_id: EntityId | None,
    branches: Branches[T],
    extra_checks: Sequence[StaticCheck[T]] = (),
) -> str | None:
    flattened = tuple(walk_consequences(consequences, branches))
    faults = [consequence.check() for consequence in flattened]
    faults.append(check_speaker(state, speaker_id))
    faults.append(
        check_refs(
            state,
            [
                reference
                for consequence in flattened
                for reference in consequence_references(consequence)
            ],
        )
    )
    faults.extend(check(state, consequence) for check in extra_checks for consequence in flattened)
    return next((fault for fault in faults if fault is not None), None)


def check_refs(state: GameState, refs: Sequence[tuple[EntityId, Reference]]) -> str | None:
    """Every fault at once: a Director told all of them retries better than one told the first."""
    looked_up = {entity_id: state.world.find(entity_id) for entity_id, _ in refs}
    missing = sorted(entity_id for entity_id, found in looked_up.items() if found is None)
    if missing:
        return f"unknown entity id(s): {missing}. Use only ids you were shown."
    canon = {entity_id: found for entity_id, found in looked_up.items() if found is not None}
    mismatched = sorted(
        f"{entity_id} is a {canon[entity_id].kind}, not a {reference.kind}"
        for entity_id, reference in refs
        if reference.kind is not None and canon[entity_id].kind != reference.kind
    )
    if mismatched:
        return (
            f"wrong kind of entity: {'; '.join(mismatched)}. "
            "Use an id of the kind each field asks for."
        )
    absent = sorted(
        {
            entity_id
            for entity_id, reference in refs
            if reference.present and not state.is_here(canon[entity_id])
        }
    )
    if absent:
        return f"not here with the player: {absent}. Move them here first, or act on who is here."
    return None


def check_speaker(state: GameState, speaker_id: EntityId | None) -> str | None:
    """The player is addressed, never the speaker: losing this lets the Director voice them."""
    if speaker_id is None:
        return None
    if speaker_id == PLAYER_ID:
        return "speaker_id names another actor the player addresses, never the player."
    speaker = state.world.find(speaker_id)
    if speaker is None:
        return f"unknown speaker id {speaker_id!r}. Use only ids you were shown, or null."
    if not isinstance(speaker, ActorEntity) or not speaker.known or not state.is_here(speaker):
        return (
            f"speaker {speaker_id!r} must be an NPC the player has met and who is here with them. "
            "Use null if nobody is being addressed."
        )
    return None
