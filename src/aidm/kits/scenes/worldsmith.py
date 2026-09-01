import json
from collections.abc import Iterable
from pathlib import Path
from typing import cast

from pydantic import BaseModel, Field

from aidm.core.entities import EntityId, Frozen, Slug
from aidm.core.facts import Fact
from aidm.core.io import engine_text
from aidm.core.model import WorldsmithAnswer
from aidm.core.tools import schema_of
from aidm.core.views import sections
from aidm.kits.entities import Entity, Thread
from aidm.kits.scenes.render import SheetRows, entity_line, thread_lines
from aidm.kits.scenes.state import Scene, SceneCanon, SceneRun, SceneState

MIN_SITUATION = 80
TAIL_EXCHANGES = 3
# The narrator's brief for a crossing; `{pursuit}` is what the player said they were going after.
CROSSING = (
    "The player is leaving WHAT THE PLAYER HAS READ for the place in SCENE. They asked for this: "
    '"{pursuit}"\n\n'
    "Write the crossing: a sentence of leaving, then the arrival. Cover the distance and the time "
    "in the fewest words that make it real, and end on what they see first. WHAT HAPPENED names "
    "anyone who travelled with them. They have not acted in the new place yet, so settle nothing."
)
SURPRISE = (
    "Surprise the player. Turn an established fact against them, or bring back something they "
    "have stopped thinking about. Surprise by recombining what exists, never by inventing what "
    "the source would not hold."
)
WORLDSMITH = engine_text(Path(__file__).parent / "prompts" / "worldsmith.md")


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


def arrival_brief(pursuit: str) -> str:
    return CROSSING.format(pursuit=pursuit)


def scene_refusal[S: BaseModel](
    draft: SceneDraft[S], world: SceneState[S] | None = None
) -> str | None:
    missing = _scene_unmet(draft, world)
    return None if not missing else "the scene needs " + "; ".join(missing)


def opening_canon[S: BaseModel](draft: SceneDraft[S], source: str) -> SceneCanon[S]:
    return SceneCanon[S](
        cast=draft.cast,
        opening=_scene(draft),
        present=_resolve(draft.present, draft.cast, "present"),
        hidden=_resolve(draft.hidden, draft.cast, "hidden"),
        threads=draft.threads,
        source=source,
    )


def resolved_id[S: BaseModel](wanted: str, cast: dict[EntityId, Entity[S]]) -> EntityId | None:
    """Ids are the worldsmith's failure mode: an unknown one matches a cast name before refusal."""
    if wanted in cast:
        return EntityId(wanted)
    matches = [one.id for one in cast.values() if one.name.casefold() == wanted.casefold()]
    return EntityId(matches[0]) if len(matches) == 1 else None


def apply_scene[S: BaseModel](world: SceneState[S], draft: SceneDraft[S]) -> None:
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
    world.cast = cast
    for one in present:
        cast[one].known = True
    # The author saw a snapshot while the current turn could advance existing threads.
    # Keep those committed values; only genuinely new authored ids belong in this scene.
    world.threads.update(
        (thread_id, thread)
        for thread_id, thread in draft.threads.items()
        if thread_id not in world.threads
    )
    world.runs.append(SceneRun(scene=_scene(draft), present=[*kept, *present], hidden=hidden))


async def write_next[S: BaseModel](
    world: SceneState[S],
    scene_type: type[SceneDraft[S]],
    intent: str,
    guidance: str,
    rows: SheetRows,
    answer: WorldsmithAnswer,
) -> SceneDraft[S]:
    def refusal(written: BaseModel) -> str | None:
        return scene_refusal(cast(SceneDraft[S], written), world)

    written = await answer(
        render_worldsmith(world, intent, guidance, rows, scene_type), scene_type, refusal
    )
    return cast(SceneDraft[S], written)


def install_scene[S: BaseModel](
    world: SceneState[S], written: SceneDraft[S], closed: tuple[Fact, ...]
) -> tuple[Fact, ...]:
    apply_scene(world, written.model_copy(deep=True))
    came = [world.require(one).name for one in world.companions]
    trace = f"the story moves to {written.title}"
    if came:
        trace += f", and {', '.join(came)} travels there with the player"
    opened = Fact(kind="scene_opened", trace=trace, told=True, card=f"New scene: {written.title}")
    return *closed, opened


def render_worldsmith[S: BaseModel](
    world: SceneState[S],
    intent: str,
    guidance: str,
    rows: SheetRows,
    answer: type[BaseModel],
) -> str:
    return _worldsmith(
        source=world.source,
        history=_history(world),
        cast="\n".join(entity_line(world, one, rows, where=True) for one in world.cast.values()),
        threads=thread_lines(world.threads.values(), standing_only=False),
        guidance=guidance,
        intent=intent,
        answer=answer,
    )


def render_opening(source: str, guidance: str, answer: type[BaseModel]) -> str:
    return _worldsmith(
        source=source,
        history="(no scenes yet — write the opening)",
        cast="(no cast yet — write the people and things this scene needs)",
        threads="- (none yet — open the first)",
        guidance=guidance,
        intent=(
            "Write the opening scene of this adventure: where the player starts, who is there, "
            "and what is waiting to be found."
        ),
        answer=answer,
    )


def _worldsmith(
    *,
    source: str,
    history: str,
    cast: str,
    threads: str,
    guidance: str,
    intent: str,
    answer: type[BaseModel],
) -> str:
    return sections(
        (
            ("YOUR ROLE", WORLDSMITH),
            ("SOURCE MATERIAL", source or "(none — write from the threads and the cast)"),
            ("SCENES SO FAR", history),
            ("THE WHOLE CAST", cast),
            ("THREADS", threads),
            ("ENGINE GUIDANCE", guidance),
            ("WHAT COMES NEXT", intent),
            ("STANDING INSTRUCTION", SURPRISE),
            ("ANSWER WITH", json.dumps(schema_of(answer), indent=2, ensure_ascii=False)),
        )
    )


def _history[S: BaseModel](world: SceneState[S]) -> str:
    return "\n\n".join(
        "\n".join(
            (
                f"SCENE {number}: {run.scene.title} ({run.scene.place})",
                f"the question: {run.scene.question}",
                run.scene.situation,
                "what happened: " + (_told(run) or "(nothing yet)"),
            )
        )
        for number, run in enumerate(world.runs, start=1)
    )


def _told(run: SceneRun) -> str:
    return "\n".join(f"> {one.prompt}\n{one.narration}" for one in run.exchanges[-TAIL_EXCHANGES:])


def _scene[S: BaseModel](draft: SceneDraft[S]) -> Scene:
    return Scene(
        place=draft.place,
        title=draft.title,
        question=draft.question,
        situation=draft.situation,
        secret=draft.secret,
    )


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
