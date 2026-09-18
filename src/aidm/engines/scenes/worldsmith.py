from collections.abc import Mapping

from aidm.core.entities import Refusal, Slug
from aidm.core.prompt import Sections
from aidm.engines.base import Person, Thing, leaked_names, named_unmet, required_needs
from aidm.engines.scenes.world import SceneProposal, SceneWorld, resolved_id

OPENING_SECTIONS: Sections = (
    ("SCENES SO FAR", "(no scenes yet — write the opening)"),
    ("THE WHOLE CAST", "(no cast yet — write the people and things this scene needs)"),
    ("THE SCENE NOW", "(none yet)"),
)
OPENING = (
    "Write the opening scene of this adventure. Name the one place the player starts in and "
    "who is there. A scene ends when the player leaves it, so a `focus` on somewhere farther "
    "on belongs to a later scene. `cast` is the adventure's people and things, not the "
    "scene's. Write who is met here and who the player will meet farther in. List under "
    "`present` and `hidden` only who is here now. The opening also writes `arc`, in a few "
    "lines or in none."
)
CROSSING = (
    "The player is leaving {left} for the place in SCENE. They asked for this: "
    '"{asked}"\n\n'
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
MEANWHILE_NUDGE = (
    "Time has passed since the player last saw the people they are not with. Let one of "
    "them have moved on without the player, if the scene has room for it."
)


def check_scene[C: Person](draft: SceneProposal[C], world: SceneWorld[C] | None = None) -> None:
    """The world is optional: the authoring call has no world yet."""
    if needs := _scene_needs(draft, world):
        raise Refusal("the scene needs " + "; ".join(needs))


def _scene_needs[C: Person](draft: SceneProposal[C], world: SceneWorld[C] | None) -> list[str]:
    """Every refusal the install makes, so the worldsmith's one retry sees them all."""
    filed: Mapping[Slug, C] = {} if world is None else world.cast
    everyone: Mapping[Slug, Thing] = (
        dict(draft.cast)
        if world is None
        else {world.player.id: world.player, **world.merged_cast(draft.cast)}
    )
    followers = () if world is None else (world.player.id, *world.party)
    others = (*draft.present, *draft.hidden)
    present = [
        entity_id
        for name in draft.present
        if (entity_id := resolved_id(name, everyone)) is not None
    ]
    hidden = [
        entity_id for name in draft.hidden if (entity_id := resolved_id(name, everyone)) is not None
    ]
    needs: list[str] = []
    if named := sorted(name for name in others if resolved_id(name, everyone) in followers):
        needs.append(
            "a scene that does not list the player or the party; "
            f"they are put there by code: {named}"
        )
    if stray := sorted(name for name in others if resolved_id(name, everyone) is None):
        needs.append(f"ids that exist; these name nobody: {stray}")
    if overlap := sorted(set(present) & set(hidden)):
        needs.append(f"nobody listed as both present and hidden: {overlap}")
    if world is not None and world.player.id in draft.cast:
        needs.append("a cast that never rewrites the player")
    if misfiled := [
        f"{entry.id!r} is filed under {key!r}"
        for key, entry in draft.cast.items()
        if key != entry.id
    ]:
        needs.append("cast entries under their own id: " + "; ".join(misfiled))
    if broken := required_needs(draft.cast, filed):
        needs.append(f"cast members as the worldsmith may write them: {broken}")
    read = "\n".join((draft.title, draft.focus, draft.situation))
    watched = [entry for entry in everyone.values() if not entry.known and entry.id not in present]
    scanned = (everyone[entity_id] for entity_id in (*present, *followers, *hidden))
    hidden_entries = [everyone[entity_id] for entity_id in hidden]
    leaked = leaked_names(read, scanned, hidden_entries) | set(named_unmet(read, watched))
    if named := sorted(leaked):
        needs.append(f"a scene that does not name what the player has not met: {named}")
    if met := sorted(
        entity_id for entity_id in set(hidden) - set(followers) if everyone[entity_id].known
    ):
        needs.append(f"a hidden list without {met}, whom the player has already met")
    return needs
