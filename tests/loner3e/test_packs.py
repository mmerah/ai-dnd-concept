from pathlib import Path

import pytest
from core_test_support import initialized, updated

from aidm.core.io import ENCODING
from aidm.core.play import DecisionOption
from aidm.engines.core import load_packs
from aidm.engines.loner3e.creation import Pack
from aidm.engines.loner3e.engine import ENGINE_DIR, build
from aidm.engines.loner3e.tools import SRD_PACK, twist_table


def test_a_broken_user_pack_raises_rather_than_being_skipped(tmp_path: Path) -> None:
    (tmp_path / "junk.json").write_text("{not json", encoding=ENCODING)

    with pytest.raises(ValueError):
        _ = build(tmp_path)


def test_a_user_pack_may_carry_its_own_twist_table(tmp_path: Path) -> None:
    entry = DecisionOption(id="entry", label="Entry")
    subjects = ("a", "b", "c", "d", "e", "f")
    actions = ("g", "h", "i", "j", "k", "l")
    mine = Pack(
        name="Mine",
        source="test",
        license="test",
        concepts=(entry,),
        skills=(entry,),
        frailties=(entry,),
        gear=(entry,),
        twist_subjects=subjects,
        twist_actions=actions,
    )
    (tmp_path / "mine.json").write_text(mine.model_dump_json(), encoding=ENCODING)

    packs = load_packs((ENGINE_DIR / "packs", tmp_path), Pack)

    assert twist_table(packs, "mine") == tuple(zip(subjects, actions, strict=True))
    assert twist_table(packs, "ap01-fantasy") == twist_table(packs, SRD_PACK)


def test_a_game_records_its_table_sets_and_is_refused_without_them() -> None:
    engine, state = initialized()
    assert state.packs == (SRD_PACK,)

    stranded = updated(state, packs=(SRD_PACK, "uninstalled"))

    with pytest.raises(ValueError, match="not installed"):
        engine.validate(stranded)

    unselected = state.draft()
    unselected.payload.twist_pack = "ap01-fantasy"

    with pytest.raises(ValueError, match="which is unselected"):
        engine.validate(unselected)
