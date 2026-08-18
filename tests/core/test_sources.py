from pathlib import Path

import pytest
from core_test_support import LONER3E, scenario, settings, updated

from aidm.app.launcher import LaunchTarget
from aidm.app.session import build_engine, open_source
from aidm.content.sources import WHOLE_CHARS, ingest, whole_text
from aidm.content.store import load_scenario, write_scenario

FIXTURES = Path(__file__).parent / "fixtures" / "source"


def test_a_markdown_document_ingests_to_addressable_records() -> None:
    source = ingest(FIXTURES / "drowned-road.md")

    ids = [record.id for record in source.records]
    assert all(id_.startswith("p1-") for id_ in ids)
    assert len(set(ids)) == len(ids)
    assert not any(record.text == "p. 3" for record in source.records)

    assert not any(">" in record.text for record in source.records)
    assert any("chapel lamp is still a mile off" in record.text for record in source.records)


def test_a_pdf_ingests_with_page_provenance() -> None:
    source = ingest(FIXTURES / "drowned-road.pdf")

    assert {record.id.split("-")[0] for record in source.records} == {"p1", "p2"}
    assert any(
        record.id.startswith("p2-") and "chapel" in record.text.lower() for record in source.records
    )


def test_search_ranks_by_the_words_asked_for() -> None:
    source = ingest(FIXTURES / "drowned-road.pdf")

    found = source.search("tide bell keeper")

    assert found
    assert "Bell House" in found[0].text
    assert source.search("submarine") == ()
    assert source.passages("submarine") == ""


def test_a_cited_scenario_is_refused_without_its_document_and_ingests_it_when_present(
    tmp_path: Path,
) -> None:
    original = scenario()
    config = updated(settings(), scenarios_dir=tmp_path)
    binding = build_engine(LONER3E).binding()
    cited = updated(original.world, expansion="cited")
    document = FIXTURES / "drowned-road.pdf"

    write_scenario(tmp_path, "bare", cited, {LONER3E: original.overlay})
    write_scenario(tmp_path, "sourced", cited, {LONER3E: original.overlay}, document)

    with pytest.raises(ValueError, match="ships no source"):
        _ = open_source(config, _target("bare"), load_scenario(tmp_path, "bare", binding))
    opened = open_source(config, _target("sourced"), load_scenario(tmp_path, "sourced", binding))
    assert opened == ingest(document)


def test_whole_text_refuses_a_document_too_large_to_hand_to_a_model_whole(tmp_path: Path) -> None:
    text = "a short adventure about a bell and a tide"
    small = tmp_path / "small.md"
    small.write_text(text, encoding="utf-8")
    assert whole_text(small) == text

    big = tmp_path / "big.md"
    big.write_text("a" * (WHOLE_CHARS + 1), encoding="utf-8")
    with pytest.raises(ValueError, match="too large"):
        _ = whole_text(big)


def _target(name: str) -> LaunchTarget:
    return LaunchTarget(slug=name, scenario_id=name, character_id="kael", engine=LONER3E)
