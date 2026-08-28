from pathlib import Path

import pytest
from core_test_support import initialized

from aidm.content.io import ENCODING
from aidm.engines.core import rules
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.rules import SRD_PACK, Pack, PackEntry, Sheet, twist_table
from aidm.engines.sources import PackSources
from aidm.state.entities import PLAYER_ID


def test_a_broken_user_pack_is_skipped_and_the_shipped_ones_still_load(tmp_path: Path) -> None:
    (tmp_path / "junk.json").write_text("{not json", encoding=ENCODING)

    engine = Loner3eEngine(PackSources((tmp_path,)))

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

    engine = Loner3eEngine(PackSources((tmp_path,)))

    assert twist_table(engine.packs, "mine") == tuple(zip(subjects, actions, strict=True))
    assert twist_table(engine.packs, "ap01-fantasy") == twist_table(engine.packs, SRD_PACK)


def test_a_game_records_its_table_set_and_is_refused_without_it() -> None:
    engine, state = initialized()
    player = Sheet.model_validate(state.player.rules)
    assert (player.packs, player.twist_pack) == ((SRD_PACK,), SRD_PACK)

    draft = state.draft()
    with rules(draft.world.require(PLAYER_ID), Sheet) as sheet:
        sheet.packs = (SRD_PACK, "uninstalled")
    stranded = draft.committed()

    with pytest.raises(ValueError, match="not installed"):
        engine.validate(stranded)
