from pathlib import Path

import pytest
from core_test_support import initialized, updated

from aidm.core.io import ENCODING
from aidm.engines.loner3e.engine import build
from aidm.engines.loner3e.tools import SRD_PACK


def test_a_broken_user_pack_raises_rather_than_being_skipped(tmp_path: Path) -> None:
    (tmp_path / "junk.json").write_text("{not json", encoding=ENCODING)

    with pytest.raises(ValueError):
        _ = build(tmp_path)


def test_a_game_records_its_table_sets_and_is_refused_without_them() -> None:
    engine, state = initialized()
    assert state.packs == (SRD_PACK,)

    stranded = updated(state, packs=(SRD_PACK, "uninstalled"))

    with pytest.raises(ValueError, match="not installed"):
        engine.validate(stranded)
