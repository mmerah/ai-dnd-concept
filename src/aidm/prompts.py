import json
from collections.abc import Callable, Iterable, Sequence

from .base import PLAYER_ID, Entity, EntityId, Frozen, Kind
from .growth import GrowthRequest
from .world import Exchange, GameState, ScenarioMeta, WorldState

type EntityRenderer = Callable[[Entity], str]
type Placement = Callable[[Entity], str]
type Label = Callable[[Entity], str]


class BaseScene(Frozen):
    player: Entity
    location: Entity
    inventory: tuple[Entity, ...]
    here: tuple[Entity, ...]
    known_elsewhere: tuple[Entity, ...]
    placements: dict[EntityId, str]

    def placement_of(self, entity: Entity) -> str:
        return self.placements[entity.id]


class SceneSnapshot(BaseScene):
    hidden: tuple[Entity, ...]
    canon: WorldState

    @classmethod
    def of(cls, state: GameState) -> "SceneSnapshot":
        world = state.world
        player = state.player
        location = world.require_kind(state.player_location, "location")
        shown = [entity for entity in world.entities() if entity.id != PLAYER_ID]
        inventory = world.children(PLAYER_ID, "item")
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
            hidden=tuple(entity for entity in shown if not entity.known),
            canon=world,
            placements=_placements(world, world.entities(), frozenset(world.all_ids())),
        )

    def catalogue(self) -> tuple[Entity, ...]:
        return tuple(entity for entity in self.canon.entities() if entity.id != PLAYER_ID)


class VisibleScene(BaseScene):
    """The Narrator's view: it holds no unrevealed entity and names none, by construction."""

    @classmethod
    def of(cls, snapshot: SceneSnapshot) -> "VisibleScene":
        canon = snapshot.canon
        shown = (
            snapshot.player,
            snapshot.location,
            *snapshot.inventory,
            *snapshot.here,
            *snapshot.known_elsewhere,
        )
        met = frozenset(entity.id for entity in canon.entities() if entity.known)
        return cls(
            player=_undetailed(snapshot.player),
            location=_undetailed(snapshot.location),
            inventory=tuple(_undetailed(item) for item in snapshot.inventory),
            here=tuple(_undetailed(entity) for entity in snapshot.here),
            known_elsewhere=tuple(_undetailed(entity) for entity in snapshot.known_elsewhere),
            placements=_placements(canon, shown, met),
        )


def _placements(
    world: WorldState,
    entities: Iterable[Entity],
    nameable: frozenset[EntityId],
) -> dict[EntityId, str]:
    return {entity.id: _placement(entity, world, nameable) for entity in entities}


def _placement(entity: Entity, world: WorldState, nameable: frozenset[EntityId]) -> str:
    """A placement names its holder only where the reader may be told that holder exists."""
    holder = world.parent_of(entity)
    if holder is None or holder.id not in nameable:
        return ""
    if holder.kind == "location":
        return f"at {holder.name}"
    return "carried" if holder.id == PLAYER_ID else f"held by {holder.name}"


def _undetailed(entity: Entity) -> Entity:
    """`detail.hook` is authored as canon the player has not reached, so the Narrator gets none."""
    return entity.model_copy(update={"detail": None})


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
    player: Entity,
    location: Entity,
    inventory: Sequence[Entity],
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
    if speaker is None or speaker.kind != "actor":
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


CORE_DIRECTOR = """You are the DIRECTOR of a tabletop roleplaying game. Decide what should happen \
this turn and propose typed mechanics; never write player-facing prose.

You alone are shown what exists but the player does not know yet. Use it: when something already \
in the world answers what the player is after, steer them to it. Always prefer existing canon to \
anything new, and never invent a named person, place, or item yourself.

Every entity is shown as `name[id=...]`, and each carries where it is. The lists separate what is \
HERE WITH THE PLAYER from what is known but ELSEWHERE. The player can only see, address, take \
from, or hand things to who and what is here; to involve someone elsewhere, move the player or \
move that NPC here first. Wherever a field asks for an id, use the exact id from the brackets — \
for known and unrevealed entities alike, never the name.

`intent` — 1-3 sentences for the Narrator: what the player attempted and what is at stake. Never \
state outcomes, numbers, or dice; the Narrator learns the result elsewhere.

`tone` — a few words of mood for the Narrator. Atmosphere only, never outcomes: "tense and \
hushed", not "they find the map".

`speaker_id` — the id of the NPC the player is addressing, or null if none. It must be an NPC the \
player already knows AND who is here with them; never one they have not met or who is elsewhere.

The selected rules engine defines the complete mechanics list and validates every reference."""

NARRATOR = """You are the NARRATOR of a tabletop roleplaying game. Write what the player \
experiences in second person, present tense, in 2-4 vivid sentences. The Director's intent is a \
plan; WHAT HAPPENED is committed truth and always wins.

Every visible entity's `state` is its exact rules state after WHAT HAPPENED. Use it to keep the \
fiction accurate and make meaningful state perceptible: wounds, pressure, injury, conditions, \
spent capabilities, armour, and similar facts should affect what you describe. Translate state \
into natural fiction instead of reciting hit points, armour class, modifiers, dice, ids, or other \
raw mechanics. Never invent an outcome unsupported by WHAT HAPPENED. If a speaker is given, write \
their reply as dialogue. Output prose only."""

MAINTAINER = """You are the MAINTAINER of a tabletop roleplaying world. Request an entry for every \
named person, place, or item introduced by the narration but absent from the catalogue. Give the \
exact name used and a one-sentence brief consistent with the narration.

- `location`: for a person or item, name the place they are — a location already in the catalogue, \
or one you request this same turn (if they are somewhere new, request that location too). Leave it \
null to place them where the player is, and for a location entry itself.
- Match loosely: a name already in the catalogue in any spelling is not new, and neither is \
something the catalogue already describes under a different name. You are shown each entry's brief \
plus any fuller detail, hook, and exact rules state so you can recognise it under a new description.
- WHAT HAPPENED lists what the engine already recorded this turn; anything covered there is not new.
- Ignore unnamed background detail, scenery, crowds, and objects nobody could interact with.
- Returning no requests is normal and is the right answer most turns."""

CREATOR = """You flesh out one requested world entity without contradicting the scenario, \
catalogue, or narration. The catalogue includes existing entities' fuller detail, hooks, and exact \
rules state; use comparable entries to keep your detail concrete and consistent. `description` \
gives two concise sentences of usable detail. `hook` gives one sentence about how it may matter \
later. Invent no additional named entities."""
