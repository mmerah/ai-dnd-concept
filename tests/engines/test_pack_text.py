from collections.abc import Mapping

import pytest
from support.table import ENGINE_IDS, ENGINES_BUILT, LONER3E, TUNNELGOONS, TWENTYFOURXX, narrowed

from aidm.core.entities import EngineId, Refusal, Slug, parse
from aidm.engines.loner3e.worldsmith import Loner3eBlock, Loner3ePack
from aidm.engines.packs import DASH, SEPARATOR, SRD_PACK, Labelled, parse_blocks, parse_table
from aidm.engines.seam import AnyEngine
from aidm.engines.tunnelgoons.worldsmith import TunnelGoonsBlock

LONER = ENGINES_BUILT[LONER3E]
# The SRD is no kit: it has no setting and no locations, and it alone carries the twist columns.
KITS = tuple(pack_id for pack_id in LONER.packs.shipped if pack_id != SRD_PACK)
GOONS = "Watchers\nBrief: They hold the gate\nHp: 10"
HEAD: Mapping[str, object] = {
    "setting": "The sea took the lower town and left the towers standing in it.",
    "names": {"female": ("Elira",), "male": ("Toma",), "surnames": ("Vane",)},
    "rules": "",
}
BODY: Mapping[str, object] = {
    "locations": tuple(
        {"label": f"The {where}", "detail": "Somewhere to be", "encounters": "Hana"}
        for where in ("Bell Tower", "Rope Walk", "Dry Quarter")
    ),
    "seeds": tuple(
        f"A salt barge comes in with no crew aboard, again ({turn})" for turn in range(6)
    ),
}
GOON_BLOCK: Mapping[str, object] = {
    "name": "The Wrecking Crew",
    "brief": "They own what the water takes",
    "hp": 10,
}
OPERATOR_BLOCK: Mapping[str, object] = {
    "name": "The Salvage Union",
    "brief": "They own what the vacuum takes",
    "skills": ("Salvage", "Talk"),
    "items": ("Cutting torch",),
}


@pytest.mark.parametrize("pack_id", KITS)
def test_a_shipped_pack_round_trips_through_its_text_fields(pack_id: Slug) -> None:
    pack = LONER.packs.shipped[pack_id]

    assert _round_trip(LONER, pack) == pack


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_every_shipped_pack_shows_its_fields(engine_id: EngineId) -> None:
    engine = ENGINES_BUILT[engine_id]

    for pack in engine.packs.shipped.values():
        assert engine.edit_fields(pack)


def test_a_pack_that_carries_the_twist_columns_keeps_them_through_an_edit() -> None:
    """The SRD's own tables are too short to be a head, so a kit is lent its twist columns."""
    srd = narrowed(LONER.packs.srd(), Loner3ePack)
    columns = {"twist_subjects": srd.twist_subjects, "twist_actions": srd.twist_actions}
    pack = narrowed(LONER.packs.shipped[KITS[0]], Loner3ePack).model_copy(update=columns)

    rebuilt = narrowed(_round_trip(LONER, pack), Loner3ePack)

    assert (rebuilt.twist_subjects, rebuilt.twist_actions) == (
        srd.twist_subjects,
        srd.twist_actions,
    )


def test_a_written_tunnelgoons_pack_round_trips_through_its_text_fields() -> None:
    engine = ENGINES_BUILT[TUNNELGOONS]
    pack = _built(
        engine,
        {"items": tuple(f"Bear trap {number}" for number in range(6))},
        {
            "factions": (GOON_BLOCK,),
            "npcs": ({**GOON_BLOCK, "name": "Hana"},),
            "monsters": ({**GOON_BLOCK, "name": "The Thing Below", "hp": 12},),
        },
    )

    assert _round_trip(engine, pack) == pack


def test_a_written_twentyfourxx_pack_round_trips_through_its_text_fields() -> None:
    engine = ENGINES_BUILT[TWENTYFOURXX]
    pack = _built(
        engine,
        {
            "specialties": (
                {
                    "label": "Welder",
                    "detail": "You cut steel and read the welds",
                    "skills": ("Salvage",),
                    "kit": ("cutting torch",),
                },
            ),
            "origins": (
                {"label": "Belter", "detail": "Born on the belt, and it shows", "increases": 3},
            ),
        },
        {
            "factions": (OPERATOR_BLOCK,),
            "npcs": ({**OPERATOR_BLOCK, "name": "Hana"},),
            "hostiles": ({**OPERATOR_BLOCK, "name": "The Drone", "hindrances": ("Blind aft",)},),
        },
    )

    assert _round_trip(engine, pack) == pack


def test_a_table_line_with_two_dashes_is_refused_by_its_line() -> None:
    with pytest.raises(Refusal, match="line 2: "):
        _ = parse_table(f"A lamp keeper\nA diver{DASH}who works{DASH}the drowned streets")


def test_a_block_missing_a_required_key_is_refused_by_its_block() -> None:
    with pytest.raises(Refusal, match=r"block 2 \(Rats\): missing Brief"):
        _ = parse_blocks(TunnelGoonsBlock, f"{GOONS}\n\nRats\nHp: 8")


def test_a_block_value_that_is_not_a_number_is_refused_by_its_block() -> None:
    with pytest.raises(Refusal, match=r"block 1 \(Rats\): Hp is not a number"):
        _ = parse_blocks(TunnelGoonsBlock, "Rats\nBrief: They swarm the dark\nHp: many")


def test_a_label_may_not_hold_the_dash_that_parts_it_from_its_detail() -> None:
    with pytest.raises(Refusal):
        _ = parse(Labelled, {"label": f"A diver{DASH}who works the drowned streets"})


def test_a_block_list_item_may_not_hold_the_separator_it_is_joined_by() -> None:
    with pytest.raises(Refusal):
        _ = parse(
            Loner3eBlock,
            {
                "name": "The Wrecking Crew",
                "concept": "They own what the water takes",
                "skills": (f"Knots{SEPARATOR}splices",),
                "frailties": ("Owed by everyone",),
            },
        )


def _built(engine: AnyEngine, head: Mapping[str, object], body: Mapping[str, object]) -> object:
    return engine.pack_of(
        parse(engine.head, {**HEAD, **head}),
        parse(engine.body, {**BODY, **body}),
        name="Mine",
        source="written in this app from the premise",
        license="",
    )


def _round_trip(engine: AnyEngine, pack: object) -> object:
    return engine.edited(pack, {field.id: field.text for field in engine.edit_fields(pack)})
