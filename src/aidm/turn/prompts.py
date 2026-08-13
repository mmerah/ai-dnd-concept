import json
from collections.abc import Callable, Iterable, Mapping, Sequence

from aidm.engines.loader import AdvancementOffer, Engine, EntityRenderer
from aidm.state.base import PLAYER_ID, Entity, EntityId, Frozen, Trait
from aidm.state.turn import SceneDirective
from aidm.state.world import LOCKED_TAG, GameState, Memory, ScenarioMeta, Thread


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

    def voice(self, speaker_id: EntityId | None) -> Entity | None:
        """The one answer to who the Narrator may speak as: an actor this scene holds as here."""
        return next(
            (held for held in self.here if held.id == speaker_id and held.kind == "actor"), None
        )


class SceneSnapshot(BaseScene):
    hidden: tuple[Entity, ...]
    canon: tuple[Entity, ...]
    party: tuple[EntityId, ...]
    threads: tuple[Thread, ...] = ()
    memories: tuple[Memory, ...] = ()
    notes: tuple[str, ...] = ()

    @classmethod
    def of(cls, state: GameState) -> "SceneSnapshot":
        world = state.world
        player = state.player
        location = world.require_kind(state.player_location, "location")
        canon = tuple(world.entities.values())
        by_id = {entity.id: entity for entity in canon}
        shown = [entity for entity in canon if entity.id != PLAYER_ID]
        inventory = world.children(PLAYER_ID, "item")
        carried_ids = {item.id for item in inventory}
        placed = [
            entity for entity in shown if entity.id not in carried_ids and entity.id != location.id
        ]
        locations = {entity.id: world.location_of(entity) for entity in placed}
        party = world.party()
        present = {
            PLAYER_ID,
            location.id,
            *(held for held, place in locations.items() if place == location.id),
        }
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
                    (thread for thread in world.threads.values() if thread.status != "resolved"),
                    key=lambda thread: thread.title,
                )
            ),
            memories=tuple(
                memory
                for memory in world.memories.values()
                if memory.owner is None or memory.owner in present
            ),
            notes=world.pending_notes,
        )

    def catalogue(self) -> tuple[Entity, ...]:
        return tuple(entity for entity in self.canon if entity.id != PLAYER_ID)


def check_speaker(scene: SceneSnapshot, speaker_id: EntityId | None) -> str | None:
    """The player is addressed, never the speaker: losing this lets the Director voice them."""
    if speaker_id is None:
        return None
    if speaker_id == PLAYER_ID:
        return "speaker_id names another actor the player addresses, never the player."
    if not any(entity.id == speaker_id for entity in scene.canon):
        return f"unknown speaker id {speaker_id!r}. Use only ids you were shown, or null."
    if scene.voice(speaker_id) is None:
        return (
            f"speaker {speaker_id!r} must be an NPC the player has met and who is here with them. "
            "Use null if nobody is being addressed."
        )
    return None


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
    remembered = () if directive is not None else (("MEMORIES", _memories(scene)),)
    # Neither director writes prose, so the canon side leaks nothing by reaching both of them.
    canon = (
        (
            "EXISTS BUT THE PLAYER DOES NOT KNOW IT YET",
            _entities(scene.hidden, describe, placement=scene.placement_of),
        ),
        ("ACTIVE THREADS", _threads(scene.threads)),
        *remembered,
        ("SCENARIO NOTES", "\n".join(f"- {note}" for note in scene.notes) or "- (none)"),
    )
    steer = (
        () if directive is None else (("SCENE DIRECTIVE", _directive(directive, scene, describe)),)
    )
    return _sections(
        (
            *_scene_sections(scene, describe, scenario, ids=True),
            *canon,
            *steer,
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
            *_scene_sections(scene, describe, scenario, ids=False),
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


def render_proposal(engine: Engine, state: GameState, offer: AdvancementOffer, intent: str) -> str:
    player = state.player
    sections = (
        ("ON OFFER", offer.prompt),
        ("RULES TEXT", offer.text),
        ("THE CHARACTER", f"{player.name}\n{entity_state(player, engine.renderer(state))}"),
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
    line = f"- {thread.title}[id={prompt_id(thread.id)}] — {thread.status}{stage}"
    return f"{line}\n  note: {thread.note}" if thread.note else line


def _memories(scene: SceneSnapshot) -> str:
    by_id = {entity.id: entity for entity in scene.canon}
    return "\n".join(_memory_line(memory, by_id) for memory in scene.memories) or "- (none)"


def _memory_line(memory: Memory, by_id: Mapping[EntityId, Entity]) -> str:
    whose = "the world" if memory.owner is None else _label(by_id[memory.owner], ids=True)
    return f"- {whose} remembers: {memory.text}"


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


def _speaker(scene: VisibleScene, speaker_id: EntityId | None) -> str:
    """A speaker the turn moved out of the scene is fiction, not a fault: narration goes on."""
    speaker = scene.voice(speaker_id)
    if speaker is None:
        return "(none — narrate the scene)"
    return f"{speaker.name} — {speaker.brief}"


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


_DIRECTOR_OPENING = """You are the DIRECTOR of a tabletop roleplaying game. Decide what happens \
this turn and answer with one plan. Never write player-facing prose. The engine resolves the \
plan: it makes every roll, pays every cost, and picks the outcome. Never state a roll's result; \
branches for outcomes that do not occur never apply."""

_IDS = """Entities appear as `name[id=...]`, each with where it is. The lists separate what is \
HERE WITH THE PLAYER from what is known but ELSEWHERE. The player can only see, address, take \
from, or hand things to what is here; to involve someone elsewhere, first bring them here with a \
`move` effect. Wherever a field asks for an id, use the exact id from the brackets — for known \
and unrevealed entities alike, never the name."""

_EXITS = """EXITS FROM HERE lists the ways out of the player's location; when the location has \
any exits, `move` for the player only reaches a place listed there.
- Walking an exit the player has not found yet is one plan, not two: write a `relation-change` \
with `mode: reveal` and the `move` together in the same `effects`, in that order.
- Exit `locked` and the fiction opens it: add a `relation-change` with `mode: untag` before them.
- New tie the fiction makes: a `relation-change` with `mode: add` — a discovered passage \
between two places (`connected`), or an NPC joining the player (`party-member`, actor as \
`source`, `player` as `target`). A party member travels with the player automatically."""

_PLAN_FIELDS = """The plan is the whole turn:

`action` — the single action resolved this turn, or null when nothing mechanical happens. Its \
actor is whoever the fiction puts on the acting side: when the player's words have someone else \
act — a monster lunging at them — plan that actor's action, not a player reaction. \
Anything else an outcome changes — a condition starting or ending, a reveal, a move — happens \
only if a branch or an effect writes it; the engine never adds it.

`branches` — fiction consequences keyed by the action's outcome labels, applied only to the \
outcome that occurs. At most one branch per label, and only labels the action allows.

`effects` — consequences that happen whatever the action settles: discoveries, movement, \
possessions changing hands.

Write no prose: the Narrator writes what the player reads."""

_RETRY = """A rejected plan comes back with the reason; fix exactly that and answer again."""

_DIRECTIVE_BRIEF = """The SCENE DIRECTIVE decides what this turn is about. Realize it \
mechanically, do not contradict it, and add nothing it did not ask for.
- When it says the turn is quiet, resolve what the player did and keep the turn small: no \
action, no complication, no extra effect.
- Never invent a named person, place, or item; the one exception is `gain-improvised-item` for \
an incidental object.
- You see unrevealed canon and every storyline, but the directive decides which this turn \
touches.
- For each id under "to bring into play", write a `reveal` effect this turn, before any effect \
or branch that names it. Reveal nothing the directive did not name.
- `advance-thread` only the threads the directive lists, naming a thread's `status`, `stage`, \
or both when the fiction genuinely moves one on."""

RULES_DIRECTOR = "\n\n".join(
    (_DIRECTOR_OPENING, _DIRECTIVE_BRIEF, _IDS, _EXITS, _PLAN_FIELDS, _RETRY)
)

SCENE_DIRECTOR = """You are the SCENE DIRECTOR of a tabletop roleplaying game. Decide what this \
turn is about and answer with one directive; the Rules Director after you turns it into the \
mechanical plan and the Narrator writes the prose. Never write player-facing prose, and never \
name a roll, a rule, or an outcome.

You are shown what exists but the player does not know yet, the scenario's ACTIVE THREADS, and \
its SCENARIO NOTES. When something already in the world answers what the player is after, steer \
the turn to it. Prefer existing canon to anything new, and never invent a named person, place, or \
item. SCENARIO NOTES are instructions from the scenario about what just changed; follow them this \
turn — they are shown once.

Drive the game forward: when a turn would otherwise be flat, put something at stake — a \
complication, a cost, a threat drawing closer. Judge that honestly; the Rules Director acts on \
whatever you write. A turn where the player looks around, rests, or asks a question carries no \
pressure and nothing at stake; saying so keeps it quiet. Inventing pressure there makes the game \
roll dice over nothing.

`focus` — 1-2 sentences: what the player is reaching for and what the turn is about.

`pressure` — 1-2 sentences: what pushes back — a complication, a cost, a threat. Never a result. \
Empty when nothing should push back.

`stakes` — one sentence: what is won or lost. Empty when nothing is.

`threads` — the ids of the ACTIVE THREADS this turn serves, exactly as they appear in the \
brackets; none when none apply.

`reveal` — the ids of things the player DOES NOT KNOW YET that this turn puts in front of them: \
what they are searching for and would find, what steps into view, what answers a question they \
just asked. The Rules Director reveals nothing you do not name; a discovery you leave out never \
happens. Name none when the fiction finds nothing.

`speaker_id` — the id of the NPC the player is addressing, or null if none. It must be an NPC \
the player already knows AND who is here with them; never one unmet or elsewhere."""

CORE_ADVISOR = """You are the ADVISOR of a tabletop roleplaying game. The player has earned an \
advancement and says how they want to grow. Turn that into the exact changes their character sheet \
needs, and nothing else.

You write only the player's own character, each change carrying a short `why` the player will \
read before confirming. Stay inside what is ON OFFER: propose exactly the picks it asks for, and \
never a pick it does not list. Keep every change small, concrete, and grounded in \
the rules text you are given — invent no capability the text does not grant.

A change that breaks the rules comes back to you with the reason; fix that change and answer \
again."""

NARRATOR = """You are the NARRATOR of a tabletop roleplaying game. Write what the player \
experiences in second person, present tense, in 2-4 vivid sentences. The Director's intent is a \
plan; WHAT HAPPENED is committed truth and always wins.

Every visible entity's `state` is its exact rules state after WHAT HAPPENED. Keep the fiction \
accurate to it and make meaningful state perceptible: wounds, pressure, injury, conditions, spent \
capabilities, armour, and similar facts. Translate state into natural fiction; never recite hit \
points, armour class, modifiers, dice, ids, or other raw mechanics. Never invent an outcome \
unsupported by WHAT HAPPENED. If a speaker is given, write their reply as dialogue. Output prose \
only."""

WORLDKEEPER = """You are the WORLDKEEPER of a tabletop roleplaying world. Keep its records after \
the turn: enter what the narration introduced, remember what will still matter, and move the \
threads the turn advanced. Most turns record nothing at all, and empty lists are the right answer.

CREATIONS — an entry for every named person, place, or item the narration introduces that is \
absent from the catalogue, with the exact name used and a one-sentence brief consistent with the \
narration.
- `detail.description`: two concise sentences of usable detail. `detail.hook`: one sentence on \
how it may matter later. Neither may contradict the scenario, catalogue, or narration, and \
neither may introduce a further named entity. The catalogue shows existing entries' detail, \
hooks, and rules state; use comparable entries to keep yours concrete.
- `location`: for a person or item, the place they are — a location already in the catalogue, or \
one you create this same turn (create that location too if it is new). Null places them where the \
player is; null also for a location entry itself.
- Match loosely: a name already in the catalogue in any spelling is not new, and neither is \
something the catalogue already describes under a different name.
- Ignore unnamed background detail, scenery, crowds, and objects nobody could interact with.

MEMORIES — durable facts about people and places that will still matter many turns from now: what \
someone revealed, what a place turned out to be, a promise made or broken. Never a play-by-play of \
the turn.
- `owner_id`: the exact id of whoever carries the memory, or null when the world itself does.
- `text`: one concrete sentence, past tense.
- ALREADY REMEMBERED is what is kept for whoever is here; never write one of those again in other \
words.
- Keep none on most turns: a turn is worth a memory only when it changed what someone knows.

THREAD MOVES — an `advance-thread` for a thread in ACTIVE THREADS the turn plainly moved, naming \
its `status`, its `stage`, or both. Move nothing the narration merely hinted at, and never invent \
a stage the scenario has not used.

WHAT HAPPENED lists what the engine already recorded this turn; anything covered there is already \
kept and is not yours to record again."""
