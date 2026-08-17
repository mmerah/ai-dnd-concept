import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path

from aidm.content.store import engine_text
from aidm.engines.advancement import Offer
from aidm.engines.loader import Engine, EntityRenderer
from aidm.engines.sheets import SheetBase
from aidm.engines.vocabulary import HOOK_EFFECTS_CARD, WORLD_CALLS, card
from aidm.state.base import Entity, EntityId, Trait
from aidm.state.world import GameState, Memory, ScenarioMeta, Thread

from .scene import BaseScene, Exit, SceneSnapshot, VisibleScene


def render_director(
    scene: SceneSnapshot,
    describe: EntityRenderer,
    scenario: ScenarioMeta,
    prompt: str,
    happened: str = "",
    preface: str = "",
) -> str:
    # The Director writes no prose, so the canon side leaks nothing by reaching it.
    canon = (
        (
            "EXISTS BUT THE PLAYER DOES NOT KNOW IT YET",
            _entities(scene.hidden, describe, placement=scene.placement_of),
        ),
        ("ACTIVE THREADS", _threads(scene.threads)),
        ("MEMORIES", _memories(scene)),
        ("SCENARIO NOTES", "\n".join(f"- {note}" for note in scene.notes) or "- (none)"),
    )
    # The scene is already the one the earlier beats left behind, so what happened comes last.
    so_far = (("WHAT JUST HAPPENED", happened),) if happened else ()
    again = (("ASKED AGAIN", preface),) if preface else ()
    return _sections(
        (
            *_scene_sections(scene, describe, scenario, ids=True),
            *canon,
            ("PLAYER ACTION", prompt),
            *so_far,
            *again,
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
            *_scene_sections(scene, describe, scenario, ids=False),
            ("WHAT HAPPENED", evidence),
            ("PLAYER ACTION", prompt),
        )
    )


def render_worldkeeper(
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
            (
                "EVERYTHING THAT EXISTS",
                _entities(scene.catalogue(), describe, placement=scene.placement_of, detail=True),
            ),
            ("ALREADY REMEMBERED", _memories(scene)),
            ("ACTIVE THREADS", _threads(scene.threads)),
            ("PLAYER", prompt),
            ("WHAT HAPPENED", evidence),
            ("NARRATION", narration),
        )
    )


def render_expander(
    scene: SceneSnapshot,
    describe: EntityRenderer,
    scenario: ScenarioMeta,
    *,
    context: str,
    request: str,
) -> str:
    """The Expander writes records and never prose, so all of canon may reach it."""
    return _sections(
        (
            _premise(scenario),
            ("THE SOURCE", context),
            (
                "PLAYER CHARACTER",
                _character(scene.player, scene.location, scene.inventory, describe, ids=True),
            ),
            (
                "EVERYTHING THAT EXISTS",
                _entities(scene.catalogue(), describe, placement=scene.placement_of, detail=True),
            ),
            (
                "EXITS FROM WHERE THE PLAYER STANDS",
                "\n".join(_exit_line(exit) for exit in scene.exits) or "- (none)",
            ),
            ("ACTIVE THREADS", _threads(scene.threads)),
            ("WHAT THE DIRECTOR NEEDS", request),
        )
    )


def render_proposal(engine: Engine[SheetBase], state: GameState, offer: Offer, intent: str) -> str:
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
    scene: BaseScene, describe: EntityRenderer, scenario: ScenarioMeta, *, ids: bool
) -> tuple[tuple[str, str], ...]:
    return (
        _premise(scenario),
        (
            "PLAYER CHARACTER",
            _character(scene.player, scene.location, scene.inventory, describe, ids=ids),
        ),
        (
            "HERE WITH THE PLAYER",
            _entities(scene.here, describe, placement=scene.placement_of, ids=ids),
        ),
        (
            "EXITS FROM HERE",
            "\n".join(_exit_line(exit, ids=ids) for exit in scene.exits) or "- (none)",
        ),
        (
            "KNOWN TO THE PLAYER, BUT ELSEWHERE",
            _entities(scene.known_elsewhere, describe, placement=scene.placement_of, ids=ids),
        ),
    )


def _character(
    player: Entity,
    location: Entity,
    inventory: Sequence[Entity],
    describe: EntityRenderer,
    *,
    ids: bool,
) -> str:
    held = "\n".join(
        _with_state(
            f"- {_label(item, ids=ids)} — {item.brief}",
            entity_state(item, describe, ids=ids),
            "  ",
        )
        for item in sorted(inventory, key=lambda item: item.name)
    )
    line = _with_state(
        f"{_label(player, ids=ids)} — {player.brief} — at {_label(location, ids=ids)}",
        entity_state(player, describe, ids=ids),
    )
    return f"{line}\ninventory:\n{held or '- (none)'}"


def _entities(
    entities: Sequence[Entity],
    describe: EntityRenderer,
    *,
    placement: Callable[[Entity], str],
    ids: bool = True,
    detail: bool = False,
) -> str:
    return (
        "\n".join(
            _with_state(
                _headline(entity, placement(entity), ids=ids) + (_detail(entity) if detail else ""),
                entity_state(entity, describe, ids=ids),
                "  ",
            )
            for entity in entities
        )
        or "- (none)"
    )


def _exit_line(exit: Exit, *, ids: bool = True) -> str:
    labelled = f"[id={prompt_id(exit.location_id)}]" if ids else ""
    locked = " — locked" if exit.locked else ""
    unfound = " — the player has not found this way yet" if not exit.known else ""
    return f"- {exit.name}{labelled}{locked}{unfound}"


def _threads(threads: Sequence[Thread]) -> str:
    return "\n".join(_thread_line(thread) for thread in threads) or "- (none)"


def _thread_line(thread: Thread) -> str:
    stage = f" at {thread.stage}" if thread.stage is not None else ""
    clock = (
        "" if thread.clock is None else f" [clock {thread.clock.current}/{thread.clock.maximum}]"
    )
    line = f"- {thread.title}[id={prompt_id(thread.id)}] — {thread.status}{stage}{clock}"
    return f"{line}\n  note: {thread.note}" if thread.note else line


def _memories(scene: SceneSnapshot) -> str:
    by_id = {entity.id: entity for entity in scene.canon}
    return "\n".join(_memory_line(memory, by_id) for memory in scene.memories) or "- (none)"


def _memory_line(memory: Memory, by_id: Mapping[EntityId, Entity]) -> str:
    whose = "the world" if memory.owner is None else _label(by_id[memory.owner], ids=True)
    return f"- {whose} remembers: {memory.text}"


def _headline(entity: Entity, placement: str, *, ids: bool = True) -> str:
    kind = "npc" if entity.kind == "actor" else entity.kind
    placed = f" — {placement}" if placement else ""
    return f"- {_label(entity, ids=ids)} ({kind}){placed} — {entity.brief}"


def _detail(entity: Entity) -> str:
    if entity.detail is None:
        return ""
    described = f"\n  detail: {entity.detail.description}" if entity.detail.description else ""
    hooked = f"\n  hook: {entity.detail.hook}" if entity.detail.hook else ""
    return f"{described}{hooked}"


def _label(entity: Entity, *, ids: bool) -> str:
    return f"{entity.name}[id={prompt_id(entity.id)}]" if ids else entity.name


def entity_state(entity: Entity, describe: EntityRenderer, *, ids: bool = True) -> str:
    """Traits are core fiction and the engine never sees them; both reach the prompt here."""
    parts = [describe(entity)]
    if entity.traits:
        parts.append("traits: " + ", ".join(_trait(held, ids=ids) for held in entity.traits))
    return "\n".join(part for part in parts if part)


def _trait(trait: Trait, *, ids: bool) -> str:
    name = f"{trait.name}[id={trait.id}]" if ids else trait.name
    return name + (f" — {trait.text}" if trait.text else "")


def _with_state(line: str, state: str, indent: str = "") -> str:
    if not state:
        return line
    block = "\n".join(f"{indent}  {row}" for row in state.splitlines())
    return f"{line}\n{indent}state:\n{block}"


_PROMPTS_DIR = Path(__file__).parent / "prompts"

DIRECTOR = engine_text(_PROMPTS_DIR / "director.md")
# Not roles of their own: the Director's mid-turn framing, rendered into the prompt's own
# ASKED AGAIN section rather than prepended to its instructions.
BEAT = engine_text(_PROMPTS_DIR / "beat.md")
SETTLE = engine_text(_PROMPTS_DIR / "settle.md")
CORE_ADVISOR = engine_text(_PROMPTS_DIR / "core_advisor.md")
NARRATOR = engine_text(_PROMPTS_DIR / "narrator.md")
WORLDKEEPER = engine_text(_PROMPTS_DIR / "worldkeeper.md")
EXPANDER = (
    f"{engine_text(_PROMPTS_DIR / 'expander.md')}\n\n"
    f"{card('Hook effects', HOOK_EFFECTS_CARD, WORLD_CALLS)}"
)
