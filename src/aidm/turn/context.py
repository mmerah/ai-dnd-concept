from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path

from aidm.content.io import engine_text
from aidm.engines.core import AdvancementOffer, Engine, EntityRenderer
from aidm.state.entities import Entity, EntityId, Exit, Frozen, Trait, kind_word
from aidm.state.model import Game, ScenarioMeta, Thread, WorldState


class BaseScene(Frozen):
    player: Entity
    location: Entity
    inventory: tuple[Entity, ...]
    here: tuple[Entity, ...]
    known_elsewhere: tuple[Entity, ...]
    placements: dict[EntityId, str]
    exits: tuple[Exit, ...] = ()
    exit_names: dict[EntityId, str] = {}

    def placement_of(self, entity: Entity) -> str:
        return self.placements[entity.id]

    def exit_name(self, way: Exit) -> str:
        return self.exit_names[way.to]


class SceneSnapshot(BaseScene):
    hidden: tuple[Entity, ...]
    canon: tuple[Entity, ...]
    party: tuple[EntityId, ...]
    threads: tuple[Thread, ...] = ()
    notes: tuple[str, ...] = ()

    @classmethod
    def from_game(cls, state: Game, notes: tuple[str, ...] = ()) -> "SceneSnapshot":
        world = state.world
        player = state.player
        location = world.require_kind(state.player_location, "location")
        canon = tuple(world.entities)
        by_id = {entity.id: entity for entity in canon}
        shown = [entity for entity in canon if entity.id != player.id]
        inventory = world.children(player.id, "item")
        carried_ids = {item.id for item in inventory}
        placed = [
            entity for entity in shown if entity.id not in carried_ids and entity.id != location.id
        ]
        locations = {entity.id: world.location_of(entity) for entity in placed}
        party = tuple(world.party)
        exit_names = {way.to: world.require(way.to).name for way in location.exits}
        exits = tuple(sorted(location.exits, key=lambda way: exit_names[way.to]))
        return cls(
            player=player,
            location=location,
            inventory=inventory,
            here=tuple(
                entity
                for entity in shown
                if entity.known and locations.get(entity.id) == location.id
            ),
            known_elsewhere=tuple(
                entity
                for entity in shown
                if entity.known and entity.id in locations and locations[entity.id] != location.id
            ),
            hidden=_reachable_hidden(world, location),
            canon=canon,
            placements=_placements(by_id, canon, frozenset(by_id), party, player.id),
            exits=exits,
            exit_names=exit_names,
            party=party,
            threads=tuple(
                sorted(
                    (thread for thread in world.threads if thread.status != "resolved"),
                    key=lambda thread: thread.title,
                )
            ),
            notes=notes,
        )

    def catalogue(self) -> tuple[Entity, ...]:
        return tuple(entity for entity in self.canon if entity.id != self.player.id)


def _reachable_hidden(world: WorldState, here: Entity) -> tuple[Entity, ...]:
    """Unknown canon a turn could touch: here, one exit away, or a signposted location."""
    near = {here.id, *(way.to for way in here.exits)}
    signposted = {way.to for entity in world.entities if entity.known for way in entity.exits}
    return tuple(
        entity
        for entity in world.entities
        if not entity.known and (world.location_of(entity) in near or entity.id in signposted)
    )


class VisibleScene(BaseScene):
    """The Narrator's view: it holds no unrevealed entity and names none, by construction."""

    @classmethod
    def revealed_from(cls, snapshot: SceneSnapshot) -> "VisibleScene":
        by_id = {entity.id: entity for entity in snapshot.canon}
        shown = (
            snapshot.player,
            snapshot.location,
            *snapshot.inventory,
            *snapshot.here,
            *snapshot.known_elsewhere,
        )
        met = frozenset(entity.id for entity in snapshot.canon if entity.known)
        known_exits = tuple(way for way in snapshot.exits if way.known)
        return cls(
            player=_undetailed(snapshot.player),
            location=_undetailed(snapshot.location),
            inventory=tuple(_undetailed(item) for item in snapshot.inventory),
            here=tuple(_undetailed(entity) for entity in snapshot.here),
            known_elsewhere=tuple(_undetailed(entity) for entity in snapshot.known_elsewhere),
            placements=_placements(by_id, shown, met, snapshot.party, snapshot.player.id),
            exits=known_exits,
            exit_names={way.to: snapshot.exit_name(way) for way in known_exits},
        )


def _placements(
    by_id: Mapping[EntityId, Entity],
    entities: Iterable[Entity],
    nameable: frozenset[EntityId],
    party: tuple[EntityId, ...],
    player_id: EntityId,
) -> dict[EntityId, str]:
    return {entity.id: _placement(entity, by_id, nameable, party, player_id) for entity in entities}


def _placement(
    entity: Entity,
    by_id: Mapping[EntityId, Entity],
    nameable: frozenset[EntityId],
    party: tuple[EntityId, ...],
    player_id: EntityId,
) -> str:
    """A placement names its holder only where the reader may be told that holder exists."""
    if entity.id in party:
        return "travelling with the player"
    holder = None if entity.parent_id is None else by_id[entity.parent_id]
    if holder is None or holder.id not in nameable:
        return ""
    if holder.kind == "location":
        return f"at {holder.name}"
    return "carried" if holder.id == player_id else f"held by {holder.name}"


def _undetailed(entity: Entity) -> Entity:
    """`detail.when_reached` is canon authored before it is reached, so the Narrator gets none."""
    return entity.model_copy(update={"detail": None})


def render_director(
    scene: SceneSnapshot,
    describe: EntityRenderer,
    scenario: ScenarioMeta,
    prompt: str,
    *,
    resumed: str = "",
) -> str:
    # The Director writes no prose, so the canon side leaks nothing by reaching it.
    decided = (("THE PLAYER'S DECISION, ALREADY RESOLVED", resumed),) if resumed else ()
    return _sections(
        (
            *_scene_sections(scene, describe, scenario),
            (
                "EXISTS BUT THE PLAYER DOES NOT KNOW IT YET",
                _entities(scene.hidden, describe, placement=scene.placement_of),
            ),
            ("ACTIVE THREADS", _threads(scene.threads)),
            ("NOTES FROM THE RULES", "\n".join(f"- {note}" for note in scene.notes) or "- (none)"),
            *decided,
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


def render_proposal(engine: Engine, state: Game, offer: AdvancementOffer, intent: str) -> str:
    subject = state.world.require(offer.subject_id)
    sections = (
        ("ON OFFER", offer.prompt),
        ("RULES TEXT", offer.text),
        ("THE CHARACTER", f"{subject.name}\n{entity_state(subject, engine.renderer(state))}"),
        ("WHAT THE PLAYER WANTS", intent),
    )
    return "\n\n".join(f"{title}\n{body}" for title, body in sections if body)


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
    labelled = f"[id={way.to}]"
    locked = " — locked" if way.locked else ""
    unfound = " — the player has not found this way yet" if not way.known else ""
    return f"- {scene.exit_name(way)}{labelled}{locked}{unfound}"


def _threads(threads: Sequence[Thread]) -> str:
    return "\n".join(_thread_line(thread) for thread in threads) or "- (none)"


def _thread_line(thread: Thread) -> str:
    stage = f", stage {thread.stage}" if thread.stage is not None else ""
    clock = "" if thread.clock is None else f", clock {thread.clock.current}/{thread.clock.maximum}"
    line = f"- {thread.title}[id={thread.id}] — status {thread.status}{stage}{clock}"
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
    return f"{entity.name}[id={entity.id}]"


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


def player_scene(state: Game) -> VisibleScene:
    """What any player-facing surface may see, stripped of unrevealed canon by construction."""
    return VisibleScene.revealed_from(SceneSnapshot.from_game(state))
