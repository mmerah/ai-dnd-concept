import json
from collections.abc import Callable, Iterable, Mapping, Sequence

from aidm.engines.loader import EntityRenderer
from aidm.state.base import PLAYER_ID, Entity, EntityId, Frozen, Kind
from aidm.state.turn import SceneDirective
from aidm.state.world import LOCKED_TAG, GameState, ScenarioMeta, Thread

type Placement = Callable[[Entity], str]
type Label = Callable[[Entity], str]


class Exit(Frozen):
    location_id: EntityId
    name: str
    known: bool
    locked: bool


class BaseScene(Frozen):
    player: Entity
    location: Entity
    inventory: tuple[Entity, ...]
    here: tuple[Entity, ...]
    known_elsewhere: tuple[Entity, ...]
    placements: dict[EntityId, str]
    exits: tuple[Exit, ...] = ()

    def placement_of(self, entity: Entity) -> str:
        return self.placements[entity.id]


class SceneSnapshot(BaseScene):
    hidden: tuple[Entity, ...]
    canon: tuple[Entity, ...]
    party: tuple[EntityId, ...]
    threads: tuple[Thread, ...] = ()
    notes: tuple[str, ...] = ()

    @classmethod
    def of(cls, state: GameState) -> "SceneSnapshot":
        world = state.world
        player = state.player
        location = world.require_kind(state.player_location, "location")
        canon = tuple(world.entities())
        by_id = {entity.id: entity for entity in canon}
        shown = [entity for entity in canon if entity.id != PLAYER_ID]
        inventory = world.children(PLAYER_ID, "item")
        carried_ids = {item.id for item in inventory}
        placed = [
            entity for entity in shown if entity.id not in carried_ids and entity.id != location.id
        ]
        locations = {entity.id: world.location_of(entity) for entity in placed}
        party = world.party()
        exits = tuple(
            sorted(
                (
                    Exit(
                        location_id=relation.far_end(location.id),
                        name=world.require(relation.far_end(location.id)).name,
                        known=relation.known,
                        locked=LOCKED_TAG in relation.tags,
                    )
                    for relation in world.connections(location.id)
                ),
                key=lambda exit: exit.name,
            )
        )
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
            canon=canon,
            placements=_placements(by_id, canon, frozenset(by_id), party),
            exits=exits,
            party=party,
            threads=tuple(
                sorted(
                    (thread for thread in state.threads.values() if thread.status != "resolved"),
                    key=lambda thread: thread.title,
                )
            ),
            notes=state.pending_notes,
        )

    def catalogue(self) -> tuple[Entity, ...]:
        return tuple(entity for entity in self.canon if entity.id != PLAYER_ID)


class VisibleScene(BaseScene):
    """The Narrator's view: it holds no unrevealed entity and names none, by construction."""

    @classmethod
    def of(cls, snapshot: SceneSnapshot) -> "VisibleScene":
        by_id = {entity.id: entity for entity in snapshot.canon}
        shown = (
            snapshot.player,
            snapshot.location,
            *snapshot.inventory,
            *snapshot.here,
            *snapshot.known_elsewhere,
        )
        met = frozenset(entity.id for entity in snapshot.canon if entity.known)
        return cls(
            player=_undetailed(snapshot.player),
            location=_undetailed(snapshot.location),
            inventory=tuple(_undetailed(item) for item in snapshot.inventory),
            here=tuple(_undetailed(entity) for entity in snapshot.here),
            known_elsewhere=tuple(_undetailed(entity) for entity in snapshot.known_elsewhere),
            placements=_placements(by_id, shown, met, snapshot.party),
            exits=tuple(exit for exit in snapshot.exits if exit.known),
        )


def _placements(
    by_id: Mapping[EntityId, Entity],
    entities: Iterable[Entity],
    nameable: frozenset[EntityId],
    party: tuple[EntityId, ...],
) -> dict[EntityId, str]:
    return {entity.id: _placement(entity, by_id, nameable, party) for entity in entities}


def _placement(
    entity: Entity,
    by_id: Mapping[EntityId, Entity],
    nameable: frozenset[EntityId],
    party: tuple[EntityId, ...],
) -> str:
    """A placement names its holder only where the reader may be told that holder exists."""
    if entity.id in party:
        return "travelling with the player"
    holder = None if entity.parent_id is None else by_id[entity.parent_id]
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
    directive: SceneDirective | None = None,
) -> str:
    # Two views of one scene: the Scene Director reads the canon side itself, the Rules Director
    # gets only what the directive passed on — including just the threads it named.
    canon = (
        (
            (
                "EXISTS BUT THE PLAYER DOES NOT KNOW IT YET",
                _entities(scene.hidden, describe, placement=scene.placement_of),
            ),
            ("ACTIVE THREADS", _threads(scene.threads)),
            ("SCENARIO NOTES", _notes(scene)),
        )
        if directive is None
        else (("SCENE DIRECTIVE", _directive(directive, scene, describe)),)
    )
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
            ("EXITS FROM HERE", _exits(scene)),
            (
                "KNOWN TO THE PLAYER, BUT ELSEWHERE",
                _entities(scene.known_elsewhere, describe, placement=scene.placement_of),
            ),
            *canon,
            ("PLAYER ACTION", prompt),
        )
    )


def render_narrator(
    scene: VisibleScene,
    describe: EntityRenderer,
    scenario: ScenarioMeta,
    *,
    focus: str,
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
            ("EXITS FROM HERE", _exits(scene)),
            (
                "KNOWN TO THE PLAYER, BUT ELSEWHERE",
                _entities(scene.known_elsewhere, describe, placement=scene.placement_of),
            ),
            ("THE DIRECTOR'S PLAN — what was meant, not what happened", focus),
            ("SPEAKER", _speaker(scene, speaker_id)),
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
            ("EVERYTHING THAT EXISTS", _catalogue(scene, describe)),
            ("PLAYER", prompt),
            ("WHAT HAPPENED", evidence),
            ("NARRATION", narration),
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


def _exits(scene: BaseScene) -> str:
    return "\n".join(_exit_line(exit) for exit in scene.exits) or "- (none)"


def _exit_line(exit: Exit) -> str:
    locked = " — locked" if exit.locked else ""
    unfound = " — the player has not found this way yet" if not exit.known else ""
    return f"- {exit.name}[id={prompt_id(exit.location_id)}]{locked}{unfound}"


def _threads(threads: Sequence[Thread]) -> str:
    return "\n".join(_thread_line(thread) for thread in threads) or "- (none)"


def _thread_line(thread: Thread) -> str:
    stage = f" at {thread.stage}" if thread.stage is not None else ""
    line = f"- {thread.title}[id={prompt_id(thread.id)}] — {thread.status}{stage}"
    return f"{line}\n  note: {thread.note}" if thread.note else line


def _directive(directive: SceneDirective, scene: SceneSnapshot, describe: EntityRenderer) -> str:
    """An empty pressure or stakes is a quiet turn, and says so by being absent rather than blank:
    a heading with nothing after it reads as an omission the Rules Director should fill."""
    threads = tuple(thread for thread in scene.threads if thread.id in directive.threads)
    found = tuple(entity for entity in scene.hidden if entity.id in directive.reveal)
    lines = [f"focus: {directive.focus}"]
    if directive.pressure:
        lines.append(f"pressure: {directive.pressure}")
    if directive.stakes:
        lines.append(f"stakes: {directive.stakes}")
    if not directive.pressure and not directive.stakes:
        lines.append("nothing pushes back and nothing is at stake: this turn is quiet")
    lines.append(f"threads it serves:\n{_threads(threads)}")
    if found:
        lines.append(
            "to bring into play — the player has not found these yet:\n"
            f"{_entities(found, describe, placement=scene.placement_of)}"
        )
    return "\n".join(lines)


def _notes(scene: SceneSnapshot) -> str:
    return "\n".join(f"- {note}" for note in scene.notes) or "- (none)"


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
    block = "\n".join(f"{indent}  {row}" for row in state.splitlines())
    return f"{line}\n{indent}state:\n{block}"


_DIRECTOR_OPENING = """You are the DIRECTOR of a tabletop roleplaying game. Decide what should \
happen this turn and answer with one plan; never write player-facing prose. The engine resolves \
your plan: it makes every roll, pays every cost, and picks the outcome. You never state a roll's \
result — branches for outcomes that do not occur simply never apply."""

_IDS = """Every entity is shown as `name[id=...]`, and each carries where it is. The lists \
separate what is HERE WITH THE PLAYER from what is known but ELSEWHERE. The player can only see, \
address, take from, or hand things to who and what is here; to involve someone elsewhere, move \
them here with a `move-actor` effect first. Wherever a field asks for an id, use the exact id from \
the brackets — for known and unrevealed entities alike, never the name."""

_EXITS = """EXITS FROM HERE lists the ways out of the player's location; when the location has any \
exits at all, `move-actor` for the player only reaches a place listed there. Walking an exit the \
player has not found yet is one plan, not two: write the `reveal-relation` and the `move-actor` \
together in the same `effects`, in that order, and add an `untag-relation` before them when the \
way is `locked` and the fiction opens it. `add-relation` records a new tie when the fiction makes \
one: a passage discovered between two places (`connected`), or an NPC who joins the player \
(`party-member`, the actor as `source` and `player` as `target`). A party member travels with the \
player automatically."""

_PLAN_FIELDS = """The plan is the whole turn:

`action` — the single action resolved this turn, or null when nothing mechanical happens. Its \
actor is whoever the fiction puts on the acting side: when the player's words have someone else \
act — a monster lunging at them — plan that actor's action, not a reaction by the player. The \
engine computes and applies the action's own arithmetic — rolls, damage, healing, costs: never \
write those anywhere in the plan. Everything else an outcome changes — a condition taking hold or \
ending, something revealed, someone moving — happens only if a branch or an effect writes it; the \
engine never adds it for you.

`branches` — fiction consequences keyed by the action's outcome labels, applied only to the one \
outcome that occurs. At most one branch per label, and only labels the action allows.

`effects` — consequences that happen whatever the action settles: discoveries, movement, \
possessions changing hands.

You write no prose at all: the directive already said what the turn is about, and the Narrator \
writes what the player reads."""

_RETRY = """A rejected plan comes back with the reason; fix exactly that and answer again. Call \
`read_content` first when you plan from a spell, feature, or stat block whose wording you cannot \
quote."""

_DIRECTIVE_BRIEF = """The SCENE DIRECTIVE decides what this turn is about; realize it mechanically \
without contradicting it, and add nothing it did not ask for. It already weighed whether the turn \
should carry pressure: when it says the turn is quiet, resolve what the player did and let the \
turn be small — no action, no complication, no extra effect. Never invent a named person, place, \
or item (a `gain-improvised-item` effect for an incidental object is the one exception).

The directive is also your only view of what the player has not found and of the scenario's \
storylines. Anything under "to bring into play" is something the player does not know about yet: \
write a `reveal` effect for its id this turn, before any effect or branch that names it. The \
threads it lists are the only ones you may `advance-thread`, naming a thread's `status`, its \
`stage`, or both when the fiction genuinely moves one on."""

RULES_DIRECTOR = "\n\n".join(
    (_DIRECTOR_OPENING, _DIRECTIVE_BRIEF, _IDS, _EXITS, _PLAN_FIELDS, _RETRY)
)

SCENE_DIRECTOR = """You are the SCENE DIRECTOR of a tabletop roleplaying game. Decide what this \
turn is about and answer with one directive; the Rules Director after you turns it into the \
mechanical plan and the Narrator writes the prose. Never write player-facing prose, and never name \
a roll, a rule, or an outcome.

You alone are shown what exists but the player does not know yet, the scenario's ACTIVE THREADS, \
and its SCENARIO NOTES. Use them: when something already in the world answers what the player is \
after, steer the turn to it. Always prefer existing canon to anything new, and never invent a \
named person, place, or item. SCENARIO NOTES are instructions from the scenario about what just \
changed; follow them this turn — they are shown once.

Drive the game forward: when a turn would otherwise be flat, put something at stake — a \
complication, a cost, a threat drawing closer. Judge that honestly, because the Rules Director \
acts on whatever you write: a turn where the player looks around, rests, or asks a question \
carries no pressure and nothing at stake, and saying so keeps it quiet. Inventing pressure for \
such a turn makes the game roll dice over nothing.

`focus` — 1-2 sentences on what the player is reaching for and what the turn should be about.

`pressure` — 1-2 sentences on what pushes back: a complication, a cost, a threat. Never a result. \
Leave it empty when nothing should push back.

`stakes` — one sentence on what is won or lost, empty when nothing is.

`threads` — the ids of the ACTIVE THREADS this turn serves, exactly as they appear in the \
brackets, and none when none apply.

`reveal` — the ids of the things the player DOES NOT KNOW YET that this turn puts in front of \
them: what they are searching for and would find, what steps into view, what a question they just \
asked is answered by. The Rules Director cannot see these and reveals nothing you do not name, so \
a discovery you leave out never happens. Name none when the fiction finds nothing.

`speaker_id` — the id of the NPC the player is addressing, or null if none. It must be an NPC the \
player already knows AND who is here with them; never one they have not met or who is elsewhere."""

NARRATOR = """You are the NARRATOR of a tabletop roleplaying game. Write what the player \
experiences in second person, present tense, in 2-4 vivid sentences. The Director's intent is a \
plan; WHAT HAPPENED is committed truth and always wins.

Every visible entity's `state` is its exact rules state after WHAT HAPPENED. Use it to keep the \
fiction accurate and make meaningful state perceptible: wounds, pressure, injury, conditions, \
spent capabilities, armour, and similar facts should affect what you describe. Translate state \
into natural fiction instead of reciting hit points, armour class, modifiers, dice, ids, or other \
raw mechanics. Never invent an outcome unsupported by WHAT HAPPENED. If a speaker is given, write \
their reply as dialogue. Output prose only."""

WORLDKEEPER = """You are the WORLDKEEPER of a tabletop roleplaying world. Create an entry for \
every named person, place, or item introduced by the narration but absent from the catalogue, \
giving the exact name used and a one-sentence brief consistent with the narration.

- `detail.description` gives two concise sentences of usable detail; `detail.hook` gives one \
sentence about how it may matter later. Neither may contradict the scenario, catalogue, or \
narration, and neither may introduce a further named entity. The catalogue shows existing entries' \
fuller detail, hooks, and exact rules state; use comparable entries to keep yours concrete.
- `location`: for a person or item, name the place they are — a location already in the catalogue, \
or one you create this same turn (if they are somewhere new, create that location too). Leave it \
null to place them where the player is, and for a location entry itself.
- Match loosely: a name already in the catalogue in any spelling is not new, and neither is \
something the catalogue already describes under a different name.
- WHAT HAPPENED lists what the engine already recorded this turn; anything covered there is not new.
- Ignore unnamed background detail, scenery, crowds, and objects nobody could interact with.
- Creating nothing is normal and is the right answer most turns."""
