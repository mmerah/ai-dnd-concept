from aidm.state.entities import CheckedEntityId, Frozen


class Scene(Frozen):
    """The current player-facing context, not a place: every consumer reads this projection."""

    key: str
    label: str
    summary: str = ""
    sections: tuple[tuple[str, str], ...]
    # The Director's own list, whole: an engine states both, so nothing leaks by omission.
    director_sections: tuple[tuple[str, str], ...]
    # Entity-derived player text declares its entity here, as a told fact declares its own.
    public_entity_ids: frozenset[CheckedEntityId] = frozenset()
    present_entity_ids: frozenset[CheckedEntityId] = frozenset()
    prompts: tuple[tuple[str, str], ...] = ()
    art_prompt: str = ""
    art_subject_ids: tuple[CheckedEntityId, ...] = ()
