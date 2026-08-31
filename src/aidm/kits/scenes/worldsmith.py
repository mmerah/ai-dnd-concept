from collections.abc import Iterable

from pydantic import BaseModel, Field

from aidm.core.entities import EntityId, Slug, slug
from aidm.kits.scenes.state import Entity, Frozen, Scene, SceneCanon, SceneState, Thread

MIN_SITUATION = 80


class SceneDraft[S: BaseModel](Frozen):
    """What the worldsmith returns. Ids arrive as free text so a wrong one can be matched against
    a cast name before it is refused; code owns the scene id and never asks for the player."""

    place: Slug
    title: str
    question: str = Field(min_length=10)
    situation: str = Field(min_length=MIN_SITUATION)
    present: tuple[str, ...] = ()
    hidden: tuple[str, ...] = ()
    secret: str = ""
    cast: dict[EntityId, Entity[S]] = Field(default_factory=dict)
    threads: dict[Slug, Thread] = Field(default_factory=dict)


def scene_refusal[S: BaseModel](
    draft: SceneDraft[S], world: SceneState[S] | None = None
) -> str | None:
    missing = _scene_unmet(draft, world)
    return None if not missing else "the scene needs " + "; ".join(missing)


def opening_canon[S: BaseModel](draft: SceneDraft[S], source: str) -> SceneCanon[S]:
    return SceneCanon[S](
        cast=draft.cast,
        opening=Scene(
            id=slug(draft.title, ()),
            place=draft.place,
            title=draft.title,
            question=draft.question,
            situation=draft.situation,
            present=tuple(_resolve(draft.present, draft.cast, "present")),
            hidden=tuple(_resolve(draft.hidden, draft.cast, "hidden")),
            secret=draft.secret,
        ),
        threads=draft.threads,
        source=source,
    )


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
        question=draft.question,
        situation=draft.situation,
        present=(*kept, *present),
        hidden=tuple(hidden),
        secret=draft.secret,
    )

    world.cast = cast
    for one in present:
        cast[one].known = True
    world.threads.update(draft.threads)
    world.played = (*world.played, world.current)
    world.current = scene
    world.opened_at = turn
    world.spent, world.settled = "", False


def _scene_unmet[S: BaseModel](
    draft: SceneDraft[S], world: SceneState[S] | None = None
) -> list[str]:
    """No world means the opening: nobody exists yet, and no id can be the player's."""
    held = {} if world is None else world.cast
    player_id = None if world is None else world.player_id
    known = {**held, **draft.cast}
    others = [
        one
        for one in (*draft.present, *draft.hidden)
        if player_id is None or resolved_id(one, known) != player_id
    ]
    standing = [
        one
        for one in (*(() if world is None else world.threads.values()), *draft.threads.values())
        if one.status != "resolved"
    ]
    unmet: list[str] = []
    if not others:
        unmet.append("at least one cast member besides the player")
    if not standing:
        unmet.append("at least one standing thread, opened here or already running")
    if world is not None and not any(resolved_id(one, held) is not None for one in others):
        unmet.append("at least one existing cast member brought back")
    if stray := sorted(one for one in others if resolved_id(one, known) is None):
        unmet.append(f"ids that exist; these name nobody: {stray}")
    # `situation` is read to the player, so naming a hidden entity there hands them the find.
    if told := sorted(_named_in(draft.situation, draft.hidden, known)):
        unmet.append(f"a situation that does not name what is hidden: {told}")
    return unmet


def _named_in[S: BaseModel](
    situation: str, hidden: Iterable[str], cast: dict[EntityId, Entity[S]]
) -> list[str]:
    """Multi-word names only: a prop called `Bell` shares its word with any bell tower."""
    said = situation.casefold()
    found = (cast[one] for wanted in hidden if (one := resolved_id(wanted, cast)) is not None)
    return [one.name for one in found if " " in one.name.strip() and one.name.casefold() in said]


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
