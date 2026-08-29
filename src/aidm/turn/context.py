from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from aidm.content.io import engine_text
from aidm.engines.core import EntityRenderer
from aidm.state.entities import Entity, EntityId, Exit, Frozen, Trait, kind_word
from aidm.state.model import Game, ScenarioMeta, Thread, WorldState


class SceneSnapshot(Frozen):
    player: Entity
    location: Entity
    inventory: tuple[Entity, ...]
    here: tuple[Entity, ...]
    known_elsewhere: tuple[Entity, ...]
    hidden: tuple[Entity, ...]
    canon: Mapping[EntityId, Entity]
    party: tuple[EntityId, ...]
    exits: tuple[Exit, ...] = ()
    threads: tuple[Thread, ...] = ()
    notes: tuple[str, ...] = ()

    @classmethod
    def from_game(cls, state: Game, notes: tuple[str, ...] = ()) -> "SceneSnapshot":
        world = state.world
        player = state.player
        location = world.require_kind(state.player_location, "location")
        shown = [entity for entity in world.entities.values() if entity.id != player.id]
        inventory = world.children(player.id, "item")
        carried_ids = {item.id for item in inventory}
        placed = [
            entity for entity in shown if entity.id not in carried_ids and entity.id != location.id
        ]
        locations = {entity.id: world.location_of(entity) for entity in placed}
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
            canon=dict(world.entities),
            party=tuple(world.party),
            exits=tuple(sorted(location.exits, key=lambda way: world.require(way.to).name)),
            threads=tuple(
                sorted(
                    (thread for thread in world.threads.values() if thread.status != "resolved"),
                    key=lambda thread: thread.title,
                )
            ),
            notes=notes,
        )

    def catalogue(self) -> tuple[Entity, ...]:
        return tuple(entity for entity in self.canon.values() if entity.id != self.player.id)


def _reachable_hidden(world: WorldState, here: Entity) -> tuple[Entity, ...]:
    """Unknown canon a turn could touch: here, one exit away, or a signposted location."""
    near = {here.id, *(way.to for way in here.exits)}
    entities = world.entities.values()
    signposted = {way.to for entity in entities if entity.known for way in entity.exits}
    return tuple(
        entity
        for entity in entities
        if not entity.known and (world.location_of(entity) in near or entity.id in signposted)
    )


class VisibleScene(Frozen):
    """The Narrator's view: it holds no unrevealed entity and names none, by construction."""

    player: Entity
    location: Entity
    inventory: tuple[Entity, ...]
    here: tuple[Entity, ...]
    known_elsewhere: tuple[Entity, ...]
    canon: Mapping[EntityId, Entity]
    party: tuple[EntityId, ...]
    exits: tuple[Exit, ...] = ()

    @classmethod
    def revealed_from(cls, snapshot: SceneSnapshot) -> "VisibleScene":
        return cls(
            player=_undetailed(snapshot.player),
            location=_undetailed(snapshot.location),
            inventory=tuple(_undetailed(item) for item in snapshot.inventory),
            here=tuple(_undetailed(entity) for entity in snapshot.here),
            known_elsewhere=tuple(_undetailed(entity) for entity in snapshot.known_elsewhere),
            canon={
                entity_id: _undetailed(entity)
                for entity_id, entity in snapshot.canon.items()
                if entity.known
            },
            party=snapshot.party,
            exits=tuple(way for way in snapshot.exits if way.known),
        )


type Scene = SceneSnapshot | VisibleScene


def placement(scene: Scene, entity: Entity) -> str:
    """A placement names its holder only where the reader may be told that holder exists."""
    if entity.id in scene.party:
        return "travelling with the player"
    holder = None if entity.parent_id is None else scene.canon.get(entity.parent_id)
    if holder is None:
        return ""
    if holder.kind == "location":
        return f"at {holder.name}"
    return "carried" if holder.id == scene.player.id else f"held by {holder.name}"


def _undetailed(entity: Entity) -> Entity:
    """Both are canon authored for the Director before the scene, so the Narrator gets neither."""
    return entity.model_copy(update={"description": "", "when_reached": ""})


ANSWERED_BY_OPTION = (
    "The player chose the option above and the rules have applied it. Develop what it caused; "
    "do not settle it again."
)


def render_director(
    scene: SceneSnapshot,
    describe: EntityRenderer,
    scenario: ScenarioMeta,
    prompt: str,
    *,
    resumed: str = "",
) -> str:
    # The Director writes no prose, so the canon side leaks nothing by reaching it.
    # A chosen option is already applied: shown as its own words, a weak model settles it twice.
    ending = (
        (
            ("THE PLAYER'S DECISION, ALREADY RESOLVED", resumed),
            ("PLAYER ACTION", ANSWERED_BY_OPTION),
        )
        if resumed
        else (("PLAYER ACTION", prompt),)
    )
    return _sections(
        (
            *_scene_sections(scene, describe, scenario),
            (
                "EXISTS BUT THE PLAYER DOES NOT KNOW IT YET",
                _entities(scene, scene.hidden, describe),
            ),
            ("ACTIVE THREADS", _threads(scene.threads)),
            ("NOTES FROM THE RULES", "\n".join(f"- {note}" for note in scene.notes) or "- (none)"),
            *ending,
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


def _sections(parts: Iterable[tuple[str, str]]) -> str:
    return "\n\n".join(f"{name}:\n{body}" for name, body in parts)


def _premise(scenario: ScenarioMeta) -> tuple[str, str]:
    return "SCENARIO", f"{scenario.title}\n{scenario.premise}"


def _scene_sections(
    scene: Scene, describe: EntityRenderer, scenario: ScenarioMeta
) -> tuple[tuple[str, str], ...]:
    return (
        _premise(scenario),
        (
            "PLAYER CHARACTER",
            _character(scene.player, scene.location, scene.inventory, describe),
        ),
        (
            "HERE WITH THE PLAYER",
            _entities(scene, scene.here, describe),
        ),
        (
            "EXITS FROM HERE",
            "\n".join(_exit_line(scene, way) for way in scene.exits) or "- (none)",
        ),
        (
            "KNOWN TO THE PLAYER, BUT ELSEWHERE",
            _entities(scene, scene.known_elsewhere, describe),
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


def _entities(scene: Scene, entities: Sequence[Entity], describe: EntityRenderer) -> str:
    return (
        "\n".join(
            _with_state(
                _headline(entity, placement(scene, entity)) + _detail(entity),
                entity_state(entity, describe),
                "  ",
            )
            for entity in entities
        )
        or "- (none)"
    )


def _exit_line(scene: Scene, way: Exit) -> str:
    locked = " — locked" if way.locked else ""
    unfound = " — the player has not found this way yet" if not way.known else ""
    return f"- {scene.canon[way.to].name}[{way.to}]{locked}{unfound}"


def _threads(threads: Sequence[Thread]) -> str:
    return "\n".join(_thread_line(thread) for thread in threads) or "- (none)"


def _thread_line(thread: Thread) -> str:
    line = f"- {thread.title}[{thread.id}] — status {thread.status}"
    return f"{line}\n  note: {thread.note}" if thread.note else line


def _headline(entity: Entity, placement: str) -> str:
    placed = f" — {placement}" if placement else ""
    return f"- {_label(entity)} ({kind_word(entity.kind)}){placed} — {entity.brief}"


def _detail(entity: Entity) -> str:
    described = f"\n  detail: {entity.description}" if entity.description else ""
    reached = f"\n  when reached: {entity.when_reached}" if entity.when_reached else ""
    return f"{described}{reached}"


def _label(entity: Entity) -> str:
    return f"{entity.name}[{entity.id}]"


def entity_state(entity: Entity, describe: EntityRenderer) -> str:
    """Traits are core fiction and the engine never sees them; both reach the prompt here."""
    parts = [describe(entity)]
    if entity.traits:
        parts.append("traits: " + ", ".join(_trait(held) for held in entity.traits))
    return "\n".join(part for part in parts if part)


def _trait(trait: Trait) -> str:
    name = f"{trait.name}[{trait.id}]"
    return name + (f" — {trait.text}" if trait.text else "")


def _with_state(line: str, state: str, indent: str = "") -> str:
    if not state:
        return line
    block = "\n".join(f"{indent}  {row}" for row in state.splitlines())
    return f"{line}\n{indent}state:\n{block}"


_PROMPTS_DIR = Path(__file__).parent / "prompts"

DIRECTOR = engine_text(_PROMPTS_DIR / "director.md")
NARRATOR = engine_text(_PROMPTS_DIR / "narrator.md")


def director_instructions(engine_instructions: str) -> str:
    return f"{DIRECTOR}\n\n{engine_instructions}"


def player_scene(state: Game) -> VisibleScene:
    """What any player-facing surface may see, stripped of unrevealed canon by construction."""
    return VisibleScene.revealed_from(SceneSnapshot.from_game(state))
