from collections.abc import Iterable

from pydantic import BaseModel, Field

from aidm.kits.scenes.state import Entity, Frozen, Scene, SceneState, Thread
from aidm.kits.scenes.views import SheetRows, entity_line, thread_lines
from aidm.state.entities import EntityId, Slug, slug

MIN_SITUATION = 80
SURPRISE = (
    "Surprise the player. Turn an established fact against them, or bring back something they "
    "have stopped thinking about. Surprise by recombining what exists, never by inventing what "
    "the source would not hold."
)


class SceneDraft[S: BaseModel](Frozen):
    """What the worldsmith returns. Ids arrive as free text so a wrong one can be matched against
    a cast name before it is refused; code owns the scene id and never asks for the player."""

    place: Slug
    title: str
    situation: str = Field(min_length=MIN_SITUATION)
    present: tuple[str, ...] = ()
    hidden: tuple[str, ...] = ()
    note: str = ""
    cast: dict[EntityId, Entity[S]] = Field(default_factory=dict)
    threads: dict[Slug, Thread] = Field(default_factory=dict)


def scene_unmet[S: BaseModel](
    draft: SceneDraft[S], world: SceneState[S], *, opening: bool
) -> list[str]:
    """The scene bar. A scene that misses one of these is re-prompted with the reason."""
    known = {**world.cast, **draft.cast}
    others = [
        one for one in (*draft.present, *draft.hidden) if resolved_id(one, known) != world.player_id
    ]
    standing = [
        one
        for one in (*world.threads.values(), *draft.threads.values())
        if one.status != "resolved"
    ]
    unmet: list[str] = []
    if not others:
        unmet.append("at least one cast member besides the player")
    if not draft.hidden:
        unmet.append("at least one hidden entity — something to find")
    if not standing:
        unmet.append("at least one standing thread, opened here or already running")
    if not opening and not any(resolved_id(one, world.cast) is not None for one in others):
        unmet.append("at least one existing cast member brought back")
    if stray := sorted(one for one in others if resolved_id(one, known) is None):
        unmet.append(f"ids that exist; these name nobody: {stray}")
    return unmet


def resolved_id[S: BaseModel](wanted: str, cast: dict[EntityId, Entity[S]]) -> EntityId | None:
    """Ids are the worldsmith's failure mode: an unknown one matches a cast name before refusal."""
    if wanted in cast:
        return EntityId(wanted)
    matches = [one.id for one in cast.values() if one.name.casefold() == wanted.casefold()]
    return EntityId(matches[0]) if len(matches) == 1 else None


def apply_scene[S: BaseModel](world: SceneState[S], draft: SceneDraft[S], turn: int) -> None:
    """Every refusal lands before the first write: a rejected scene leaves the world alone."""
    for one, held in draft.cast.items():
        if one in world.cast:
            raise ValueError(f"the scene rewrites {one!r}, who is already in the cast")
        if one != held.id:
            raise ValueError(f"entity {held.id!r} is filed under {one!r}")
    cast: dict[EntityId, Entity[S]] = {**world.cast, **draft.cast}
    # The player and their companions are in every scene; naming them is not how they get there.
    followers = [world.player_id, *world.companions]
    present = [one for one in _resolve(draft.present, cast, "present") if one not in followers]
    hidden = [one for one in _resolve(draft.hidden, cast, "hidden") if one not in followers]
    if overlap := sorted(set(present) & set(hidden)):
        raise ValueError(f"the scene lists {overlap} as both present and hidden")
    if met := sorted(one for one in hidden if cast[one].known):
        raise ValueError(f"the scene hides {met}, whom the player has already met")
    carried = [one.id for one in cast.values() if one.carried_by in followers]
    kept = [one for one in (*followers, *carried) if one not in present and one not in hidden]
    scene = Scene(
        id=slug(draft.title, {one.id for one in (*world.played, world.current)}),
        place=draft.place,
        title=draft.title,
        situation=draft.situation,
        present=(*kept, *present),
        hidden=tuple(hidden),
        note=draft.note,
    )

    world.cast = cast
    for one in present:
        cast[one].known = True
    world.threads.update(draft.threads)
    world.played = (*world.played, world.current)
    world.current = scene
    world.opened_at = turn
    world.spent = ""


def _resolve[S: BaseModel](
    wanted: Iterable[str], cast: dict[EntityId, Entity[S]], where: str
) -> list[EntityId]:
    found: list[EntityId] = []
    for one in wanted:
        matched = resolved_id(one, cast)
        if matched is None:
            raise ValueError(f"the scene lists {one!r} as {where}, and no such id or name exists")
        if matched not in found:
            found.append(matched)
    return found


def render_worldsmith[S: BaseModel](
    world: SceneState[S],
    intent: str,
    include: tuple[str, ...],
    guidance: str,
    rows: SheetRows,
    *,
    opening: bool = False,
) -> str:
    """The whole material for one scene, assembled by code so no role has to remember it."""
    if opening:
        history = "(no scenes yet — write the opening)"
        cast = "(no cast yet — write the people and things this scene needs)"
    else:
        history = "\n\n".join(
            f"SCENE {number}: {one.title} ({one.place})\n{one.situation}"
            for number, one in enumerate((*world.played, world.current), start=1)
        )
        cast = "\n".join(entity_line(world, one, rows, where=True) for one in world.cast.values())
    return "\n\n".join(
        f"{name}:\n{body}"
        for name, body in (
            ("SOURCE MATERIAL", world.source or "(none — write from the threads and the cast)"),
            ("SCENES SO FAR", history),
            ("THE WHOLE CAST", cast),
            ("THREADS", thread_lines(world.threads.values(), standing_only=False)),
            ("ENGINE GUIDANCE", guidance),
            ("WHAT COMES NEXT", intent),
            ("FACES TO BRING BACK (a hint, not an order)", ", ".join(include) or "(none)"),
            ("STANDING INSTRUCTION", SURPRISE),
        )
    )
