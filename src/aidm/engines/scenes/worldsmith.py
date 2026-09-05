from collections.abc import Iterable, Mapping

from pydantic import BaseModel

from aidm.core.entities import EntityId
from aidm.core.tools import schema_text
from aidm.core.views import sections
from aidm.engines.base import Person, Thing, named_unmet
from aidm.engines.scenes.drafts import SceneDraft
from aidm.engines.scenes.world import SceneWorld, resolved_id

CROSSING = (
    "The player is leaving {left} for the place in SCENE. They asked for this: "
    '"{pursuit}"\n\n'
    "Write the crossing: a sentence of leaving, then the arrival. Cover the distance and the time "
    "in the fewest words that make it real, and end on what they see first. WHAT HAPPENED names "
    "anyone who travelled with them. They have not acted in the new place yet, so settle nothing."
)
COMPLICATING = (
    "The game master brings a complication down on the scene the player is in: {brief}. Write "
    "the situation it makes as a new scene. The same `place` is allowed and usual; whoever is "
    "here stays unless the brief moves them. Change the situation, not the player's answer to "
    "it: they have not acted, so settle nothing for them. `recap` is the scene as it stood "
    "before it turned: what the player did here so far, for the game master and for you."
)
TURNING = (
    "The situation changes where the player stands, and they did nothing to bring it on. Write "
    "what arrives or turns, as they see it, from SCENE and WHAT HAPPENED, and end on what it "
    "asks of them. They have not answered it, so settle nothing."
)
SURPRISE = (
    "Surprise the player. Turn an established fact against them, or bring back something they "
    "have stopped thinking about. Surprise by recombining what exists, never by inventing what "
    "the source would not hold."
)


def scene_refusal[C: Person, P: Person](
    draft: SceneDraft[C], world: SceneWorld[C, P] | None = None
) -> str | None:
    """Free: the drafts may not import the world, and the authoring call has no world."""
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
        else {world.player.id: world.player, **world.merged_cast(draft.cast)}
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
    if stray := sorted(name for name in others if resolved_id(name, everyone) is None):
        unmet.append(f"ids that exist; these name nobody: {stray}")
    # `situation` is read to the player, so naming a hidden entity there hands them the find.
    if named := sorted(named_in(draft.situation, draft.hidden, everyone)):
        unmet.append(f"a situation that does not name what is hidden: {named}")
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
    scope: str,
    history: str,
    scene: str,
    cast: str,
    guidance: str,
    intent: str,
    answer: type[BaseModel],
) -> str:
    return sections(
        (
            ("YOUR ROLE", role),
            ("SOURCE MATERIAL", source or "(none — write from the cast)"),
            ("THE SCOPE OF PLAY", scope),
            ("SCENES SO FAR", history),
            ("THE WHOLE CAST", cast),
            ("THE SCENE NOW", scene),
            ("ENGINE GUIDANCE", guidance),
            ("WHAT COMES NEXT", intent),
            ("STANDING INSTRUCTION", SURPRISE),
            ("ANSWER WITH", schema_text(answer)),
        )
    )
