"""`Dnd5eRules` is the adapter between core's engine-agnostic contract and the legacy engine
underneath it. These cover the two guarantees at that boundary: a rule event may not change a
core-visible field without `apply` noticing (F31), and `validate_state` still rejects a legacy-only
invariant violation now that it constructs the legacy state once rather than twice (F32)."""

import pytest
from aidm.domain.base import EntityId
from aidm.utils.models import updated as core_updated
from aidm_5e.codecs import ACTOR_STATE_CODEC
from aidm_5e.domain.models.base import EntityId as LegacyEntityId
from aidm_5e.domain.models.entities import ActorEntity as LegacyActor
from aidm_5e.domain.models.stats import StatBlock
from aidm_5e.rules import _require_rules_only_change  # pyright: ignore[reportPrivateUsage]
from aidm_5e.utils.models import updated
from fivee_test_support import initial_5e_game

MARA = LegacyEntityId("mara")


def test_a_core_visible_change_from_a_rule_event_fails_fast() -> None:
    """`Dnd5eRuleEvent` cannot itself move, discover or create an entity, but if a future legacy
    reducer branch ever slipped a `known`/`location_id`/`container_id` change in alongside a stats
    change, `apply` must not silently keep only the rules half of that diff."""
    before = LegacyActor(
        id=MARA,
        name="Mara",
        brief="A scribe.",
        known=True,
        location_id=LegacyEntityId("study"),
        stats=StatBlock(max_hp=10, hp=10),
    )
    changed_stats = StatBlock(max_hp=10, hp=7)
    stats_only = updated(before, stats=changed_stats)
    moved_too = updated(before, stats=changed_stats, location_id=LegacyEntityId("vault"))

    _require_rules_only_change(stats_only, before)  # a rules-only change passes silently
    with pytest.raises(ValueError, match="core-visible"):
        _require_rules_only_change(moved_too, before)


def test_validate_state_rejects_an_npc_with_progression() -> None:
    """Only the player may hold `progression`; core's own validator cannot see that far into the
    opaque rules envelope, so the legacy model's `_consistent_world` is the check. `validate_state`
    must still catch it from the single `to_legacy_state` construction, without the redundant
    `model_validate(model_dump())` round trip F32 removed."""
    engine, state = initial_5e_game()
    assert state.player.rules is not None
    player = ACTOR_STATE_CODEC.decode(state.player.rules)
    assert player.progression is not None
    mara_id = EntityId("mara")
    mara = state.world.entities[mara_id]
    assert mara.rules is not None
    mara_actor = ACTOR_STATE_CODEC.decode(mara.rules)
    borrowed = updated(mara_actor, progression=player.progression)
    broken_mara = core_updated(mara, rules=ACTOR_STATE_CODEC.encode(borrowed))
    broken = core_updated(
        state,
        world=core_updated(state.world, entities={**state.world.entities, mara_id: broken_mara}),
    )

    with pytest.raises(ValueError, match="only the player may have progression"):
        engine.rules.validate_state(broken)
