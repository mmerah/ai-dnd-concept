from random import Random

import pytest
from core_test_support import tool_context
from pydantic_ai import ModelRetry

from aidm.core.base import PLAYER_ID, SAVE_VERSION, EngineId, Entity, EntityId, Kind
from aidm.core.mechanics import Mechanics
from aidm.core.packs import Content, ContentRef, LenientRecord
from aidm.core.sheet import Counter, Sheet
from aidm.core.tools import TurnContext
from aidm.core.world import GameState, Record, ScenarioMeta, WorldState

VAULT = EntityId("vault")
RAT = EntityId("rat")
GIANT_RAT = ContentRef(pack="testpack", collection="monsters", index="giant-rat")

MECHANICS = Mechanics(
    content=Content(
        packs=("testpack",),
        # A dict comprehension, not a display: basedpyright cannot see the `__hash__` pydantic's
        # `frozen=True` generates for `ContentRef` at runtime, so it flags a literal `{ref: ...}`.
        records={
            ref: LenientRecord(
                index="giant-rat",
                name="Giant Rat",
                text="Bite +4, 1d4 piercing.",
                numbers={"hp": 7},
            )
            for ref in (GIANT_RAT,)
        },
    ),
    refills={"short-rest": ("short-rest",), "long-rest": ("short-rest", "long-rest")},
)


def _entity(entity_id: EntityId, *, kind: Kind, known: bool, parent_id: EntityId | None) -> Entity:
    return Entity(
        id=entity_id,
        kind=kind,
        name=entity_id,
        brief=entity_id,
        known=known,
        parent_id=parent_id,
    )


def _state() -> GameState[Sheet]:
    player_sheet = Sheet(
        kind="actor",
        numbers={"armor-class": 12},
        counters={
            "hp": Counter(current=5, maximum=10),
            "slot-1": Counter(current=0, maximum=1, recharge="long-rest"),
            "grit": Counter(current=0, maximum=2, recharge="short-rest"),
        },
    )
    world = WorldState[Sheet](
        records={
            VAULT: Record(
                entity=_entity(VAULT, kind="location", known=True, parent_id=None),
                rules=Sheet(kind="location"),
            ),
            PLAYER_ID: Record(
                entity=_entity(PLAYER_ID, kind="actor", known=True, parent_id=VAULT),
                rules=player_sheet,
            ),
            RAT: Record(
                entity=_entity(RAT, kind="actor", known=False, parent_id=VAULT),
                rules=Sheet(kind="actor", counters={"hp": Counter(current=4, maximum=4)}),
            ),
        }
    )
    return GameState[Sheet](
        save_version=SAVE_VERSION,
        scenario_id="vault",
        character_id="kael",
        scenario=ScenarioMeta(title="T", premise="P"),
        engine=EngineId("test"),
        world=world,
    )


def _context(rng: Random | None = None) -> TurnContext[Sheet]:
    return TurnContext(
        draft=_state().draft(),
        rng=rng if rng is not None else Random(7),
        facts=[],
        default_rules=lambda entity: Sheet(kind=entity.kind),
    )


def _counters(deps: TurnContext[Sheet], entity_id: EntityId) -> dict[str, Counter]:
    return deps.draft.world.record(entity_id).rules.counters


def test_adjust_clamps_at_bounds_reports_what_landed_and_refuses_an_unknown_counter() -> None:
    deps = _context()
    run = tool_context(deps)

    _ = MECHANICS.adjust(run, entity_id=PLAYER_ID, counter="hp", delta=100, reason="healed")

    assert _counters(deps, PLAYER_ID)["hp"] == Counter(current=10, maximum=10)
    (fact,) = deps.facts
    assert fact.data["delta"] == 5

    _ = MECHANICS.adjust(run, entity_id=PLAYER_ID, counter="hp", delta=5, reason="healed again")
    assert len(deps.facts) == 1

    with pytest.raises(ModelRetry, match="grit, hp, slot-1"):
        _ = MECHANICS.adjust(run, entity_id=PLAYER_ID, counter="mana", delta=1, reason="x")


def test_spend_refuses_when_the_pool_cannot_cover_it_and_a_legal_spend_reduces_it() -> None:
    deps = _context()
    run = tool_context(deps)

    with pytest.raises(ModelRetry, match="cannot go below"):
        _ = MECHANICS.spend(run, entity_id=PLAYER_ID, counter="slot-1", amount=1)
    assert _counters(deps, PLAYER_ID)["slot-1"].current == 0

    _ = MECHANICS.spend(run, entity_id=PLAYER_ID, counter="hp", amount=2)
    assert _counters(deps, PLAYER_ID)["hp"].current == 3


def test_recharge_refills_only_the_counters_its_label_covers() -> None:
    deps = _context()
    run = tool_context(deps)

    _ = MECHANICS.recharge(run, entity_id=PLAYER_ID, label="short-rest")
    counters = _counters(deps, PLAYER_ID)
    assert counters["grit"].current == 2
    assert counters["slot-1"].current == 0

    _ = MECHANICS.recharge(run, entity_id=PLAYER_ID, label="long-rest")
    counters = _counters(deps, PLAYER_ID)
    assert counters["slot-1"].current == 1
    assert counters["grit"].current == 2

    with pytest.raises(ModelRetry, match="unknown recharge label"):
        _ = MECHANICS.recharge(run, entity_id=PLAYER_ID, label="nap")


def test_roll_keeps_the_higher_seeded_draw_and_carries_a_vs_verdict() -> None:
    deps = _context(Random(7))
    run = tool_context(deps)
    expected = Random(7)
    first = expected.randint(1, 20)
    second = expected.randint(1, 20)
    kept = max(first, second)

    _ = MECHANICS.roll(run, dice="1d20", reason="check", mode="keep-highest")
    (rolled,) = deps.facts
    assert rolled.data["total"] == kept
    assert rolled.data["rolled"] == [kept]

    _ = MECHANICS.roll(run, dice="1d20 + 1000", reason="check", vs=1)
    verdict = deps.facts[-1]
    assert "SUCCESS" in verdict.trace
    assert verdict.narrator is not None

    _ = MECHANICS.roll(run, dice="1d20", reason="check")
    plain = deps.facts[-1]
    assert plain.narrator is None


def test_acting_on_an_unrevealed_actor_reveals_it_before_the_counter_changes() -> None:
    deps = _context()
    run = tool_context(deps)

    _ = MECHANICS.adjust(run, entity_id=RAT, counter="hp", delta=-1, reason="bitten")

    assert [fact.kind for fact in deps.facts] == ["entity_discovered", "counter_changed"]


def test_set_number_refuses_an_unknown_key_and_sets_one_that_is_there() -> None:
    deps = _context()
    run = tool_context(deps)

    with pytest.raises(ModelRetry, match="has no number"):
        _ = MECHANICS.set_number(run, entity_id=PLAYER_ID, key="mana", value=1)

    _ = MECHANICS.set_number(run, entity_id=PLAYER_ID, key="armor-class", value=15)
    (fact,) = deps.facts
    assert (fact.data["before"], fact.data["after"]) == (12, 15)


def test_read_content_returns_the_record_and_refuses_a_bad_ref() -> None:
    rendered = MECHANICS.read_content(ref="testpack/monsters/giant-rat")
    assert "Giant Rat" in rendered
    assert "Bite +4, 1d4 piercing." in rendered

    with pytest.raises(ModelRetry, match="missing content"):
        _ = MECHANICS.read_content(ref="testpack/monsters/missing-monster")

    with pytest.raises(ModelRetry, match="malformed ref"):
        _ = MECHANICS.read_content(ref="not-a-valid-ref")


def test_tags_round_trip_and_refuse_a_duplicate_id() -> None:
    deps = _context()
    run = tool_context(deps)

    _ = MECHANICS.add_tag(
        run, entity_id=PLAYER_ID, tag_id="poisoned", name="Poisoned", text="stung"
    )
    sheet = deps.draft.world.record(PLAYER_ID).rules
    assert sheet.tag("poisoned") is not None

    with pytest.raises(ModelRetry, match="already carries"):
        _ = MECHANICS.add_tag(run, entity_id=PLAYER_ID, tag_id="poisoned", name="Poisoned")

    _ = MECHANICS.remove_tag(run, entity_id=PLAYER_ID, tag_id="poisoned")
    assert sheet.tag("poisoned") is None
