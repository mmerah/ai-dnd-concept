import json
from collections.abc import Iterable, Sequence

from ..domain.base import EntityId, Kind
from ..domain.entities import Entity
from ..domain.growth import GrowthRequest
from ..domain.state import Exchange
from .context import (
    CatalogueEntityView,
    CreatorContext,
    DirectorContext,
    DirectorScene,
    EntityRenderer,
    MaintainerContext,
    NarratorContext,
    NarratorEntityView,
    NarratorScene,
    entity_placement,
)


def _sections(parts: Iterable[tuple[str, str]]) -> str:
    return "\n\n".join(f"{name}:\n{body}" for name, body in parts)


def _premise(title: str, premise: str) -> tuple[str, str]:
    return "SCENARIO", f"{title}\n{premise}"


def build_director_prompt(
    context: DirectorContext,
    entity_state: EntityRenderer,
) -> str:
    scene = context.scene
    return _sections(
        (
            _premise(context.scenario_title, context.scenario_premise),
            ("PLAYER CHARACTER", _director_character(scene, entity_state)),
            (
                "HERE WITH THE PLAYER",
                _director_entities(scene.here, scene, entity_state),
            ),
            (
                "KNOWN TO THE PLAYER, BUT ELSEWHERE",
                _director_entities(scene.elsewhere, scene, entity_state),
            ),
            (
                "EXISTS BUT THE PLAYER DOES NOT KNOW IT YET",
                _director_entities(scene.unrevealed, scene, entity_state),
            ),
            ("PLAYER ACTION", context.prompt),
        )
    )


def build_narrator_prompt(context: NarratorContext) -> str:
    scene = context.scene
    return _sections(
        (
            _premise(context.scenario_title, context.scenario_premise),
            ("PLAYER CHARACTER", _narrator_character(scene)),
            ("HERE WITH THE PLAYER", _narrator_entities(scene.here)),
            (
                "KNOWN TO THE PLAYER, BUT ELSEWHERE",
                _narrator_entities(scene.elsewhere),
            ),
            ("THE DIRECTOR'S PLAN — what was meant, not what happened", context.intent),
            ("THE DIRECTOR ASKS FOR THIS TONE", context.tone),
            ("SPEAKER", _speaker(scene, context.speaker_id)),
            ("WHAT HAPPENED", context.evidence),
            ("PLAYER ACTION", context.prompt),
        )
    )


def build_maintainer_prompt(context: MaintainerContext) -> str:
    return _sections(
        (
            _premise(context.scenario_title, context.scenario_premise),
            ("EVERYTHING THAT EXISTS", _catalogue(context.scene.catalogue)),
            ("PLAYER", context.prompt),
            ("WHAT HAPPENED", context.evidence),
            ("NARRATION", context.narration),
        )
    )


def build_creator_prompt(
    context: CreatorContext,
    request: GrowthRequest,
) -> str:
    where = f"\nlocation: {request.location}" if request.location else ""
    kind = "an npc" if request.kind == "actor" else f"a {request.kind}"
    wanted = f"{kind} named {request.name}\nbrief: {request.brief}{where}"
    return _sections(
        (
            _premise(context.scenario_title, context.scenario_premise),
            ("EVERYTHING THAT EXISTS", _catalogue(context.scene.catalogue)),
            ("RECENT PLAY", _history(context.recent)),
            ("NARRATION", context.narration),
            ("CREATE", wanted),
        )
    )


def _director_character(
    scene: DirectorScene,
    entity_state: EntityRenderer,
) -> str:
    inventory = "\n".join(
        _with_state(
            f"- {_label(item)} — {item.brief}",
            entity_state(item),
            "  ",
        )
        for item in sorted(scene.carried, key=lambda held: held.name)
    )
    player = _with_state(
        f"{_label(scene.player)} — {scene.player.brief} — at {_label(scene.where)}",
        entity_state(scene.player),
    )
    return f"{player}\ninventory:\n{inventory or '- (none)'}"


def _director_entities(
    entities: Sequence[Entity],
    scene: DirectorScene,
    entity_state: EntityRenderer,
) -> str:
    return (
        "\n".join(
            _with_state(
                f"- {_label(entity)} ({_kind_label(entity.kind)})"
                f"{_with_placement(entity_placement(entity, scene.canon))} — {entity.brief}",
                entity_state(entity),
                "  ",
            )
            for entity in entities
        )
        or "- (none)"
    )


def _label(entity: Entity) -> str:
    return f"{entity.name}[id={prompt_id(entity.id)}]"


def prompt_id(entity_id: str) -> str:
    escaped = json.dumps(entity_id, ensure_ascii=True)[1:-1]
    return escaped.replace("[", "\\u005b").replace("]", "\\u005d")


def _kind_label(kind: Kind) -> str:
    return "npc" if kind == "actor" else kind


def _with_placement(placement: str) -> str:
    return f" — {placement}" if placement else ""


def _with_state(line: str, state: str, indent: str = "") -> str:
    if not state:
        return line
    continued = state.replace("\n", f"\n{indent}       ")
    return f"{line}\n{indent}state: {continued}"


def _narrator_character(scene: NarratorScene) -> str:
    inventory = "\n".join(
        _with_state(f"- {item.name} — {item.brief}", item.state, "  ")
        for item in sorted(scene.carried, key=lambda held: held.name)
    )
    player = _with_state(
        f"{scene.player.name} — {scene.player.brief} — at {scene.where.name}",
        scene.player.state,
    )
    return f"{player}\ninventory:\n{inventory or '- (none)'}"


def _narrator_entities(entities: Sequence[NarratorEntityView]) -> str:
    return (
        "\n".join(
            _with_state(
                f"- {entity.name}[id={prompt_id(entity.id)}] "
                f"({_kind_label(entity.kind)}) — {entity.brief}",
                entity.state,
                "  ",
            )
            for entity in entities
        )
        or "- (none)"
    )


def _speaker(scene: NarratorScene, speaker_id: EntityId | None) -> str:
    if speaker_id is None:
        return "(none — narrate the scene)"
    speaker = next((entity for entity in scene.here if entity.id == speaker_id), None)
    if speaker is None or speaker.kind != "actor":
        raise ValueError(f"speaker {speaker_id!r} is not a visible actor here")
    return f"{speaker.name}[id={prompt_id(speaker.id)}] — {speaker.brief}"


def _catalogue(entities: Sequence[CatalogueEntityView]) -> str:
    return (
        "\n".join(
            _catalogue_entry(entity)
            for entity in entities
        )
        or "- (none)"
    )


def _catalogue_entry(entity: CatalogueEntityView) -> str:
    line = (
        f"- {entity.name}[id={prompt_id(entity.id)}] ({_kind_label(entity.kind)})"
        f"{_with_placement(entity.placement)} — {entity.brief}"
    )
    if entity.description:
        line += f"\n  detail: {entity.description}"
    if entity.hook:
        line += f"\n  hook: {entity.hook}"
    return _with_state(line, entity.state, "  ")


def _history(recent: Sequence[Exchange]) -> str:
    return (
        "\n\n".join(f"Player: {exchange.prompt}\nDM: {exchange.narration}" for exchange in recent)
        or "(nothing yet)"
    )
