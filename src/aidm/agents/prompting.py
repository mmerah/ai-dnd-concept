import json
from collections.abc import Callable, Iterable, Sequence

from ..domain.base import EntityId, Kind
from ..domain.definitions import ScenarioMeta
from ..domain.entities import ActorEntity, Entity, ItemEntity, LocationEntity
from ..domain.growth import GrowthRequest
from ..domain.state import Exchange
from .context import EntityRenderer, SceneSnapshot, VisibleScene

type Placement = Callable[[Entity], str]
type Label = Callable[[Entity], str]


def render_director(
    scene: SceneSnapshot,
    describe: EntityRenderer,
    scenario: ScenarioMeta,
    prompt: str,
) -> str:
    return _sections(
        (
            _premise(scenario),
            (
                "PLAYER CHARACTER",
                _character(
                    scene.player, scene.location, scene.inventory, describe, label=_labelled
                ),
            ),
            (
                "HERE WITH THE PLAYER",
                _entities(scene.here, describe, placement=scene.placement_of),
            ),
            (
                "KNOWN TO THE PLAYER, BUT ELSEWHERE",
                _entities(scene.known_elsewhere, describe, placement=scene.placement_of),
            ),
            (
                "EXISTS BUT THE PLAYER DOES NOT KNOW IT YET",
                _entities(scene.hidden, describe, placement=scene.placement_of),
            ),
            ("PLAYER ACTION", prompt),
        )
    )


def render_narrator(
    scene: VisibleScene,
    describe: EntityRenderer,
    scenario: ScenarioMeta,
    *,
    intent: str,
    tone: str,
    speaker_id: EntityId | None,
    evidence: str,
    prompt: str,
) -> str:
    return _sections(
        (
            _premise(scenario),
            (
                "PLAYER CHARACTER",
                _character(scene.player, scene.location, scene.inventory, describe, label=_named),
            ),
            (
                "HERE WITH THE PLAYER",
                _entities(scene.here, describe, placement=scene.placement_of),
            ),
            (
                "KNOWN TO THE PLAYER, BUT ELSEWHERE",
                _entities(scene.known_elsewhere, describe, placement=scene.placement_of),
            ),
            ("THE DIRECTOR'S PLAN — what was meant, not what happened", intent),
            ("THE DIRECTOR ASKS FOR THIS TONE", tone),
            ("SPEAKER", _speaker(scene, speaker_id)),
            ("WHAT HAPPENED", evidence),
            ("PLAYER ACTION", prompt),
        )
    )


def render_maintainer(
    scene: SceneSnapshot,
    describe: EntityRenderer,
    scenario: ScenarioMeta,
    *,
    prompt: str,
    evidence: str,
    narration: str,
) -> str:
    return _sections(
        (
            _premise(scenario),
            ("EVERYTHING THAT EXISTS", _catalogue(scene, describe)),
            ("PLAYER", prompt),
            ("WHAT HAPPENED", evidence),
            ("NARRATION", narration),
        )
    )


def render_creator(
    scene: SceneSnapshot,
    describe: EntityRenderer,
    scenario: ScenarioMeta,
    *,
    narration: str,
    recent: Sequence[Exchange],
    request: GrowthRequest,
) -> str:
    where = f"\nlocation: {request.location}" if request.location else ""
    kind = "an npc" if request.kind == "actor" else f"a {request.kind}"
    wanted = f"{kind} named {request.name}\nbrief: {request.brief}{where}"
    return _sections(
        (
            _premise(scenario),
            ("EVERYTHING THAT EXISTS", _catalogue(scene, describe)),
            ("RECENT PLAY", _history(recent)),
            ("NARRATION", narration),
            ("CREATE", wanted),
        )
    )


def prompt_id(entity_id: str) -> str:
    escaped = json.dumps(entity_id, ensure_ascii=True)[1:-1]
    return escaped.replace("[", "\\u005b").replace("]", "\\u005d")


def _sections(parts: Iterable[tuple[str, str]]) -> str:
    return "\n\n".join(f"{name}:\n{body}" for name, body in parts)


def _premise(scenario: ScenarioMeta) -> tuple[str, str]:
    return "SCENARIO", f"{scenario.title}\n{scenario.premise}"


def _character(
    player: ActorEntity,
    location: LocationEntity,
    inventory: Sequence[ItemEntity],
    describe: EntityRenderer,
    *,
    label: Label,
) -> str:
    held = "\n".join(
        _with_state(f"- {label(item)} — {item.brief}", describe(item), "  ")
        for item in sorted(inventory, key=lambda item: item.name)
    )
    line = _with_state(
        f"{label(player)} — {player.brief} — at {label(location)}",
        describe(player),
    )
    return f"{line}\ninventory:\n{held or '- (none)'}"


def _entities(
    entities: Sequence[Entity],
    describe: EntityRenderer,
    *,
    placement: Placement,
) -> str:
    return (
        "\n".join(
            _with_state(_headline(entity, placement(entity)), describe(entity), "  ")
            for entity in entities
        )
        or "- (none)"
    )


def _catalogue(scene: SceneSnapshot, describe: EntityRenderer) -> str:
    return (
        "\n".join(
            _with_state(
                _headline(entity, scene.placement_of(entity)) + _detail(entity),
                describe(entity),
                "  ",
            )
            for entity in scene.catalogue()
        )
        or "- (none)"
    )


def _headline(entity: Entity, placement: str) -> str:
    placed = f" — {placement}" if placement else ""
    return f"- {_labelled(entity)} ({_kind_label(entity.kind)}){placed} — {entity.brief}"


def _detail(entity: Entity) -> str:
    if entity.detail is None:
        return ""
    described = f"\n  detail: {entity.detail.description}" if entity.detail.description else ""
    hooked = f"\n  hook: {entity.detail.hook}" if entity.detail.hook else ""
    return f"{described}{hooked}"


def _speaker(scene: VisibleScene, speaker_id: EntityId | None) -> str:
    if speaker_id is None:
        return "(none — narrate the scene)"
    speaker = next((entity for entity in scene.here if entity.id == speaker_id), None)
    if not isinstance(speaker, ActorEntity):
        raise ValueError(f"speaker {speaker_id!r} is not a visible actor here")
    return f"{_labelled(speaker)} — {speaker.brief}"


def _labelled(entity: Entity) -> str:
    return f"{entity.name}[id={prompt_id(entity.id)}]"


def _named(entity: Entity) -> str:
    return entity.name


def _kind_label(kind: Kind) -> str:
    return "npc" if kind == "actor" else kind


def _with_state(line: str, state: str, indent: str = "") -> str:
    if not state:
        return line
    continued = state.replace("\n", f"\n{indent}       ")
    return f"{line}\n{indent}state: {continued}"


def _history(recent: Sequence[Exchange]) -> str:
    return (
        "\n\n".join(f"Player: {exchange.prompt}\nDM: {exchange.narration}" for exchange in recent)
        or "(nothing yet)"
    )
