import pytest
from core_test_support import initialized, updated

from aidm.engines.base import SRD_PACK


def test_a_game_records_its_table_sets_and_is_refused_without_them() -> None:
    engine, state = initialized()
    assert state.packs == (SRD_PACK,)

    stranded = updated(state, packs=(SRD_PACK, "uninstalled"))

    with pytest.raises(ValueError, match="not installed"):
        engine.validate(stranded)
