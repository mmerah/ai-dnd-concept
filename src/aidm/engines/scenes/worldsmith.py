from collections.abc import Iterable, Mapping, Sequence

from pydantic import BaseModel

from aidm.core.entities import EntityId
from aidm.core.play import Commission
from aidm.core.tools import schema_text
from aidm.core.views import Sections, sections
from aidm.engines.base import Person, Thing
from aidm.engines.hub import named_unmet, place_unmet
from aidm.engines.scenes.drafts import CastDraft, HubDraft, ReturnDraft, SceneDraft
from aidm.engines.scenes.world import SceneWorld, resolved_id

CROSSING = (
    "The player is leaving {left} for the place in SCENE. They asked for this: "
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
COMMISSION_ASK = (
    "The game master asked for a {kind}: {brief}. Write that one entry under its own id, or "
    "rewrite one known entry's brief, and nothing else."
)


def scene_refusal[C: Person, P: Person](
    draft: SceneDraft[C],
    world: SceneWorld[C, P] | None = None,
    asked: Sequence[Commission] = (),
) -> str | None:
    """Free: the drafts may not import the world, and the authoring call has no world."""
    unmet = scene_unmet(draft, world, asked)
    return None if not unmet else "the scene needs " + "; ".join(unmet)


def cast_refusal[C: Person, P: Person](draft: CastDraft[C], world: SceneWorld[C, P]) -> str | None:
    """Free: the drafts may not import the world; one bar module beside `scene_refusal`."""
    entity_id, entry = next(iter(draft.cast.items()))
    unmet: list[str] = []
    if entity_id == world.player.id:
        unmet.append("an entry that is not the player")
    if entry.id != entity_id:
        unmet.append(f"{entry.id!r} filed under its own id, not {entity_id!r}")
    if entity_id not in world.cast:
        if entry.known:
            unmet.append("a new entry unmet")
        if why := entry.unwritten():
            unmet.append(why)
    return None if not unmet else "the scene needs " + "; ".join(unmet)


def scene_unmet[C: Person, P: Person](
    draft: SceneDraft[C], world: SceneWorld[C, P] | None, asked: Sequence[Commission]
) -> list[str]:
    """The one bar: every refusal the install makes, so the worldsmith's one retry sees them all."""
    filed: Mapping[EntityId, C] = {} if world is None else world.cast
    everyone: Mapping[EntityId, Thing] = (
        dict(draft.cast)
        if world is None
        else {world.player.id: world.player, **world.merged_cast(draft.cast)}
    )
    followers = () if world is None else (world.player.id, *world.party)
    others = (*draft.present, *draft.hidden)
    unmet: list[str] = []
    if world is None and not isinstance(draft, HubDraft) and not draft.arc:
        unmet.append("an `arc`: a few lines on what lies beyond this scene")
    if named := sorted(name for name in others if resolved_id(name, everyone) in followers):
        unmet.append(
            "a scene that does not list the player or the party; "
            f"they are put there by code: {named}"
        )
    if world is not None and world.player.id in draft.cast:
        unmet.append("a cast that never rewrites the player")
    if misfiled := [
        f"{entry.id!r} is filed under {key!r}"
        for key, entry in draft.cast.items()
        if key != entry.id
    ]:
        unmet.append("cast entries under their own id: " + "; ".join(misfiled))
    # Nothing can be brought back once everyone left behind travels with the player.
    needs_return = world is not None and bool(set(world.cast) - set(world.party))
    unmet.extend(_cast_unmet(draft, everyone, filed, needs_return=needs_return))
    present = [
        entity_id
        for name in draft.present
        if (entity_id := resolved_id(name, everyone)) is not None
    ]
    hidden = [
        entity_id for name in draft.hidden if (entity_id := resolved_id(name, everyone)) is not None
    ]
    if overlap := sorted(set(present) & set(hidden)):
        unmet.append(f"nobody listed as both present and hidden: {overlap}")
    if met := sorted(
        entity_id for entity_id in set(hidden) - set(followers) if everyone[entity_id].known
    ):
        unmet.append(f"a hidden list without {met}, whom the player has already met")
    if broken := [
        f"{eid}: {why}"
        for eid, entry in draft.cast.items()
        if eid not in filed and (why := entry.unwritten())
    ]:
        unmet.append(f"cast members as the worldsmith may write them: {broken}")
    unmet.extend(_hub_unmet(draft, world, everyone))
    if asked:
        written = len([eid for eid in draft.cast if eid not in filed])
        if written < len(asked):
            unmet.append(
                f"{len(asked)} asked for, {written} written: one new cast entry per commission"
            )
    return unmet


def named_in(situation: str, hidden: Iterable[str], cast: Mapping[EntityId, Thing]) -> list[str]:
    """The hidden list arrives as free text, so each entry is resolved before the leak rule runs."""
    return named_unmet(
        situation,
        (
            cast[entity_id]
            for wanted in hidden
            if (entity_id := resolved_id(wanted, cast)) is not None
        ),
    )


def worldsmith_prompt(
    role: str,
    *,
    source: str,
    history: str,
    cast: str,
    guidance: str,
    intent: str,
    answer: type[BaseModel],
    hub: Sections = (),
    asked: str = "",
) -> str:
    return sections(
        (
            ("YOUR ROLE", role),
            ("SOURCE MATERIAL", source or "(none — write from the cast)"),
            ("SCENES SO FAR", history),
            *hub,
            ("THE WHOLE CAST", cast),
            ("ENGINE GUIDANCE", guidance),
            *((("THE GAME MASTER ASKED FOR", asked),) if asked else ()),
            ("WHAT COMES NEXT", intent),
            ("STANDING INSTRUCTION", SURPRISE),
            ("ANSWER WITH", schema_text(answer)),
        )
    )


def _cast_unmet[C: Person](
    draft: SceneDraft[C],
    everyone: Mapping[EntityId, Thing],
    filed: Mapping[EntityId, Thing],
    *,
    needs_return: bool,
) -> list[str]:
    """The cast a scene owes, whatever the engine's own people are made of."""
    others = (*draft.present, *draft.hidden)
    unmet: list[str] = []
    if not others:
        unmet.append("at least one cast member besides the player")
    if needs_return and not any(resolved_id(name, filed) is not None for name in others):
        unmet.append("at least one existing cast member brought back")
    if stray := sorted(name for name in others if resolved_id(name, everyone) is None):
        unmet.append(f"ids that exist; these name nobody: {stray}")
    # `situation` is read to the player, so naming a hidden entity there hands them the find.
    if named := sorted(named_in(draft.situation, draft.hidden, everyone)):
        unmet.append(f"a situation that does not name what is hidden: {named}")
    return unmet


def _hub_unmet[C: Person, P: Person](
    draft: SceneDraft[C], world: SceneWorld[C, P] | None, everyone: Mapping[EntityId, Thing]
) -> list[str]:
    """A return is read by the player: no field names what they have not met. `situation` against
    the draft's own `hidden` is `_cast_unmet`'s. Untold fact traces are not checked: prose cannot
    be matched to a trace, so that half of the caution's second guard is the two-spawn fallback."""
    hub = None if world is None or world.campaign is None else world.campaign.place
    unmet: list[str] = []
    if (
        misplaced := place_unmet(draft.place, hub, returning=isinstance(draft, ReturnDraft))
    ) is not None:
        unmet.append(misplaced)
    if isinstance(draft, ReturnDraft) and world is not None:
        unmet_world = {eid: entry for eid, entry in world.cast.items() if not entry.known}
        unmet_hidden = {
            entity_id: everyone[entity_id]
            for name in draft.hidden
            if (entity_id := resolved_id(name, everyone)) is not None
        }
        for field, text, candidates in (
            ("debrief", draft.debrief, {**unmet_world, **unmet_hidden}.values()),
            ("situation", draft.situation, unmet_world.values()),
            ("question", draft.question, {**unmet_world, **unmet_hidden}.values()),
        ):
            if named := sorted(named_unmet(text, candidates)):
                unmet.append(f"a {field} that does not name what the player has not met: {named}")
    return unmet
