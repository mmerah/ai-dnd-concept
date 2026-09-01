from collections.abc import Iterable, Mapping, Sequence

from pydantic import Field

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Mutable, Slug, require_unique
from aidm.core.facts import Fact
from aidm.core.play import Exchange
from aidm.engines.core import Entity
from aidm.engines.hub import Debrief, Offer, Stop, check_board

SCENE_TURN_CAP = 12
TAIL_EXCHANGES = 3
SPENT_NOTE = "This scene looks spent — {reason}. If its question is settled, call `next_scene`."
SCENE_SETTLED = Fact(
    kind="scene_settled",
    trace=(
        "this scene is settled. Bring it to a close, then ask the player what they want to "
        "pursue next — in the fiction, naming what the scene left open, never as a list of "
        "choices. They may also stay and keep playing here, so ask; do not push them out"
    ),
    told=True,
)
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


class Scene(Frozen):
    # Names the art cache entry, so returning to a place reuses its picture.
    place: Slug
    title: str
    # Public: the player reads it; settling it ends the scene.
    question: str = Field(min_length=10)
    situation: str = Field(min_length=40)
    # What `question` does not say: never narrated, never in a view.
    secret: str = ""
    debrief: Debrief | None = None  # the hub's word on the job just left; hub runs after the first


class SceneRun(Mutable):
    scene: Scene
    present: list[CheckedEntityId] = Field(default_factory=list)
    hidden: list[CheckedEntityId] = Field(default_factory=list)
    exchanges: list[Exchange] = Field(default_factory=list)
    # The game master has called the question answered; the player may move on, or play on.
    settled: bool = False
    # Why the scene looks finished already, written by the rule that settled it.
    spent: str = ""


def scene_spent(run: SceneRun, someone_dead: bool) -> str | None:
    """Deliberately blunt: catches only what no reading of the fiction can miss."""
    if run.spent:
        return run.spent
    if someone_dead:
        return "someone here is dead"
    if len(run.exchanges) >= SCENE_TURN_CAP:
        return f"{SCENE_TURN_CAP} turns have passed here"
    return None


def check_named(
    present: Sequence[EntityId], hidden: Sequence[EntityId], cast: Mapping[EntityId, Entity]
) -> None:
    require_unique("ids in the scene", (*present, *hidden))
    for who in (*present, *hidden):
        if who not in cast:
            raise ValueError(f"scene names {who!r}, who is not in the cast")
    for who in hidden:
        if cast[who].known:
            raise ValueError(f"{who!r} is hidden here but the player has already met them")
    for who in present:
        if not cast[who].known:
            raise ValueError(f"{who!r} is here but the player has not met them")


def arrival_brief(pursuit: str) -> str:
    return CROSSING.format(pursuit=pursuit)


def resolved_id(wanted: str, cast: Mapping[EntityId, Entity]) -> EntityId | None:
    """Ids are the worldsmith's failure mode: an unknown one matches a cast name before refusal."""
    if wanted in cast:
        return EntityId(wanted)
    matches = [one.id for one in cast.values() if one.name.casefold() == wanted.casefold()]
    return EntityId(matches[0]) if len(matches) == 1 else None


def resolve_ids(
    wanted: Iterable[str], cast: Mapping[EntityId, Entity], where: str
) -> list[EntityId]:
    found: list[EntityId] = []
    for one in wanted:
        matched = resolved_id(one, cast)
        if matched is None:
            raise ValueError(f"the scene lists {one!r} as {where}, and no such id or name exists")
        if matched not in found:
            found.append(matched)
    return found


def named_in(situation: str, hidden: Iterable[str], cast: Mapping[EntityId, Entity]) -> list[str]:
    """Multi-word names only: a prop called `Bell` shares its word with any bell tower."""
    said = situation.casefold()
    found = (cast[one] for wanted in hidden if (one := resolved_id(wanted, cast)) is not None)
    return [one.name for one in found if " " in one.name.strip() and one.name.casefold() in said]


def scene_history(runs: Sequence[SceneRun]) -> str:
    return "\n\n".join(
        "\n".join(
            (
                f"SCENE {number}: {run.scene.title} ({run.scene.place})",
                f"the question: {run.scene.question}",
                run.scene.situation,
                "what happened: " + (told_tail(run) or "(nothing yet)"),
            )
        )
        for number, run in enumerate(runs, start=1)
    )


def told_tail(run: SceneRun) -> str:
    return "\n".join(f"> {one.prompt}\n{one.narration}" for one in run.exchanges[-TAIL_EXCHANGES:])


def check_hub(hub: Slug | None, board: Sequence[Offer], runs: Sequence[SceneRun]) -> None:
    check_board(hub, board)
    if hub is None:
        for index, run in enumerate(runs):
            if run.scene.debrief is not None:
                raise ValueError(f"run {index} has a debrief with no hub")
        return
    first = runs[0].scene
    if first.place != hub or first.debrief is not None:
        raise ValueError(f"run 0 does not open at hub {hub!r} with no debrief")
    for index in range(1, len(runs)):
        scene = runs[index].scene
        at_hub = scene.place == hub
        if at_hub and scene.debrief is None:
            raise ValueError(f"run {index} is at the hub with no debrief")
        if not at_hub and scene.debrief is not None:
            raise ValueError(f"run {index} is away from the hub with a debrief")
        if at_hub and runs[index - 1].scene.place == hub:
            raise ValueError(f"run {index} is a hub run right after a hub run")


def stops_of(runs: Sequence[SceneRun]) -> tuple[Stop, ...]:
    return tuple(
        Stop(place=run.scene.place, title=run.scene.title, debrief=run.scene.debrief)
        for run in runs
    )
