import re
from collections.abc import Iterable, Mapping, Sequence

from aidm.core.entities import Refusal, Slug
from aidm.core.play import Chapter
from aidm.core.prompt import Pairs, render_history
from aidm.engines.base import Person, Thing
from aidm.engines.scenes.tools import SceneDraft
from aidm.engines.scenes.world import SceneWorld, resolved_id

CROSSING = (
    "The player is leaving {left} for the place in SCENE. They asked for this: "
    '"{pursuit}"\n\n'
    "Their going is already told. Write the arrival. Cover the distance and the time in the "
    "fewest words that make it real. End on what they see first. WHAT HAPPENED names anyone "
    "who travelled with them. They have not acted in the new place yet, so settle nothing."
)
COMPLICATING = (
    "The game master brings a complication down on the scene the player is in: {brief}. Write "
    "the situation it makes as a new scene. The same `place` is allowed and usual. Whoever is "
    "here stays unless the brief moves them. Change the situation, not the player's answer to "
    "it. They have not acted, so settle nothing for them. `recap` is the scene as it stood "
    "before it turned."
)
TURNING = (
    "The situation changes where the player stands, and they did nothing to bring it on. Write "
    "what arrives or turns, as they see it, from SCENE and WHAT HAPPENED. End on what it asks "
    "of them. They have not answered it, so settle nothing."
)


def check_scene[C: Person](draft: SceneDraft[C], world: SceneWorld[C] | None = None) -> None:
    """The drafts may not import the world, and the authoring call has no world."""
    if unmet := scene_unmet(draft, world):
        raise Refusal("the scene needs " + "; ".join(unmet))


def scene_unmet[C: Person](draft: SceneDraft[C], world: SceneWorld[C] | None) -> list[str]:
    """Every refusal the install makes, so the worldsmith's one retry sees them all."""
    filed: Mapping[Slug, C] = {} if world is None else world.cast
    everyone: Mapping[Slug, Thing] = (
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
        if eid not in filed and (why := entry.forbidden())
    ]:
        unmet.append(f"cast members as the worldsmith may write them: {broken}")
    return unmet


def scene_sections[C: Person](world: SceneWorld[C] | None, log: Sequence[Chapter]) -> Pairs:
    if world is None:
        return (
            ("SCENES SO FAR", "(no scenes yet — write the opening)"),
            ("THE WHOLE CAST", "(no cast yet — write the people and things this scene needs)"),
            ("THE SCENE NOW", "(none yet)"),
        )
    return (
        ("SCENES SO FAR", render_history(log)),
        ("THE WHOLE CAST", world.cast_lines()),
        ("THE SCENE NOW", world.scene_lines()),
    )


def named_unmet(text: str, entities: Iterable[Thing]) -> list[str]:
    """A multi-word name or a bare id: a prop called `Bell` shares its word with any bell tower."""
    folded = text.casefold()
    return [
        entity.name
        for entity in entities
        if (" " in entity.name.strip() and entity.name.casefold() in folded)
        or re.search(rf"\b{re.escape(entity.id)}\b", text) is not None
    ]


def named_in(situation: str, hidden: Iterable[str], cast: Mapping[Slug, Thing]) -> list[str]:
    return named_unmet(
        situation,
        (
            cast[entity_id]
            for wanted in hidden
            if (entity_id := resolved_id(wanted, cast)) is not None
        ),
    )
