from collections.abc import Sequence
from dataclasses import dataclass

from .base import PLAYER_ID, ActorEntity, EntityId, Kind
from .world import GameState


@dataclass(frozen=True, slots=True)
class Reference:
    """What an id in a proposed command must name to be resolvable."""

    kind: Kind | None
    present: bool = False


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
