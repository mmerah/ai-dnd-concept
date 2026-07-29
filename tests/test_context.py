"""The context policy is the experiment: each role must see only what its job needs."""

import pytest
from support import BareRules

from aidm.agents import views
from aidm.agents.context import Scene, TurnContext
from aidm.agents.prompting import (
    creator_prompt,
    director_prompt,
    maintainer_prompt,
    narrator_prompt,
)
from aidm.content.records.base import ContentRef
from aidm.domain.models.base import EntityId
from aidm.domain.models.direction import Direction
from aidm.domain.models.entities import GrowthRequest
from aidm.domain.models.state import GameState
from aidm.utils.models import updated

DIRECTION = Direction(intent="Kael searches the study for anything hidden.", tone="hushed")
REQUEST = GrowthRequest(kind="actor", name="Elgin", brief="An apothecary.")
GHOST = ContentRef(pack="srd-2014", collection="monsters", index="ghost")


def context(state: GameState) -> TurnContext:
    return TurnContext(
        state=state,
        prompt="I search the study.",
        rules=BareRules(),
        narration="You find nothing.",
    )


def test_the_scene_buckets_are_the_lists_a_role_is_shown(state: GameState) -> None:
    """The exclusions are load-bearing: the room the player stands in and the items they carry are
    named on their own, so neither reads as somewhere to go. `unrevealed` cuts across the rest."""
    scene = Scene.of(state)
    assert scene.where.id == "study"
    assert [e.id for e in scene.carried] == ["lantern"]
    assert [e.id for e in scene.here] == ["mara"]  # elena is here too, but unknown
    assert [e.id for e in scene.elsewhere] == []
    assert [e.id for e in scene.unrevealed] == ["vault", "elena", "vault_map"]


def test_the_room_the_player_stands_in_stays_discoverable(state: GameState) -> None:
    """It is `where`, so it is never offered as a place to go — but an unrevealed one is still a
    legal `discover` target, and dropping it from that list would make it unreachable."""
    study = state.world.entities[EntityId("study")]
    dark = updated(state, world=state.world.replacing(updated(study, known=False)))
    scene = Scene.of(dark)
    assert study.id not in {e.id for e in (*scene.here, *scene.elsewhere)}
    assert "the study[id=study]" in views.unrevealed(scene)


def test_unrevealed_canon_never_reaches_the_narrator(state: GameState) -> None:
    """The Narrator alone writes what the player reads, so it is the one role kept in the dark."""
    ctx = context(state)
    built = {
        "director": director_prompt(ctx),
        "narrator": narrator_prompt(ctx, DIRECTION),
        "maintainer": maintainer_prompt(ctx),
        "creator": creator_prompt(ctx, REQUEST),
    }
    for role, prompt in built.items():
        assert ("An archivist." in prompt) == (role != "narrator"), f"{role}: wrong canon"


def test_known_entities_carry_their_ids_for_the_director(state: GameState) -> None:
    """The bug: the Director could not name a known entity because its id was hidden from it."""
    director = director_prompt(context(state))
    assert "the vault map[id=vault_map]" in director
    assert "Mara[id=mara] (npc)" in director
    assert "— actor" not in director


def test_a_carried_item_keeps_its_id_and_brief(state: GameState) -> None:
    """Regression: an item in an inventory must stay in context, not drop to a bare name — the
    Director needs its id to drop or give it, and its brief to reason about it."""
    shown = views.character(Scene.of(state), BareRules())
    assert "- a lantern[id=lantern] — A tin lantern." in shown


def test_an_item_another_actor_carries_is_shown_with_its_holder(state: GameState) -> None:
    lantern = updated(state.world.entities[EntityId("lantern")], container_id=EntityId("mara"))
    entities = {**state.world.entities, EntityId("lantern"): lantern}
    handed = updated(state, world=updated(state.world, entities=entities))
    assert "a lantern[id=lantern] (item) — held by Mara" in views.here(Scene.of(handed))


def test_an_npc_stat_block_includes_health_armour_and_attributes(state: GameState) -> None:
    shown = views.statblocks(Scene.of(state), BareRules())
    assert (
        "Mara[id=mara] (npc) — hp 4/4 — ac 10"
        " — attributes strength 10, dexterity 10, constitution 10,"
        " intelligence 10, wisdom 10, charisma 10"
    ) in shown


def test_a_record_the_pack_lost_is_rendered_not_skipped(state: GameState) -> None:
    """A miss must reach the prompt: skipping it turns a stat block into a bare name, and the
    Director then plans against a monster it cannot see the moves of."""
    mara = state.world.entities[EntityId("mara")]
    lost = updated(state, world=state.world.replacing(updated(mara, ref=GHOST)))
    shown = views.statblocks(Scene.of(lost), BareRules())
    assert "missing content srd-2014/monsters/ghost: unknown_pack" in shown


def test_no_role_is_ever_shown_the_player_as_an_entity(state: GameState) -> None:
    for view in (views.here, views.elsewhere, views.unrevealed, views.catalogue):
        assert "[id=player]" not in view(Scene.of(state)), view.__name__


def test_narrator_reads_the_plan_before_the_outcome(state: GameState) -> None:
    """The intent gives the Narrator context; the events read last, because they overrule it."""
    narrator = narrator_prompt(context(state), DIRECTION)
    assert DIRECTION.tone in narrator
    assert narrator.index(DIRECTION.intent) < narrator.index("WHAT HAPPENED")


def test_a_known_speaker_is_rendered_by_id(state: GameState) -> None:
    direction = Direction(intent="i", tone="t", speaker_id=EntityId("mara"))
    narrator = narrator_prompt(context(state), direction)
    assert "Mara[id=mara] — A scribe." in narrator


def test_a_hidden_speaker_fails_fast(state: GameState) -> None:
    direction = Direction(intent="i", tone="t", speaker_id=EntityId("elena"))
    with pytest.raises(ValueError, match="unknown or hidden speaker"):
        narrator_prompt(context(state), direction)
