import json
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from aidm.content.store import engine_text
from aidm.engines.advancement import Offer
from aidm.engines.engine import Engine, EntityRenderer
from aidm.state.base import Entity, Exit, Trait, kind_word
from aidm.state.world import Game, ScenarioMeta, Thread

from .scene import BaseScene, SceneSnapshot, VisibleScene


def render_director(
    scene: SceneSnapshot,
    describe: EntityRenderer,
    scenario: ScenarioMeta,
    prompt: str,
) -> str:
    # The Director writes no prose, so the canon side leaks nothing by reaching it.
    return _sections(
        (
            *_scene_sections(scene, describe, scenario),
            (
                "EXISTS BUT THE PLAYER DOES NOT KNOW IT YET",
                _entities(scene.hidden, describe, placement=scene.placement_of),
            ),
            ("ACTIVE THREADS", _threads(scene.threads)),
            ("NOTES FROM THE RULES", "\n".join(f"- {note}" for note in scene.notes) or "- (none)"),
            ("PLAYER ACTION", prompt),
        )
    )


def render_narrator(
    scene: VisibleScene,
    describe: EntityRenderer,
    scenario: ScenarioMeta,
    *,
    evidence: str,
    prompt: str,
) -> str:
    return _sections(
        (
            *_scene_sections(scene, describe, scenario),
            ("WHAT HAPPENED", evidence),
            ("PLAYER ACTION", prompt),
        )
    )


def render_proposal(engine: Engine, state: Game, offer: Offer, intent: str) -> str:
    subject = state.world.require(offer.subject_id)
    sections = (
        ("ON OFFER", offer.prompt),
        ("RULES TEXT", offer.text),
        ("THE CHARACTER", f"{subject.name}\n{entity_state(subject, engine.renderer(state))}"),
        ("WHAT THE PLAYER WANTS", intent),
    )
    return "\n\n".join(f"{title}\n{body}" for title, body in sections if body)


def prompt_id(entity_id: str) -> str:
    escaped = json.dumps(entity_id, ensure_ascii=True)[1:-1]
    return escaped.replace("[", "\\u005b").replace("]", "\\u005d")


def _sections(parts: Iterable[tuple[str, str]]) -> str:
    return "\n\n".join(f"{name}:\n{body}" for name, body in parts)


def _premise(scenario: ScenarioMeta) -> tuple[str, str]:
    return "SCENARIO", f"{scenario.title}\n{scenario.premise}"


def _scene_sections(
    scene: BaseScene, describe: EntityRenderer, scenario: ScenarioMeta
) -> tuple[tuple[str, str], ...]:
    return (
        _premise(scenario),
        (
            "PLAYER CHARACTER",
            _character(scene.player, scene.location, scene.inventory, describe),
        ),
        (
            "HERE WITH THE PLAYER",
            _entities(scene.here, describe, placement=scene.placement_of),
        ),
        (
            "EXITS FROM HERE",
            "\n".join(_exit_line(scene, way) for way in scene.exits) or "- (none)",
        ),
        (
            "KNOWN TO THE PLAYER, BUT ELSEWHERE",
            _entities(scene.known_elsewhere, describe, placement=scene.placement_of),
        ),
    )


def _character(
    player: Entity,
    location: Entity,
    inventory: Sequence[Entity],
    describe: EntityRenderer,
) -> str:
    held = "\n".join(
        _with_state(
            f"- {_label(item)} — {item.brief}{_detail(item)}",
            entity_state(item, describe),
            "  ",
        )
        for item in sorted(inventory, key=lambda item: item.name)
    )
    line = _with_state(
        f"{_label(player)} — {player.brief} — at {_label(location)}",
        entity_state(player, describe),
    )
    return f"{line}\ninventory:\n{held or '- (none)'}"


def _entities(
    entities: Sequence[Entity],
    describe: EntityRenderer,
    *,
    placement: Callable[[Entity], str],
) -> str:
    return (
        "\n".join(
            _with_state(
                _headline(entity, placement(entity)) + _detail(entity),
                entity_state(entity, describe),
                "  ",
            )
            for entity in entities
        )
        or "- (none)"
    )


def _exit_line(scene: BaseScene, way: Exit) -> str:
    labelled = f"[id={prompt_id(way.to)}]"
    locked = " — locked" if way.locked else ""
    unfound = " — the player has not found this way yet" if not way.known else ""
    return f"- {scene.exit_name(way)}{labelled}{locked}{unfound}"


def _threads(threads: Sequence[Thread]) -> str:
    return "\n".join(_thread_line(thread) for thread in threads) or "- (none)"


def _thread_line(thread: Thread) -> str:
    stage = f", stage {thread.stage}" if thread.stage is not None else ""
    clock = "" if thread.clock is None else f", clock {thread.clock.current}/{thread.clock.maximum}"
    line = f"- {thread.title}[id={prompt_id(thread.id)}] — status {thread.status}{stage}{clock}"
    return f"{line}\n  note: {thread.note}" if thread.note else line


def _headline(entity: Entity, placement: str) -> str:
    placed = f" — {placement}" if placement else ""
    return f"- {_label(entity)} ({kind_word(entity.kind)}){placed} — {entity.brief}"


def _detail(entity: Entity) -> str:
    if entity.detail is None:
        return ""
    described = f"\n  detail: {entity.detail.description}" if entity.detail.description else ""
    reached = (
        f"\n  when reached: {entity.detail.when_reached}" if entity.detail.when_reached else ""
    )
    return f"{described}{reached}"


def _label(entity: Entity) -> str:
    return f"{entity.name}[id={prompt_id(entity.id)}]"


def entity_state(entity: Entity, describe: EntityRenderer) -> str:
    """Traits are core fiction and the engine never sees them; both reach the prompt here."""
    parts = [describe(entity)]
    if entity.traits:
        parts.append("traits: " + ", ".join(_trait(held) for held in entity.traits))
    return "\n".join(part for part in parts if part)


def _trait(trait: Trait) -> str:
    name = f"{trait.name}[id={trait.id}]"
    return name + (f" — {trait.text}" if trait.text else "")


def _with_state(line: str, state: str, indent: str = "") -> str:
    if not state:
        return line
    block = "\n".join(f"{indent}  {row}" for row in state.splitlines())
    return f"{line}\n{indent}state:\n{block}"


_PROMPTS_DIR = Path(__file__).parent / "prompts"

DIRECTOR = engine_text(_PROMPTS_DIR / "director.md")
CORE_ADVISOR = engine_text(_PROMPTS_DIR / "core_advisor.md")
NARRATOR = engine_text(_PROMPTS_DIR / "narrator.md")


def director_instructions(engine_instructions: str) -> str:
    return f"{DIRECTOR}\n\n{engine_instructions}"


def advisor_instructions(engine_instructions: str) -> str:
    return f"{CORE_ADVISOR}\n\n{engine_instructions}"
