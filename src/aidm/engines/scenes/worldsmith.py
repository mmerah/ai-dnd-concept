from typing import Any

from aidm.core.entities import EngineId, Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.model import (
    AnyScenario,
    Game,
    Scenario,
    ScenarioKind,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.engines.base import Person
from aidm.engines.hub import CAMPAIGN_OPENING, GO_HOME, ONE_SHOT_OPENING, job_closed
from aidm.engines.scenes.drafts import HubDraft, JobDraft, NextDraft, ReturnDraft, SceneDraft
from aidm.engines.scenes.world import (
    SceneCanon,
    SceneWorld,
    resolve_ids,
    run_of,
    scene_refusal,
    worldsmith_prompt,
)

CROSSING = (
    "The player is leaving WHAT THE PLAYER HAS READ for the place in SCENE. They asked for this: "
    '"{pursuit}"\n\n'
    "Write the crossing: a sentence of leaving, then the arrival. Cover the distance and the time "
    "in the fewest words that make it real, and end on what they see first. WHAT HAPPENED names "
    "anyone who travelled with them. They have not acted in the new place yet, so settle nothing."
)


def opening_draft[C: Person](cast_type: type[C], kind: ScenarioKind) -> type[SceneDraft[C]]:
    """Pydantic parametrizes the subscript at runtime, so the cast type reaches the schema."""
    return HubDraft[cast_type] if kind == "campaign" else SceneDraft[cast_type]


def opening_canon[C: Person](
    draft: SceneDraft[C], source: str, cast_type: type[C]
) -> SceneCanon[C]:
    """Parametrized at runtime, so the cast revalidates as the engine's own people."""
    cast = draft.cast
    present = resolve_ids(draft.present, cast, "present")
    hidden = resolve_ids(draft.hidden, cast, "hidden")
    for one in present:
        cast[one].known = True
    hub, board = (draft.place, draft.offers) if isinstance(draft, HubDraft) else (None, ())
    return SceneCanon[cast_type](
        cast=cast,
        opening=run_of(draft, [*present, *hidden]),
        source=source,
        hub=hub,
        board=board,
    )


async def write_next[C: Person, P: Person](
    world: SceneWorld[C, P],
    intent: str,
    answer: WorldsmithAnswer,
    *,
    cast_type: type[C],
    guidance: str,
) -> SceneDraft[C]:
    returning = world.hub is not None and not world.at_hub and intent == GO_HOME
    model: type[SceneDraft[C]] = (
        ReturnDraft[cast_type]
        if returning
        else JobDraft[cast_type]
        if world.at_hub
        else NextDraft[cast_type]
    )

    prompt = world.render_worldsmith(intent, guidance, model)
    return await answer(prompt, model, lambda written: scene_refusal(written, world))


def install_scene[C: Person, W: SceneWorld[Any, Any]](
    state: Game[W], written: SceneDraft[C], *, finished_note: str
) -> list[Fact]:
    world = state.payload
    world.apply_scene(written.model_copy(deep=True))
    trace = f"the story moves to {written.title}"
    if came := [one.name for one in world.members()]:
        trace += f", the player travelling with {', '.join(came)}"
    label = "Home" if isinstance(written, ReturnDraft) else "New scene"
    card = "\n".join(
        (
            f"{label}: {written.title}",
            f"At stake: {written.question}",
            *([f"The job: {written.job}"] if isinstance(written, JobDraft) else []),
        )
    )
    opened = Fact(kind="scene_opened", trace=trace, told=True, card=card)
    if isinstance(written, ReturnDraft):
        world.board = written.offers
        job = world.jobs[-1]
        if job.finished and finished_note:
            state.notes = (*state.notes, finished_note.format(title=job.title))
        return [job_closed(job), opened]
    return [opened]


def render_opening[C: Person](
    cast_type: type[C], source: str, guidance: str, kind: ScenarioKind, hub_phrase: str
) -> str:
    return worldsmith_prompt(
        source=source,
        history="(no scenes yet — write the opening)",
        cast="(no cast yet — write the people and things this scene needs)",
        guidance=guidance,
        intent=CAMPAIGN_OPENING.format(hub=hub_phrase) if kind == "campaign" else ONE_SHOT_OPENING,
        answer=opening_draft(cast_type, kind),
    )


def build_scenario[C: Person](
    file_type: type[Scenario[SceneCanon[C]]],
    engine_id: EngineId,
    title: str,
    premise: str,
    packs: tuple[Slug, ...],
    written: SceneDraft[C],
    source: str,
    kind: ScenarioKind,
    cast_type: type[C],
) -> AnyScenario:
    if (refused := scene_refusal(written)) is not None:
        raise Refusal(refused)
    return file_type(
        meta=ScenarioMeta(title=title, premise=premise or written.situation, kind=kind),
        engine=engine_id,
        packs=packs,
        payload=opening_canon(written, source, cast_type),
    )
