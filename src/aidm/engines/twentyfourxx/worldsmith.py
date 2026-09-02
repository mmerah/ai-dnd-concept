from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, Field

from aidm.core.entities import EngineId, EntityId, Frozen, Slug
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import AnyScenario, ScenarioKind, ScenarioMeta, WorldsmithAnswer
from aidm.engines.core import PLAYER_ID, Entity
from aidm.engines.hub import (
    BOARD_MAX,
    BOARD_MIN,
    CAMPAIGN_OPENING,
    GO_HOME,
    MIN_JOB,
    ONE_SHOT_OPENING,
    Debrief,
    Offer,
    job_closed,
)
from aidm.engines.scenes import (
    MIN_SITUATION,
    Scene,
    SceneRun,
    cast_unmet,
    hub_rows,
    hub_unmet,
    resolve_ids,
    resolved_id,
    scene_history,
    worldsmith_prompt,
)
from aidm.engines.twentyfourxx.creation import Pack, guidance
from aidm.engines.twentyfourxx.views import entity_line
from aidm.engines.twentyfourxx.world import (
    Npc,
    SceneCanon,
    TwentyfourxxGame,
    TwentyfourxxScenario,
    TwentyfourxxScenarioFile,
    TwentyfourxxWorld,
)

HUB_PHRASE = "the fixer and the regulars"  # what `CAMPAIGN_OPENING` asks this engine's hub to be
WORLDSMITH = (Path(__file__).parent / "worldsmith.md").read_text(encoding=ENCODING)
BOARD_GUIDANCE = (
    "The SRD's job-finding setup is the board's range, not a recipe: 1–2 nothing, owe somebody to "
    "get in on a job; 3–4 found a job, but something seems off; 5–6 a choice between two jobs."
)
# Read by the next turn, which is usually the next offer click: the note must stand on its own.
JOB_DONE_NOTE = (
    "The job {title} is closed and was completed. The SRD's after-a-job step applies: call "
    "`job_done` once, with the skill the player names, else the skill the job called on."
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
    cast: dict[EntityId, Npc] = Field(default_factory=dict)


class JobDraft(SceneDraft):
    """The scene that leaves the hub."""

    job: str = Field(min_length=MIN_JOB)


class HubDraft(SceneDraft):
    """The campaign's opening: the hub and its board."""

    offers: tuple[Offer, ...] = Field(min_length=BOARD_MIN, max_length=BOARD_MAX)


class ReturnDraft(HubDraft):
    """The return home: the debrief is the paragraph; the verdict is the master's."""

    debrief: str = Field(min_length=1)


def opening_draft(kind: ScenarioKind) -> type[SceneDraft]:
    return HubDraft if kind == "campaign" else SceneDraft


def scene_refusal(draft: SceneDraft, world: TwentyfourxxWorld | None = None) -> str | None:
    missing = _scene_unmet(draft, world)
    return None if not missing else "the scene needs " + "; ".join(missing)


def opening_canon(draft: SceneDraft, source: str) -> SceneCanon:
    cast = draft.cast
    present = resolve_ids(draft.present, cast, "present")
    for one in present:
        cast[one].known = True
    hub, board = (draft.place, draft.offers) if isinstance(draft, HubDraft) else (None, ())
    return SceneCanon(
        cast=cast,
        opening=_scene(draft, False),
        present=present,
        hidden=resolve_ids(draft.hidden, cast, "hidden"),
        source=source,
        hub=hub,
        board=board,
    )


def apply_scene(world: TwentyfourxxWorld, draft: SceneDraft) -> None:
    """Every refusal lands before the first write: a rejected scene leaves the world alone."""
    for one, held in draft.cast.items():
        if one == PLAYER_ID:
            raise ValueError("the scene rewrites the player")
        if one in world.cast:
            raise ValueError(f"the scene rewrites {one!r}, who is already in the cast")
        if one != held.id:
            raise ValueError(f"entity {held.id!r} is filed under {one!r}")
    cast: dict[EntityId, Npc] = {**world.cast, **draft.cast}
    known: Mapping[EntityId, Entity] = {PLAYER_ID: world.player, **cast}
    present = [one for one in resolve_ids(draft.present, known, "present") if one != PLAYER_ID]
    hidden = [one for one in resolve_ids(draft.hidden, known, "hidden") if one != PLAYER_ID]
    if overlap := sorted(set(present) & set(hidden)):
        raise ValueError(f"the scene lists {overlap} as both present and hidden")
    if met := sorted(one for one in hidden if cast[one].known):
        raise ValueError(f"the scene hides {met}, whom the player has already met")
    finished = world.job_done  # the master's verdict on the job the return is closing
    world.cast = cast
    for one in present:
        cast[one].known = True
    world.runs.append(SceneRun(scene=_scene(draft, finished), present=present, hidden=hidden))


async def write_next(
    packs: Mapping[str, Pack], state: TwentyfourxxGame, intent: str, answer: WorldsmithAnswer
) -> BaseModel:
    world = state.payload.world
    returning = world.hub is not None and not world.at_hub and intent == GO_HOME
    model: type[SceneDraft] = ReturnDraft if returning else JobDraft if world.at_hub else SceneDraft

    def refusal(written: BaseModel) -> str | None:
        if not isinstance(written, model):
            raise ValueError("24XX received an incompatible scene")
        return scene_refusal(written, world)

    prompt = render_worldsmith(world, intent, guidance(packs, state.packs), model)
    return await answer(prompt, model, refusal)


def install_scene(state: TwentyfourxxGame, written: BaseModel) -> tuple[Fact, ...]:
    if not isinstance(written, SceneDraft):
        raise ValueError("24XX received an incompatible scene")
    world = state.payload.world
    apply_scene(world, written.model_copy(deep=True))
    trace = f"the story moves to {written.title}"
    label = "Home" if isinstance(written, ReturnDraft) else "New scene"
    opened = Fact(kind="scene_opened", trace=trace, told=True, card=f"{label}: {written.title}")
    if isinstance(written, ReturnDraft):
        world.board = written.offers
        job = world.jobs()[-1]
        if job.debrief.finished:
            state.notes = (*state.notes, JOB_DONE_NOTE.format(title=job.title))
        return (job_closed(job), opened)
    return (opened,)


def render_worldsmith(
    world: TwentyfourxxWorld, intent: str, guidance: str, answer: type[SceneDraft]
) -> str:
    returning = issubclass(answer, ReturnDraft)
    cast = "\n".join(
        (
            entity_line(world.player, detail=world.last_seen(world.player.id)),
            *(entity_line(one, detail=world.last_seen(one.id)) for one in world.cast.values()),
        )
    )
    return worldsmith_prompt(
        WORLDSMITH,
        source=world.source,
        history=scene_history(world.job_runs()),
        cast=cast,
        guidance="\n\n".join((guidance, BOARD_GUIDANCE)) if returning else guidance,
        intent=intent,
        answer=answer,
        hub=hub_rows(world, returning=returning),
    )


def render_opening(
    packs: Mapping[str, Pack], source: str, picks: Sequence[Slug], kind: ScenarioKind
) -> str:
    campaign = kind == "campaign"
    scene_guidance = guidance(packs, picks)
    return worldsmith_prompt(
        WORLDSMITH,
        source=source,
        history="(no scenes yet — write the opening)",
        cast="(no cast yet — write the people and things this scene needs)",
        guidance="\n\n".join((scene_guidance, BOARD_GUIDANCE)) if campaign else scene_guidance,
        intent=CAMPAIGN_OPENING.format(hub=HUB_PHRASE) if campaign else ONE_SHOT_OPENING,
        answer=opening_draft(kind),
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
        raise ValueError("24XX received an incompatible scene")
    if (refused := scene_refusal(written)) is not None:
        raise ValueError(refused)
    return TwentyfourxxScenarioFile(
        meta=ScenarioMeta(title=title, premise=premise or written.situation, kind=kind),
        engine=EngineId("twentyfourxx"),
        packs=packs,
        art_style=art_style,
        payload=TwentyfourxxScenario(world=opening_canon(written, source)),
    )


def _scene(draft: SceneDraft, finished: bool) -> Scene:
    return Scene(
        place=draft.place,
        title=draft.title,
        question=draft.question,
        situation=draft.situation,
        secret=draft.secret,
        job=draft.job if isinstance(draft, JobDraft) else "",
        debrief=Debrief(text=draft.debrief, finished=finished)
        if isinstance(draft, ReturnDraft)
        else None,
    )


def _scene_unmet(draft: SceneDraft, world: TwentyfourxxWorld | None = None) -> list[str]:
    """No world means the opening: nobody exists yet, and no id can be the player's."""
    held = {} if world is None else world.cast
    known: Mapping[EntityId, Entity] = (
        dict(draft.cast) if world is None else {PLAYER_ID: world.player, **held, **draft.cast}
    )
    others = [
        one for one in (*draft.present, *draft.hidden) if resolved_id(one, known) != PLAYER_ID
    ]
    unmet = cast_unmet(others, draft.hidden, draft.situation, known, held, opening=world is None)
    if broken := sorted(eid for eid, one in draft.cast.items() if not one.alive):
        unmet.append(f"cast members as the worldsmith may write them: alive: {broken}")
    unmet.extend(
        hub_unmet(
            draft.place,
            None if world is None else world.hub,
            debrief=draft.debrief if isinstance(draft, ReturnDraft) else None,
            held=held,
            known=known,
        )
    )
    return unmet
