import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, Field

from aidm.core.entities import EngineId, EntityId, Frozen, Slug
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import AnyScenario, ScenarioMeta, WorldsmithAnswer
from aidm.core.tools import schema_of
from aidm.core.views import sections
from aidm.engines.core import PLAYER_ID, Entity
from aidm.engines.scenes import (
    SURPRISE,
    Scene,
    SceneRun,
    named_in,
    resolve_ids,
    resolved_id,
    scene_history,
)
from aidm.engines.twentyfourxx.creation import Pack, guidance
from aidm.engines.twentyfourxx.views import entity_line
from aidm.engines.twentyfourxx.world import (
    Npc,
    Operator,
    SceneCanon,
    TwentyfourxxGame,
    TwentyfourxxScenario,
    TwentyfourxxScenarioFile,
    TwentyfourxxWorld,
)

MIN_SITUATION = 80
WORLDSMITH = (Path(__file__).parent / "worldsmith.md").read_text(encoding=ENCODING)


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


def scene_refusal(draft: SceneDraft, world: TwentyfourxxWorld | None = None) -> str | None:
    missing = _scene_unmet(draft, world)
    return None if not missing else "the scene needs " + "; ".join(missing)


def opening_canon(draft: SceneDraft, source: str) -> SceneCanon:
    cast = draft.cast
    present = resolve_ids(draft.present, cast, "present")
    for one in present:
        cast[one].known = True
    return SceneCanon(
        cast=cast,
        opening=_scene(draft),
        present=present,
        hidden=resolve_ids(draft.hidden, cast, "hidden"),
        source=source,
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
    world.cast = cast
    for one in present:
        cast[one].known = True
    world.runs.append(SceneRun(scene=_scene(draft), present=present, hidden=hidden))


async def write_next(
    packs: Mapping[str, Pack], state: TwentyfourxxGame, intent: str, answer: WorldsmithAnswer
) -> BaseModel:
    world = state.payload.world

    def refusal(written: BaseModel) -> str | None:
        if not isinstance(written, SceneDraft):
            raise ValueError("24XX received an incompatible scene")
        return scene_refusal(written, world)

    prompt = render_worldsmith(world, intent, guidance(packs, state.packs))
    return await answer(prompt, SceneDraft, refusal)


def install_scene(state: TwentyfourxxGame, written: BaseModel) -> tuple[Fact, ...]:
    if not isinstance(written, SceneDraft):
        raise ValueError("24XX received an incompatible scene")
    apply_scene(state.payload.world, written.model_copy(deep=True))
    trace = f"the story moves to {written.title}"
    return (Fact(kind="scene_opened", trace=trace, told=True, card=f"New scene: {written.title}"),)


def render_worldsmith(world: TwentyfourxxWorld, intent: str, guidance: str) -> str:
    cast = "\n".join(
        (
            entity_line(world.player, detail=_where(world, world.player)),
            *(entity_line(one, detail=_where(world, one)) for one in world.cast.values()),
        )
    )
    return _worldsmith(
        source=world.source,
        history=scene_history(world.runs),
        cast=cast,
        guidance=guidance,
        intent=intent,
        answer=SceneDraft,
    )


def render_opening(packs: Mapping[str, Pack], source: str, picks: Sequence[Slug]) -> str:
    return _worldsmith(
        source=source,
        history="(no scenes yet — write the opening)",
        cast="(no cast yet — write the people and things this scene needs)",
        guidance=guidance(packs, picks),
        intent=(
            "Write the opening scene of this adventure: where the player starts, who is there, "
            "and what is waiting to be found."
        ),
        answer=SceneDraft,
    )


def build_scenario(
    title: str,
    premise: str,
    art_style: str,
    packs: tuple[Slug, ...],
    written: BaseModel,
    source: str,
) -> AnyScenario:
    if not isinstance(written, SceneDraft):
        raise ValueError("24XX received an incompatible scene")
    if (refused := scene_refusal(written)) is not None:
        raise ValueError(refused)
    return TwentyfourxxScenarioFile(
        meta=ScenarioMeta(title=title, premise=premise or written.situation),
        engine=EngineId("twentyfourxx"),
        packs=packs,
        art_style=art_style,
        payload=TwentyfourxxScenario(world=opening_canon(written, source)),
    )


def _worldsmith(
    *,
    source: str,
    history: str,
    cast: str,
    guidance: str,
    intent: str,
    answer: type[BaseModel],
) -> str:
    return sections(
        (
            ("YOUR ROLE", WORLDSMITH),
            ("SOURCE MATERIAL", source or "(none — write from the cast)"),
            ("SCENES SO FAR", history),
            ("THE WHOLE CAST", cast),
            ("ENGINE GUIDANCE", guidance),
            ("WHAT COMES NEXT", intent),
            ("STANDING INSTRUCTION", SURPRISE),
            ("ANSWER WITH", json.dumps(schema_of(answer), indent=2, ensure_ascii=False)),
        )
    )


def _where(world: TwentyfourxxWorld, one: Operator | Npc) -> str:
    seen = world.last_seen(one.id)
    return f"last seen in: {seen}" if seen else ""


def _scene(draft: SceneDraft) -> Scene:
    return Scene(
        place=draft.place,
        title=draft.title,
        question=draft.question,
        situation=draft.situation,
        secret=draft.secret,
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
    if broken := sorted(eid for eid, one in draft.cast.items() if not one.alive):
        unmet.append(f"cast members as the worldsmith may write them: alive: {broken}")
    return unmet
