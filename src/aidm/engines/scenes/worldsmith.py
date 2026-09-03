from collections.abc import Iterable, Mapping

from pydantic import BaseModel

from aidm.core.entities import EntityId
from aidm.core.tools import schema_text
from aidm.core.views import Sections, sections
from aidm.engines.base import Person, Thing
from aidm.engines.hub import place_unmet
from aidm.engines.scenes.drafts import ReturnDraft, SceneDraft
from aidm.engines.scenes.world import SceneWorld, resolved_id

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


def scene_refusal[C: Person, P: Person](
    draft: SceneDraft[C], world: SceneWorld[C, P] | None = None
) -> str | None:
    unmet = scene_unmet(draft, world)
    return None if not unmet else "the scene needs " + "; ".join(unmet)


def scene_unmet[C: Person, P: Person](
    draft: SceneDraft[C], world: SceneWorld[C, P] | None
) -> list[str]:
    """The one bar: every refusal the install makes, so the worldsmith's one retry sees them all."""
    filed: Mapping[EntityId, C] = {} if world is None else world.cast
    everyone: Mapping[EntityId, Thing] = (
        dict(draft.cast)
        if world is None
        else {world.player.id: world.player, **world.merged_cast(draft)}
    )
    followers = () if world is None else (world.player.id, *world.party)
    others = (*draft.present, *draft.hidden)
    unmet: list[str] = []
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
    unmet.extend(_hub_unmet(draft, world))
    return unmet


def named_in(situation: str, hidden: Iterable[str], cast: Mapping[EntityId, Thing]) -> list[str]:
    """Multi-word names only: a prop called `Bell` shares its word with any bell tower."""
    lowered = situation.casefold()
    found = (
        cast[entity_id] for wanted in hidden if (entity_id := resolved_id(wanted, cast)) is not None
    )
    return [
        entity.name
        for entity in found
        if " " in entity.name.strip() and entity.name.casefold() in lowered
    ]


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
) -> str:
    return sections(
        (
            ("YOUR ROLE", role),
            ("SOURCE MATERIAL", source or "(none — write from the cast)"),
            ("SCENES SO FAR", history),
            *hub,
            ("THE WHOLE CAST", cast),
            ("ENGINE GUIDANCE", guidance),
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
    draft: SceneDraft[C], world: SceneWorld[C, P] | None
) -> list[str]:
    """A debrief means a return: it is home, and it is read to the player."""
    hub = None if world is None or world.campaign is None else world.campaign.place
    debrief = draft.debrief if isinstance(draft, ReturnDraft) else None
    unmet: list[str] = []
    if (misplaced := place_unmet(draft.place, hub, returning=debrief is not None)) is not None:
        unmet.append(misplaced)
    if debrief is not None and world is not None:
        strangers = [eid for eid, entry in world.cast.items() if not entry.known]
        if named := sorted(named_in(debrief, strangers, world.cast)):
            unmet.append(f"a debrief that does not name what the player has not met: {named}")
    return unmet
