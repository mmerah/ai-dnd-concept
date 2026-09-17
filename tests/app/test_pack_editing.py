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


def test_a_trait_that_collides_with_the_srd_is_refused_and_nothing_is_written(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    installed, on_disk = _written(runtime), _file(tmp_path).read_text()
    values = dict(_values(runtime, MINE))
    # Rewritten, not added: the table is already as long as the rules allow.
    values["skills"] = "\n".join(("Quiet Hands", *values["skills"].splitlines()[1:]))

    with pytest.raises(Refusal, match="quiet-hands"):
        runtime.rewrite_pack(LONER3E, MINE, values)

    assert _written(runtime) == installed
    assert _file(tmp_path).read_text() == on_disk


def test_a_shipped_pack_cannot_be_rewritten(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    with pytest.raises(Refusal, match="shipped packs are read-only"):
        runtime.rewrite_pack(LONER3E, SHIPPED, {})


def test_an_edited_setting_lands_on_disk_and_in_the_running_engine(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    values = dict(_values(runtime, MINE))
    values["setting"] = SETTING

    runtime.rewrite_pack(LONER3E, MINE, values)

    assert _written(runtime).setting == SETTING
    assert json.loads(_file(tmp_path).read_text())["setting"] == SETTING


def _runtime(tmp_path: Path) -> Runtime:
    """A written pack of the player's own: a shipped kit copied under a name of its own."""
    shipped = json.loads((Loner3eEngine.directory / "packs" / f"{SHIPPED}.json").read_text())
    _file(tmp_path).parent.mkdir(parents=True)
    _file(tmp_path).write_text(json.dumps({**shipped, "name": "Mine"}))
    settings = offline_settings(tmp_path).model_copy(update={"packs_dir": tmp_path / "packs"})
    return Runtime(settings, lambda _: ScriptedSpawner())


def _file(tmp_path: Path) -> Path:
    return tmp_path / "packs" / "loner3e" / f"{MINE}.json"


def _written(runtime: Runtime) -> Loner3ePack:
    return narrowed(runtime.engines[LONER3E].packs.written[MINE], Loner3ePack)


def _values(runtime: Runtime, pack_id: Slug) -> dict[str, str]:
    engine = runtime.engines[LONER3E]
    pack = engine.packs.installed[pack_id]
    return {field.id: field.text for field in engine.edit_fields(pack)}
