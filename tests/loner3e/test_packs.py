from pathlib import Path

import pytest
from core_test_support import initialized

from aidm.content.io import ENCODING
from aidm.engines.loner3e.mechanics import Mechanics
from aidm.engines.loner3e.pack import SRD_PACK, Pack, PackEntry, twist_table
from aidm.engines.loner3e.rules import Loner3eEngine
from aidm.state.model import PLAYER_ID


def test_a_broken_user_pack_is_skipped_and_the_shipped_ones_still_load(tmp_path: Path) -> None:
    (tmp_path / "junk.json").write_text("{not json", encoding=ENCODING)

    engine = Loner3eEngine(tmp_path)

    assert "junk" not in engine.packs
    assert {"srd", "ap01-fantasy"} <= set(engine.packs)


def test_a_user_pack_may_carry_its_own_twist_table(tmp_path: Path) -> None:
    entry = PackEntry(id="entry", label="Entry")
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

    engine = Loner3eEngine(tmp_path)

    assert twist_table(engine.packs, "mine") == tuple(zip(subjects, actions, strict=True))
    assert twist_table(engine.packs, "ap01-fantasy") == twist_table(engine.packs, SRD_PACK)


def test_a_game_records_its_table_set_and_is_refused_without_it() -> None:
    engine, state = initialized()
    assert Mechanics.of(state).sheets[PLAYER_ID].pack == SRD_PACK

    draft = state.draft()
    mechanics = Mechanics.of(draft)
    mechanics.sheets[PLAYER_ID] = mechanics.sheets[PLAYER_ID].model_copy(
        update={"pack": "uninstalled"}
    )
    stranded = draft.committed()

    with pytest.raises(ValueError, match="not installed"):
        engine.validate(stranded)
