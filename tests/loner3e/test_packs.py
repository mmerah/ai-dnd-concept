import pytest
from support.loner import initialized
from support.table import updated

from aidm.core.entities import Refusal
from aidm.engines.base import SRD_PACK


def test_a_game_records_its_table_sets_and_is_refused_without_them() -> None:
    engine, state = initialized()
    assert state.packs == (SRD_PACK,)

    stranded = updated(state, packs=(SRD_PACK, "uninstalled"))

    with pytest.raises(Refusal, match="not installed"):
        engine.validate(stranded)
