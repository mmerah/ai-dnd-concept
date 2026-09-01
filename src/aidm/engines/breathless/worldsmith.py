import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, Field

from aidm.core.entities import EngineId, EntityId, Frozen, Slug
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import AnyScenario, ScenarioMeta, WorldsmithAnswer
from aidm.core.tools import schema_of
from aidm.core.views import sections
from aidm.engines.breathless.creation import Pack, guidance
from aidm.engines.breathless.views import entity_line
from aidm.engines.breathless.world import (
    BreathlessGame,
    BreathlessScenario,
    BreathlessScenarioFile,
    BreathlessWorld,
    Npc,
    Scene,
    SceneCanon,
    SceneRun,
    Survivor,
)
from aidm.engines.core import PLAYER_ID, Entity

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


def arrival_brief(pursuit: str) -> str:
    return CROSSING.format(pursuit=pursuit)


def scene_refusal(draft: SceneDraft, world: BreathlessWorld | None = None) -> str | None:
    missing = _scene_unmet(draft, world)
    return None if not missing else "the scene needs " + "; ".join(missing)


def opening_canon(draft: SceneDraft, source: str) -> SceneCanon:
    cast = draft.cast
    present = _resolve(draft.present, cast, "present")
    for one in present:
        cast[one].known = True
    return SceneCanon(
        cast=cast,
        opening=_scene(draft),
        present=present,
        hidden=_resolve(draft.hidden, cast, "hidden"),
        source=source,
    )


def resolved_id(wanted: str, cast: Mapping[EntityId, Entity]) -> EntityId | None:
    """Ids are the worldsmith's failure mode: an unknown one matches a cast name before refusal."""
    if wanted in cast:
        return EntityId(wanted)
    matches = [one.id for one in cast.values() if one.name.casefold() == wanted.casefold()]
    return EntityId(matches[0]) if len(matches) == 1 else None


def apply_scene(world: BreathlessWorld, draft: SceneDraft) -> None:
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
    present = [one for one in _resolve(draft.present, known, "present") if one != PLAYER_ID]
    hidden = [one for one in _resolve(draft.hidden, known, "hidden") if one != PLAYER_ID]
    if overlap := sorted(set(present) & set(hidden)):
        raise ValueError(f"the scene lists {overlap} as both present and hidden")
    if met := sorted(one for one in hidden if cast[one].known):
        raise ValueError(f"the scene hides {met}, whom the player has already met")
    world.cast = cast
    for one in present:
        cast[one].known = True
    world.runs.append(SceneRun(scene=_scene(draft), present=present, hidden=hidden))


async def write_next(
    packs: Mapping[str, Pack], state: BreathlessGame, intent: str, answer: WorldsmithAnswer
) -> BaseModel:
    world = state.payload.world

    def refusal(written: BaseModel) -> str | None:
        if not isinstance(written, SceneDraft):
            raise ValueError("Breathless received an incompatible scene")
        return scene_refusal(written, world)

    prompt = render_worldsmith(world, intent, guidance(packs, state.packs))
    return await answer(prompt, SceneDraft, refusal)


def install_scene(state: BreathlessGame, written: BaseModel) -> tuple[Fact, ...]:
    if not isinstance(written, SceneDraft):
        raise ValueError("Breathless received an incompatible scene")
    apply_scene(state.payload.world, written.model_copy(deep=True))
    trace = f"the story moves to {written.title}"
    return (Fact(kind="scene_opened", trace=trace, told=True, card=f"New scene: {written.title}"),)


def render_worldsmith(world: BreathlessWorld, intent: str, guidance: str) -> str:
    cast = "\n".join(
        (
            entity_line(world.player, detail=_where(world, world.player)),
            *(entity_line(one, detail=_where(world, one)) for one in world.cast.values()),
        )
    )
    return _worldsmith(
        source=world.source,
        history=_history(world),
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
        raise ValueError("Breathless received an incompatible scene")
    if (refused := scene_refusal(written)) is not None:
        raise ValueError(refused)
    return BreathlessScenarioFile(
        meta=ScenarioMeta(title=title, premise=premise or written.situation),
        engine=EngineId("breathless"),
        packs=packs,
        art_style=art_style,
        payload=BreathlessScenario(world=opening_canon(written, source)),
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


def _where(world: BreathlessWorld, one: Survivor | Npc) -> str:
    seen = world.last_seen(one.id)
    return f"last seen in: {seen}" if seen else ""


def _history(world: BreathlessWorld) -> str:
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


def _scene(draft: SceneDraft) -> Scene:
    return Scene(
        place=draft.place,
        title=draft.title,
        question=draft.question,
        situation=draft.situation,
        secret=draft.secret,
    )


def _scene_unmet(draft: SceneDraft, world: BreathlessWorld | None = None) -> list[str]:
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
    if told := sorted(_named_in(draft.situation, draft.hidden, known)):
        unmet.append(f"a situation that does not name what is hidden: {told}")
    if broken := sorted(eid for eid, one in draft.cast.items() if not one.alive):
        unmet.append(f"cast members as the worldsmith may write them: alive: {broken}")
    return unmet


def _named_in(situation: str, hidden: Iterable[str], cast: Mapping[EntityId, Entity]) -> list[str]:
    """Multi-word names only: a prop called `Bell` shares its word with any bell tower."""
    said = situation.casefold()
    found = (cast[one] for wanted in hidden if (one := resolved_id(wanted, cast)) is not None)
    return [one.name for one in found if " " in one.name.strip() and one.name.casefold() in said]


def _resolve(wanted: Iterable[str], cast: Mapping[EntityId, Entity], where: str) -> list[EntityId]:
    found: list[EntityId] = []
    for one in wanted:
        matched = resolved_id(one, cast)
        if matched is None:
            raise ValueError(f"the scene lists {one!r} as {where}, and no such id or name exists")
        if matched not in found:
            found.append(matched)
    return found
