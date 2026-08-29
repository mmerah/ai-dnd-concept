from typing import Self

from aidm.state.entities import CheckedEntityId, Frozen
from aidm.state.model import WorldState


class SceneSection(Frozen):
    """One block of the turn's context; `director` is what only the Director may read."""

    title: str
    player: str = ""
    director: str | None = None  # None means the player text serves both readers


class Scene(Frozen):
    """The current player-facing context, not a place: every consumer reads this projection."""

    key: str
    label: str
    summary: str = ""
    sections: tuple[SceneSection, ...]
    # Entity-derived player text declares its entity here, as a told fact declares its own.
    public_entity_ids: frozenset[CheckedEntityId] = frozenset()
    present_entity_ids: frozenset[CheckedEntityId] = frozenset()
    prompts: tuple[tuple[str, str], ...] = ()
    art_prompt: str = ""
    art_subject_ids: tuple[CheckedEntityId, ...] = ()


class VisibleScene(Frozen):
    """The Narrator's view: it has no field that can hold director-only text."""

    key: str
    label: str
    summary: str
    sections: tuple[tuple[str, str], ...]
    present_entity_ids: frozenset[CheckedEntityId]
    prompts: tuple[tuple[str, str], ...]
    art_prompt: str
    art_subject_ids: tuple[CheckedEntityId, ...]

    @classmethod
    def revealed_from(cls, scene: Scene, world: WorldState) -> Self:
        named = scene.public_entity_ids | scene.present_entity_ids | set(scene.art_subject_ids)
        for entity_id in sorted(named):
            entity = world.find(entity_id)
            if entity is None:
                raise ValueError(f"the scene names {entity_id!r}, which the world does not hold")
            if not entity.known:
                raise ValueError(f"the scene names {entity_id!r}, whom the player has not met")
        return cls(
            key=scene.key,
            label=scene.label,
            summary=scene.summary,
            sections=tuple(
                (section.title, section.player) for section in scene.sections if section.player
            ),
            present_entity_ids=scene.present_entity_ids,
            prompts=scene.prompts,
            art_prompt=scene.art_prompt,
            art_subject_ids=scene.art_subject_ids,
        )
