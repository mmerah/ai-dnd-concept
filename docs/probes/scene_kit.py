"""Probe: the throwaway scene kit. change_world arms, prompts and the scene bar.
Proven by a live 5-turn run: 0 invalid, 0 refused calls. Has no apply_scene or scene_spent.
Reference only — PLAN.md phase 2 copies from this."""
"""Throwaway scene kit: state, change_world arms, prompts, scene bar."""
from typing import Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class Mutable(BaseModel):
    model_config = ConfigDict(extra="forbid")

Kind = Literal["actor", "item", "prop"]

class Trait(Frozen):
    id: str
    name: str
    text: str = ""

class Sheet(Mutable):
    """Loner-flavoured sheet, enough to be real."""
    concept: str = ""
    skills: tuple[str, ...] = ()
    frailties: tuple[str, ...] = ()
    gear: tuple[str, ...] = ()
    luck: int = 6

class Entity(Mutable):
    id: str
    kind: Kind
    name: str
    brief: str
    known: bool = False
    traits: list[Trait] = Field(default_factory=list)
    sheet: Sheet | None = None
    carried_by: str | None = None

class Scene(Frozen):
    id: str
    title: str
    situation: str = Field(min_length=40)
    present: tuple[str, ...] = ()
    hidden: tuple[str, ...] = ()
    note: str = ""

class Thread(Mutable):
    id: str
    title: str
    status: Literal["active", "resolved", "dormant"] = "active"
    note: str = ""

class SceneState(Mutable):
    cast: dict[str, Entity] = Field(default_factory=dict)
    played: tuple[Scene, ...] = ()
    current: Scene
    threads: dict[str, Thread] = Field(default_factory=dict)
    companions: list[str] = Field(default_factory=list)
    player_id: str
    source: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        for key, one in self.cast.items():
            if key != one.id:
                raise ValueError(f"entity {one.id!r} filed under {key!r}")
        for who in (*self.current.present, *self.current.hidden):
            if who not in self.cast:
                raise ValueError(f"scene names {who!r}, not in the cast")
        if self.player_id not in self.cast:
            raise ValueError("the player is not in the cast")
        return self

    def require(self, entity_id: str) -> Entity:
        one = self.cast.get(entity_id)
        if one is None:
            raise ValueError(f"unknown id {entity_id!r}. Use only ids you were shown.")
        return one

# ---------------- change_world arms ----------------

class Reveal(Frozen):
    """Make a hidden entity known when the player notices, finds, or reaches it."""
    verb: Literal["reveal"]
    entity_id: str = Field(description="Exact id of an entity listed under HIDDEN HERE.")

class Enter(Frozen):
    """Bring a cast member into the current scene."""
    verb: Literal["enter"]
    entity_id: str = Field(description="Exact id of a cast member not already here.")

class Leave(Frozen):
    """Take a cast member out of the current scene."""
    verb: Literal["leave"]
    entity_id: str = Field(description="Exact id of someone here.")

class MoveItem(Frozen):
    """Move an item: to the player, to someone here, or loose in the scene."""
    verb: Literal["move_item"]
    item_id: str = Field(description="Exact id of an item here or carried.")
    to: str = Field(description="`player`, `scene`, or the exact id of an actor here.")

class ImproviseItem(Frozen):
    """Give the player an ordinary object not already in the world."""
    verb: Literal["improvise_item"]
    name: str = Field(description="The object's name, such as `a handful of gravel`.")

class AddTrait(Frozen):
    """Add a lasting condition or quality to an entity."""
    verb: Literal["add_trait"]
    entity_id: str = Field(description="Exact entity id. An actor must be here.")
    name: str = Field(min_length=1, description="Display name, such as `Battle Worn`.")
    text: str = Field(description="The effect in plain language.")

class RemoveTrait(Frozen):
    """Remove a lasting condition that has ended."""
    verb: Literal["remove_trait"]
    entity_id: str = Field(description="Exact entity id.")
    trait_id: str = Field(description="Exact id of one of its traits.")

class Kill(Frozen):
    """Record that an actor has died. What they carried falls loose here."""
    verb: Literal["kill"]
    actor_id: str = Field(description="Exact id of the actor who died. They must be here.")

class JoinParty(Frozen):
    """An actor here starts travelling with the player."""
    verb: Literal["join_party"]
    actor_id: str = Field(description="Exact id of the actor joining.")

class LeaveParty(Frozen):
    """A companion stops travelling with the player."""
    verb: Literal["leave_party"]
    actor_id: str = Field(description="Exact id of the companion leaving.")

class AdvanceThread(Frozen):
    """Update an active storyline's status or private note."""
    verb: Literal["advance_thread"]
    thread_id: str = Field(description="Exact id of an ACTIVE THREAD.")
    status: Literal["active", "resolved", "dormant"] | None = None
    note: str | None = None

WorldChange = (
    Reveal | Enter | Leave | MoveItem | ImproviseItem | AddTrait
    | RemoveTrait | Kill | JoinParty | LeaveParty | AdvanceThread
)

class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb",
        description="The one world change to apply; `verb` picks the change.",
    )

class RollQuestion(Frozen):
    """Roll Chance against Risk for one closed dramatic question."""
    question: str = Field(description="The closed question the dice settle.")
    actor_id: str = Field(description="Exact id of who is acting.")
    risk: str = Field(description="What goes wrong on a bad roll, in one line.")

# ---------------- apply ----------------

def apply_change(state: SceneState, change: WorldChange) -> str:
    cur = state.current
    here = set(cur.present)
    match change:
        case Reveal():
            one = state.require(change.entity_id)
            if change.entity_id not in cur.hidden:
                raise ValueError(f"{change.entity_id!r} is not hidden here")
            one.known = True
            state.current = cur.model_copy(update={
                "hidden": tuple(x for x in cur.hidden if x != change.entity_id),
                "present": (*cur.present, change.entity_id)})
            return f"learned of the {one.kind} {one.name}[{one.id}]"
        case Enter():
            one = state.require(change.entity_id)
            if change.entity_id in here:
                raise ValueError(f"{one.name} is already here")
            one.known = True
            state.current = cur.model_copy(update={"present": (*cur.present, one.id)})
            return f"{one.name}[{one.id}] arrives"
        case Leave():
            one = state.require(change.entity_id)
            if one.id not in here:
                raise ValueError(f"{one.name} is not here")
            state.current = cur.model_copy(update={
                "present": tuple(x for x in cur.present if x != one.id)})
            return f"{one.name}[{one.id}] leaves"
        case MoveItem():
            item = state.require(change.item_id)
            if item.kind != "item":
                raise ValueError(f"{item.id!r} is a {item.kind}, not an item")
            if change.to == "player":
                item.carried_by, item.known = state.player_id, True
                return f"the player took {item.name}[{item.id}]"
            if change.to == "scene":
                item.carried_by = None
                return f"{item.name}[{item.id}] is left here"
            holder = state.require(change.to)
            if holder.id not in here:
                raise ValueError(f"{holder.name} is not here")
            item.carried_by = holder.id
            return f"{item.name}[{item.id}] passes to {holder.name}"
        case ImproviseItem():
            new_id = change.name.lower().replace(" ", "-")[:32].strip("-")
            if new_id in state.cast:
                raise ValueError(f"id {new_id!r} already exists")
            state.cast[new_id] = Entity(id=new_id, kind="item", name=change.name,
                                        brief=change.name, known=True,
                                        carried_by=state.player_id)
            return f"new item: {change.name}[{new_id}]"
        case AddTrait():
            one = state.require(change.entity_id)
            tid = change.name.lower().replace(" ", "-")
            if any(t.id == tid for t in one.traits):
                raise ValueError(f"{one.name} already carries {change.name!r}")
            one.traits.append(Trait(id=tid, name=change.name, text=change.text))
            return f"{one.name}[{one.id}] gained the trait {change.name}[{tid}]"
        case RemoveTrait():
            one = state.require(change.entity_id)
            held = next((t for t in one.traits if t.id == change.trait_id), None)
            if held is None:
                carried = ", ".join(t.id for t in one.traits) or "(none)"
                raise ValueError(f"{one.name} has no trait {change.trait_id!r}. Has: {carried}")
            one.traits.remove(held)
            return f"{one.name}[{one.id}] lost the trait {held.name}"
        case Kill():
            one = state.require(change.actor_id)
            if one.id not in here:
                raise ValueError(f"{one.name} is not here")
            one.traits.append(Trait(id="dead", name="Dead"))
            for item in state.cast.values():
                if item.carried_by == one.id:
                    item.carried_by = None
            if one.id in state.companions:
                state.companions.remove(one.id)
            return f"{one.name}[{one.id}] is dead"
        case JoinParty():
            one = state.require(change.actor_id)
            if one.id not in here:
                raise ValueError(f"{one.name} is not here")
            if one.id in state.companions:
                raise ValueError(f"{one.name} already travels with the player")
            state.companions.append(one.id)
            return f"{one.name}[{one.id}] travels with the player"
        case LeaveParty():
            one = state.require(change.actor_id)
            if one.id not in state.companions:
                raise ValueError(f"{one.name} does not travel with the player")
            state.companions.remove(one.id)
            return f"{one.name}[{one.id}] no longer travels with the player"
        case AdvanceThread():
            th = state.threads.get(change.thread_id)
            if th is None:
                known = ", ".join(state.threads) or "(none)"
                raise ValueError(f"unknown thread {change.thread_id!r}. Threads: {known}")
            th.status = change.status or th.status
            if change.note is not None:
                th.note = change.note
            return f"thread {th.title}[{th.id}] — {th.status} — {th.note}"

# ---------------- prompts ----------------

def _sheet_rows(one: Entity) -> str:
    if one.sheet is None:
        return ""
    s = one.sheet
    bits = [f"concept: {s.concept}" if s.concept else "",
            f"skills: {', '.join(s.skills)}" if s.skills else "",
            f"frailties: {', '.join(s.frailties)}" if s.frailties else "",
            f"gear: {', '.join(s.gear)}" if s.gear else "",
            f"luck: {s.luck}"]
    return "; ".join(b for b in bits if b)

def _line(state: SceneState, one: Entity) -> str:
    parts = [f"- {one.name}[{one.id}] — {one.brief}"]
    if rows := _sheet_rows(one):
        parts.append(f"  {rows}")
    if one.traits:
        parts.append("  traits: " + ", ".join(f"{t.name}[{t.id}]" for t in one.traits))
    if one.carried_by:
        parts.append(f"  carried by {one.carried_by}")
    if one.id in state.companions:
        parts.append("  travels with the player")
    return "\n".join(parts)

def render_master(state: SceneState, action: str) -> str:
    cur = state.current
    player = state.cast[state.player_id]
    present = [state.cast[i] for i in cur.present if i != state.player_id]
    hidden = [state.cast[i] for i in cur.hidden]
    carried = [e for e in state.cast.values() if e.carried_by == state.player_id]
    threads = [t for t in state.threads.values() if t.status == "active"]
    return "\n\n".join([
        f"SCENE:\n{cur.title}\n{cur.situation}",
        f"YOU PLAY FOR:\n{_line(state, player)}",
        "CARRYING:\n" + ("\n".join(_line(state, e) for e in carried) or "- (none)"),
        "HERE WITH THE PLAYER:\n" + ("\n".join(_line(state, e) for e in present) or "- (none)"),
        "HIDDEN HERE (the player has not found these):\n"
        + ("\n".join(_line(state, e) for e in hidden) or "- (none)"),
        "ACTIVE THREADS:\n"
        + ("\n".join(f"- {t.title}[{t.id}] — {t.note}" for t in threads) or "- (none)"),
        f"DIRECTOR NOTE (never narrate this):\n{cur.note or '(none)'}",
        f"PLAYER ACTION:\n{action}",
    ])

def render_worldsmith(state: SceneState, intent: str, include: tuple[str, ...],
                      guidance: str, opening: bool = False) -> str:
    if opening:
        history = "(no scenes yet — write the opening)"
        cast = "(no cast yet — write the people and things this scene needs)"
    else:
        history = "\n\n".join(
            f"SCENE {i+1}: {s.title}\n{s.situation}" for i, s in enumerate((*state.played, state.current)))
        cast = "\n".join(_line(state, e) for e in state.cast.values())
    threads = "\n".join(f"- {t.title}[{t.id}] — {t.status} — {t.note}"
                        for t in state.threads.values()) or "- (none)"
    return "\n\n".join([
        "You are the WORLDSMITH. Write the next scene of a solo tabletop game.",
        f"SOURCE MATERIAL:\n{state.source}",
        f"SCENES SO FAR:\n{history}",
        f"THE WHOLE CAST:\n{cast}",
        f"THREADS:\n{threads}",
        f"ENGINE GUIDANCE:\n{guidance}",
        f"WHAT THE GAME MASTER THINKS COMES NEXT:\n{intent}",
        f"FACES TO BRING BACK (a hint, not an order):\n{', '.join(include) or '(none)'}",
    ])

# ---------------- the scene bar ----------------

def scene_unmet(scene: Scene, new_cast: dict[str, Entity], state: SceneState,
                opening: bool) -> list[str]:
    unmet: list[str] = []
    others = [i for i in (*scene.present, *scene.hidden) if i != state.player_id]
    if len(scene.situation) < 80:
        unmet.append("a situation of real substance")
    if not others:
        unmet.append("at least one cast member besides the player")
    if not scene.hidden:
        unmet.append("at least one hidden entity — something to find")
    if not opening:
        held = set(state.cast)
        if not any(i in held for i in others):
            unmet.append("at least one existing cast member brought back")
    return unmet
