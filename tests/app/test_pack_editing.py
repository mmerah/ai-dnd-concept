import json
from pathlib import Path

import pytest
from support.table import LONER3E, ScriptedSpawner, narrowed, offline_settings

from aidm.app.runtime import Runtime
from aidm.core.entities import Refusal, Slug
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.worldsmith import Loner3ePack

MINE: Slug = "mine"
SHIPPED: Slug = "ap01-fantasy"
SETTING = "The sea took the lower town and left the towers standing in it."
SRD_SKILL = {"id": "quiet-hands", "label": "Quiet Hands", "detail": ""}


def test_a_trait_that_collides_with_the_srd_is_refused_and_nothing_is_written(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    installed, on_disk = _written(runtime), _file(tmp_path).read_text()
    values = _values(runtime, MINE)
    # Rewritten, not added: the table is already as long as the rules allow.
    values["skills"] = json.dumps([SRD_SKILL, *json.loads(values["skills"])[1:]])

    with pytest.raises(Refusal, match="quiet-hands"):
        runtime.rewrite_pack(LONER3E, MINE, values)

    assert _written(runtime) == installed
    assert _file(tmp_path).read_text() == on_disk


def test_a_shipped_pack_cannot_be_rewritten(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    with pytest.raises(Refusal, match="shipped packs are read-only"):
        runtime.rewrite_pack(LONER3E, SHIPPED, {})


def test_a_box_for_the_packs_own_provenance_is_refused_and_nothing_is_written(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    on_disk = _file(tmp_path).read_text()

    with pytest.raises(Refusal, match="name is the pack's own"):
        runtime.rewrite_pack(LONER3E, MINE, {"name": json.dumps("Renamed")})

    assert _file(tmp_path).read_text() == on_disk


def test_an_edited_setting_lands_on_disk_and_in_the_running_engine(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    values = _values(runtime, MINE)
    values["setting"] = json.dumps(SETTING)

    runtime.rewrite_pack(LONER3E, MINE, values)

    assert _written(runtime).setting == SETTING
    assert json.loads(_file(tmp_path).read_text())["setting"] == SETTING


def test_one_edited_field_leaves_every_other_field_as_it_was(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    before = _written(runtime).model_dump()
    values = _values(runtime, MINE)
    values["setting"] = json.dumps(SETTING)

    runtime.rewrite_pack(LONER3E, MINE, values)

    after = _written(_reopened(tmp_path)).model_dump()
    assert after.pop("setting") == SETTING
    assert after == {key: value for key, value in before.items() if key != "setting"}


def test_a_box_that_is_not_json_is_refused_naming_its_field(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    values = _values(runtime, MINE)
    values["seeds"] = "[a salt barge comes in with no crew aboard]"

    with pytest.raises(Refusal, match="seeds: not JSON"):
        runtime.rewrite_pack(LONER3E, MINE, values)


def _runtime(tmp_path: Path) -> Runtime:
    """A written pack of the player's own: a shipped kit copied under a name of its own."""
    shipped = json.loads((Loner3eEngine.directory / "packs" / f"{SHIPPED}.json").read_text())
    _file(tmp_path).parent.mkdir(parents=True)
    _file(tmp_path).write_text(json.dumps({**shipped, "name": "Mine"}))
    return _reopened(tmp_path)


def _reopened(tmp_path: Path) -> Runtime:
    """A second runtime over the same directory reads the packs back off disk."""
    settings = offline_settings(tmp_path).model_copy(update={"packs_dir": tmp_path / "packs"})
    return Runtime(settings, spawner=ScriptedSpawner())


def _file(tmp_path: Path) -> Path:
    return tmp_path / "packs" / "loner3e" / f"{MINE}.json"


def _written(runtime: Runtime) -> Loner3ePack:
    return narrowed(runtime.engines[LONER3E].packs.written[MINE], Loner3ePack)


def _values(runtime: Runtime, pack_id: Slug) -> dict[str, str]:
    return runtime.engines[LONER3E].packs.installed[pack_id].boxes()
