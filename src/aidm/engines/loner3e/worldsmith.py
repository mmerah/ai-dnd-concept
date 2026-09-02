import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, Field

from aidm.core.entities import EngineId, EntityId, Frozen, Slug
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import AnyScenario, ScenarioKind, ScenarioMeta, WorldsmithAnswer
from aidm.core.tools import schema_of
from aidm.core.views import Rows, sections
from aidm.engines.hub import (
    BOARD_MAX,
    BOARD_MIN,
    GO_HOME,
    HUB_QUESTION,
    JOB_ASK,
    Debrief,
    Offer,
    hub_sections,
    job_closed,
)
from aidm.engines.loner3e.creation import Pack, guidance
from aidm.engines.loner3e.tools import close_conflicts
from aidm.engines.loner3e.views import entity_line
from aidm.engines.loner3e.world import (
    LUCK_MAX,
    Loner3eGame,
    Loner3eScenario,
    Loner3eScenarioFile,
    LonerCharacter,
    LonerWorld,
    SceneCanon,
)
from aidm.engines.scenes import (
    SURPRISE,
    Scene,
    SceneRun,
    named_in,
    resolve_ids,
    resolved_id,
    scene_history,
)

MIN_SITUATION = 80
MIN_JOB = 80
WORLDSMITH = (Path(__file__).parent / "worldsmith.md").read_text(encoding=ENCODING)
# Read by the next turn, which is usually the next offer click: the note must stand on its own.
GROWTH_NOTE = (
    "The job {title} is closed and was completed. The adventure's end applies: ask what the "
    "character learned if the player has not said, then write it once with `change_tags` and "
    "`drive`."
)
ONE_SHOT_OPENING = (
    "Write the opening scene of this adventure: where the player starts, who is there, "
    "and what is waiting to be found."
)
CAMPAIGN_OPENING = (
    "Write the opening of this campaign: the hub the player keeps coming back to — one place, a "
    "guild hall or a ship, whoever keeps it and the regulars — and a board of two or three "
    "`offers`. Nothing has happened yet. " + HUB_QUESTION
)


class SceneDraft(Frozen):
    """What the worldsmith returns. Ids arrive as free text so a wrong one can be matched against
    a cast name before it is refused; code owns the scene id and never asks for the player."""

    place: Slug
    title: str
    question: str = Field(min_length=10)
    situation: str = Field(min_length=MIN_SITUATION)
    present: tuple[str, ...] = ()
    hidden: tuple[str, ...] = ()
    secret: str = ""
    job: str = ""  # the job as taken; on the scene that leaves the hub only
    cast: dict[EntityId, LonerCharacter] = Field(default_factory=dict)
    offers: tuple[Offer, ...] = ()  # the board; only a hub scene fills it


class HubDraft(SceneDraft):
    debrief: Debrief


def scene_refusal(
    draft: SceneDraft, world: LonerWorld | None = None, *, hub: bool = False
) -> str | None:
    missing = _scene_unmet(draft, world, hub=hub)
    return None if not missing else "the scene needs " + "; ".join(missing)


def opening_canon(draft: SceneDraft, source: str, kind: ScenarioKind) -> SceneCanon:
    cast = draft.cast
    present = resolve_ids(draft.present, cast, "present")
    for one in present:
        cast[one].known = True
    hub, board = (draft.place, draft.offers) if kind == "campaign" else (None, ())
    return SceneCanon(
        cast=cast,
        opening=_scene(draft),
        present=present,
        hidden=resolve_ids(draft.hidden, cast, "hidden"),
        source=source,
        hub=hub,
        board=board,
    )


def apply_scene(world: LonerWorld, draft: SceneDraft) -> None:
    """Every refusal lands before the first write: a rejected scene leaves the world alone."""
    for one, held in draft.cast.items():
        if one in world.cast:
            raise ValueError(f"the scene rewrites {one!r}, who is already in the cast")
        if one != held.id:
            raise ValueError(f"entity {held.id!r} is filed under {one!r}")
    cast: dict[EntityId, LonerCharacter] = {**world.cast, **draft.cast}
    # The player and their companions are in every scene; naming them is not how they get there.
    followers = [world.player_id, *world.companions]
    present = [one for one in resolve_ids(draft.present, cast, "present") if one not in followers]
    hidden = [one for one in resolve_ids(draft.hidden, cast, "hidden") if one not in followers]
    if overlap := sorted(set(present) & set(hidden)):
        raise ValueError(f"the scene lists {overlap} as both present and hidden")
    if met := sorted(one for one in hidden if cast[one].known):
        raise ValueError(f"the scene hides {met}, whom the player has already met")
    kept = [one for one in followers if one not in present and one not in hidden]
    world.cast = cast
    for one in present:
        cast[one].known = True
    world.runs.append(SceneRun(scene=_scene(draft), present=[*kept, *present], hidden=hidden))


async def write_next(
    packs: Mapping[str, Pack], state: Loner3eGame, intent: str, answer: WorldsmithAnswer
) -> BaseModel:
    world = state.payload.world
    returning = world.hub is not None and not world.at_hub and intent == GO_HOME
    model: type[SceneDraft] = HubDraft if returning else SceneDraft

    def refusal(written: BaseModel) -> str | None:
        if not isinstance(written, model):
            raise ValueError("Loner 3E received an incompatible scene")
        return scene_refusal(written, world, hub=returning)

    prompt = render_worldsmith(world, intent, guidance(packs, state.packs), returning=returning)
    return await answer(prompt, model, refusal)


def install_scene(state: Loner3eGame, written: BaseModel) -> tuple[Fact, ...]:
    if not isinstance(written, SceneDraft):
        raise ValueError("Loner 3E received an incompatible scene")
    # Read before the move: someone left behind is still in the scene that is closing.
    closed = close_conflicts(state)
    world = state.payload.world
    apply_scene(world, written.model_copy(deep=True))
    came = [world.require(one).name for one in world.companions]
    trace = f"the story moves to {written.title}"
    if came:
        trace += f", and {', '.join(came)} travels there with the player"
    label = "Home" if isinstance(written, HubDraft) else "New scene"
    opened = Fact(kind="scene_opened", trace=trace, told=True, card=f"{label}: {written.title}")
    if isinstance(written, HubDraft):
        world.board = written.offers
        job = world.jobs()[-1]
        if job.debrief.finished:
            state.notes = (*state.notes, GROWTH_NOTE.format(title=job.title))
        return (*closed, job_closed(job), opened)
    return (*closed, opened)


def render_worldsmith(
    world: LonerWorld, intent: str, guidance: str, *, returning: bool = False
) -> str:
    cast = "\n".join(
        entity_line(world, one, detail=_where(world, one)) for one in world.cast.values()
    )
    hub: Rows = ()
    if world.hub is not None:
        hub = hub_sections(
            world.runs[0].scene.title,
            world.hub,
            world.board,
            world.jobs(),
            moment="returning" if returning else "taking" if world.at_hub else "away",
        )
    return _worldsmith(
        source=world.source,
        history=scene_history(world.job_runs()),
        cast=cast,
        guidance=guidance,
        intent=intent,
        answer=HubDraft if returning else SceneDraft,
        hub=hub,
    )


def render_opening(
    packs: Mapping[str, Pack], source: str, picks: Sequence[Slug], kind: ScenarioKind
) -> str:
    return _worldsmith(
        source=source,
        history="(no scenes yet — write the opening)",
        cast="(no cast yet — write the people and things this scene needs)",
        guidance=guidance(packs, picks),
        intent=CAMPAIGN_OPENING if kind == "campaign" else ONE_SHOT_OPENING,
        answer=SceneDraft,
    )


def build_scenario(
    title: str,
    premise: str,
    art_style: str,
    packs: tuple[Slug, ...],
    written: BaseModel,
    source: str,
    kind: ScenarioKind,
) -> AnyScenario:
    if not isinstance(written, SceneDraft):
        raise ValueError("Loner 3E received an incompatible scene")
    if (refused := scene_refusal(written, hub=(kind == "campaign"))) is not None:
        raise ValueError(refused)
    return Loner3eScenarioFile(
        meta=ScenarioMeta(title=title, premise=premise or written.situation, kind=kind),
        engine=EngineId("loner3e"),
        packs=packs,
        art_style=art_style,
        payload=Loner3eScenario(world=opening_canon(written, source, kind)),
    )


def _worldsmith(
    *,
    source: str,
    history: str,
    cast: str,
    guidance: str,
    intent: str,
    answer: type[BaseModel],
    hub: Rows = (),
) -> str:
    return sections(
        (
            ("YOUR ROLE", WORLDSMITH),
            ("SOURCE MATERIAL", source or "(none — write from the cast)"),
            ("SCENES SO FAR", history),
            *hub,
            ("THE WHOLE CAST", cast),
            ("ENGINE GUIDANCE", guidance),
            ("WHAT COMES NEXT", intent),
            ("STANDING INSTRUCTION", SURPRISE),
            ("ANSWER WITH", json.dumps(schema_of(answer), indent=2, ensure_ascii=False)),
        )
    )


def _where(world: LonerWorld, one: LonerCharacter) -> str:
    seen = world.last_seen(one.id)
    return f"last seen in: {seen}" if seen else ""


def _scene(draft: SceneDraft) -> Scene:
    return Scene(
        place=draft.place,
        title=draft.title,
        question=draft.question,
        situation=draft.situation,
        secret=draft.secret,
        job=draft.job,
        debrief=draft.debrief if isinstance(draft, HubDraft) else None,
    )


def _scene_unmet(
    draft: SceneDraft, world: LonerWorld | None = None, *, hub: bool = False
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
    unmet: list[str] = []
    if not others:
        unmet.append("at least one cast member besides the player")
    if world is not None and not any(resolved_id(one, held) is not None for one in others):
        unmet.append("at least one existing cast member brought back")
    if stray := sorted(one for one in others if resolved_id(one, known) is None):
        unmet.append(f"ids that exist; these name nobody: {stray}")
    # `situation` is read to the player, so naming a hidden entity there hands them the find.
    if told := sorted(named_in(draft.situation, draft.hidden, known)):
        unmet.append(f"a situation that does not name what is hidden: {told}")
    if broken := sorted(
        eid for eid, one in draft.cast.items() if not one.alive or one.luck.current != LUCK_MAX
    ):
        unmet.append(f"cast members as the worldsmith may write them: alive, full luck: {broken}")
    taking = world is not None and world.at_hub
    if taking and len(draft.job) < MIN_JOB:
        unmet.append(f"a `job` of a short paragraph: {JOB_ASK}")
    if not taking and draft.job:
        unmet.append("no `job`: only the scene that leaves the hub carries it")
    if hub:
        if world is not None and draft.place != world.hub:
            unmet.append(f"the hub's place {world.hub!r}: this scene is home")
        if not BOARD_MIN <= len(draft.offers) <= BOARD_MAX:
            unmet.append(f"a board of {BOARD_MIN} to {BOARD_MAX} offers")
    else:
        if draft.offers:
            unmet.append("no offers: only the hub has a board")
        if world is not None and world.hub is not None and draft.place == world.hub:
            unmet.append("a place away from the hub: home is reached by going home")
    return unmet
