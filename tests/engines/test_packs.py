from pathlib import Path

import pytest
from support.table import ENGINES_BUILT, LONER3E, TWENTYFOURXX, narrowed

from aidm.core.entities import EngineId, Refusal
from aidm.core.io import ENCODING
from aidm.core.play import DecisionOption
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.worldsmith import Loner3eBlock, Loner3ePack
from aidm.engines.packs import SRD_PACK, Names, Pack, PackSet, read_packs
from aidm.engines.twentyfourxx.engine import TwentyfourxxEngine
from aidm.engines.twentyfourxx.worldsmith import (
    OriginProposal,
    SpecialtyProposal,
    TwentyfourxxHead,
)

TEST_ENGINE = EngineId("test")


def _loner3e_pack(name: str) -> Loner3ePack:
    return Loner3ePack(
        name=name,
        source="",
        license="",
        concepts=(DecisionOption(id="concept", label="Concept"),),
        skills=(DecisionOption(id="skill", label="Skill"),),
        frailties=(DecisionOption(id="frailty", label="Frailty"),),
        gear=(DecisionOption(id="gear", label="Gear"),),
    )


def test_read_packs_lists_a_written_pack_alongside_the_shipped_ones(tmp_path: Path) -> None:
    shipped = ENGINES_BUILT[LONER3E].directory / "packs"
    (tmp_path / "mine.json").write_text(_loner3e_pack("Mine").model_dump_json(), encoding=ENCODING)

    packs = read_packs(LONER3E, shipped, tmp_path, Loner3ePack)

    assert "mine" in packs.written
    assert "mine" in packs.installed
    assert "mine" not in packs.shipped


def test_read_packs_skips_a_written_pack_that_shadows_a_shipped_id(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    shipped = ENGINES_BUILT[LONER3E].directory / "packs"
    (tmp_path / "srd.json").write_text(
        _loner3e_pack("Fake SRD").model_dump_json(), encoding=ENCODING
    )

    packs = read_packs(LONER3E, shipped, tmp_path, Loner3ePack)

    assert "is a shipped pack" in caplog.text
    assert packs.written == {}
    assert packs.installed[SRD_PACK] == packs.shipped[SRD_PACK]


def test_read_packs_skips_a_written_file_that_is_not_a_pack(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    shipped = ENGINES_BUILT[LONER3E].directory / "packs"
    (tmp_path / "broken.json").write_text('{"name": 1}', encoding=ENCODING)
    (tmp_path / "mine.json").write_text(_loner3e_pack("Mine").model_dump_json(), encoding=ENCODING)

    packs = read_packs(LONER3E, shipped, tmp_path, Loner3ePack)

    assert caplog.text
    assert "broken" not in packs.installed
    assert "mine" in packs.installed


def test_installing_leaves_the_set_it_was_called_on_unchanged() -> None:
    packs = narrowed(ENGINES_BUILT[LONER3E], Loner3eEngine).packs

    added = packs.installing("mine", _loner3e_pack("Mine"))

    assert "mine" in added.written
    assert "mine" in added.installed
    assert "mine" not in packs.written
    assert "mine" not in packs.installed


def test_sections_shows_adventure_seeds_only_at_the_opening() -> None:
    pack = Pack(name="Test", source="", license="", seeds=("A vanished caravan.",))

    assert "ADVENTURE SEEDS" in dict(pack.sections(opening=True))
    assert "ADVENTURE SEEDS" not in dict(pack.sections(opening=False))


def test_sections_drops_empty_name_lists() -> None:
    empty = Pack(name="Test", source="", license="")
    female_only = Pack(name="Test", source="", license="", names=Names(female=("Elira",)))
    with_neutral = Pack(
        name="Test", source="", license="", names=Names(female=("Elira",), neutral=("Ash",))
    )

    assert "NAMES" not in dict(empty.sections(opening=False))
    assert dict(female_only.sections(opening=False))["NAMES"] == "female: Elira"
    assert dict(with_neutral.sections(opening=False))["NAMES"] == "female: Elira\nneutral: Ash"


def test_loner3e_pack_sections_render_trait_tags_and_factions() -> None:
    pack = _loner3e_pack("Test").model_copy(
        update={
            "factions": (
                Loner3eBlock(
                    name="The Watch",
                    concept="Keeps order",
                    skills=("Discipline",),
                    frailties=("Slow to bend",),
                ),
            )
        }
    )

    sections = dict(pack.sections(opening=False))

    assert sections["TRAIT TAGS"] == (
        "concepts: Concept\nskills: Skill\nfrailties: Frailty\ngear: Gear"
    )
    assert sections["FACTIONS"] == (
        "- The Watch — Keeps order; skills: Discipline; frailties: Slow to bend"
    )


def test_pack_set_guidance_starts_with_pack_for_the_pack_it_reads() -> None:
    pack = Pack(name="Test", source="", license="", setting="A quiet border town.")
    packs = PackSet(TEST_ENGINE, {SRD_PACK: pack}, {})

    assert packs.guidance(SRD_PACK, opening=False).startswith("PACK: Test")


def test_rules_section_is_empty_unless_the_pack_writes_rules() -> None:
    plain = Pack(name="Test", source="", license="")
    with_rules = Pack(name="Test", source="", license="", rules="Spend Luck to reroll once.")
    plain_packs = PackSet(TEST_ENGINE, {SRD_PACK: plain}, {})
    written_packs = PackSet(TEST_ENGINE, {SRD_PACK: with_rules}, {})

    assert plain_packs.rules_section(SRD_PACK) == ()
    assert written_packs.rules_section(SRD_PACK) == (
        ("SPECIAL RULES: Test", "Spend Luck to reroll once."),
    )


def test_seeds_lists_the_packs_own_seeds() -> None:
    first = Pack(name="First", source="", license="", seeds=("A vanished caravan.",))
    second = Pack(name="Second", source="", license="", seeds=("A debt come due.",))
    packs = PackSet(TEST_ENGINE, {SRD_PACK: first, "second": second}, {})

    assert packs.seeds(SRD_PACK) == ("A vanished caravan.",)
    assert packs.seeds("second") == ("A debt come due.",)


def test_require_refuses_an_uninstalled_pack() -> None:
    packs = PackSet(TEST_ENGINE, {SRD_PACK: Pack(name="SRD", source="", license="")}, {})

    with pytest.raises(Refusal, match="is not installed"):
        packs.require("gone")


def test_played_reads_the_srd_once_then_the_chosen_pack() -> None:
    srd = Pack(name="SRD", source="", license="")
    second = Pack(name="Second", source="", license="")
    packs = PackSet(TEST_ENGINE, {SRD_PACK: srd, "second": second}, {})

    assert packs.played(SRD_PACK) == (srd,)
    assert packs.played("second") == (srd, second)


def test_options_lists_the_srd_first() -> None:
    srd = Pack(name="SRD", source="", license="")
    second = Pack(name="Second", source="", license="")
    packs = PackSet(TEST_ENGINE, {"second": second, SRD_PACK: srd}, {})

    assert packs.options() == (
        DecisionOption(id=SRD_PACK, label="SRD"),
        DecisionOption(id="second", label="Second"),
    )


def test_a_twentyfourxx_head_never_gives_two_picks_the_same_id() -> None:
    engine = narrowed(ENGINES_BUILT[TWENTYFOURXX], TwentyfourxxEngine)
    head = TwentyfourxxHead(
        setting="A belt station and the ships that dock there.",
        names=Names(),
        specialties=(
            SpecialtyProposal(label="Face", detail="You talk the docks down.", skills=("Talk",)),
            SpecialtyProposal(label="Face", detail="You wear another name.", skills=("Bluff",)),
        ),
        origins=(OriginProposal(label="Face", detail="Known on every deck."),),
    )

    made = engine.pack_of(head, None, name="Test", origin="", license="")

    made_ids = tuple(option.id for option in (*made.specialties, *made.origins))
    assert made_ids == ("face", "face-2", "face-3")
