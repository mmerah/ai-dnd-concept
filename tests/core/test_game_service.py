import json
from pathlib import Path

import pytest
from support.loner import TARGET, open_game, session
from support.table import ScriptedSpawner, narrated, offline_settings, play_turn, tool_call, updated

from aidm.app.runtime import BEGUN, Runtime
from aidm.core.entities import EntityId, Refusal
from aidm.core.io import FileStore
from aidm.core.model import AnyGame, ScenarioMeta
from aidm.core.play import Commission
from aidm.engines.base import PLAYER_ID


class _UnsavableStore(FileStore):
    """Overrides `save` alone: `FileStore` is frozen and slotted, so this cannot monkeypatch it."""

    def save(self, slug: str, state: AnyGame) -> None:
        raise OSError("disk is gone")


def test_opening_does_not_save_and_restart_discards_durable_state(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    game = session(tmp_path)
    assert store.slugs() == ()

    store.save(TARGET.slug, game.state.model_copy(update={"notes": ["kept"]}).commit())
    assert session(tmp_path).state.notes == ["kept"]

    game = session(tmp_path)
    game.restart()
    assert game.state.notes == []
    assert store.load(TARGET.slug) is None


def test_a_commission_round_trips_through_a_save(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    game = session(tmp_path)
    commission = Commission(kind="person", brief="A witness who saw the theft happen.")

    store.save(TARGET.slug, game.state.model_copy(update={"commissions": [commission]}).commit())

    assert session(tmp_path).state.commissions == [commission]


def test_restart_keeps_scene_art_a_replayed_scene_would_reuse(tmp_path: Path) -> None:
    game = session(tmp_path)
    art = FileStore(tmp_path).media_dir(TARGET.slug) / "abc123def456.jpg"
    art.parent.mkdir(parents=True, exist_ok=True)
    _ = art.write_bytes(b"art")

    game.restart()

    assert art.read_bytes() == b"art"


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"character_id": "someone-else"}, "save is 'whispering-vault'/'someone-else'"),
        ({"scenario": ScenarioMeta(title="Another Vault", premise="Elsewhere.")}, "Another Vault"),
    ),
    ids=("another origin", "a scenario edited since the save"),
)
def test_resume_refuses_a_save_that_is_not_this_game(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    game = session(tmp_path)
    FileStore(tmp_path).save(TARGET.slug, game.state.model_copy(update=change).commit())

    with pytest.raises(Refusal, match=message):
        session(tmp_path)


def test_one_open_game_per_slug(tmp_path: Path) -> None:
    runtime = Runtime(updated(offline_settings(), saves_dir=tmp_path), ScriptedSpawner())
    opened = runtime.session(TARGET)

    assert runtime.session(TARGET) is opened


async def test_the_opening_is_narrated_once_and_costs_a_turn(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["narrator"] = [narrated("The abbot's study holds its breath.")]

    await table.service.open()

    history = table.service.engine.history(table.service.state)
    assert [exchange.prompt for exchange in history] == [BEGUN]
    assert len(history) == 1

    await table.service.open()
    assert len(table.service.engine.history(table.service.state)) == 1


async def test_an_opening_the_narrator_will_not_write_commits_nothing(tmp_path: Path) -> None:
    """The premise still stands in for it; a page reload asks again."""
    table = open_game(tmp_path)

    await table.service.open()

    assert table.service.engine.history(table.service.state) == ()
    assert not table.service.busy


async def test_a_failed_commit_still_frees_the_game(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.service.store = _UnsavableStore(table.service.store.directory)

    with pytest.raises(OSError):
        _ = await play_turn(table, "I take the map.")

    assert (table.service.busy, table.service.turn) == (False, None)


async def test_a_commission_now_is_fulfilled_between_two_master_spawns(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    asked = tool_call("roll_question", actor_id=PLAYER_ID, question="Does the door give?")
    commissioned = tool_call(
        "commission", kind="person", brief="A witness who saw who broke the seal.", later=False
    )
    table.spawner.answers["worldsmith"] = [
        json.dumps(
            {
                "cast": {
                    "elena": {
                        "id": "elena",
                        "name": "Elena",
                        "brief": "A witness who saw who broke the seal.",
                    }
                },
                "arc": "",
            }
        )
    ]
    # The initial spawn's calls; play_turn below appends the re-spawned master's own, empty turn.
    table.spawner.turns.append(table.plays((asked, commissioned)))

    state = await play_turn(table, "I ask around and call for a witness.")

    roles = [role for role, _ in table.spawner.prompts]
    assert roles == ["master", "worldsmith", "master", "narrator"]
    master_prompts = [text for role, text in table.spawner.prompts if role == "master"]
    assert "Does the door give?" in master_prompts[1]
    assert "elena" in master_prompts[1]
    assert "You asked the worldsmith for a person" in master_prompts[1]
    assert state.payload.require(EntityId("elena")).known is False

    seen_so_far = len(table.spawner.prompts)
    next_state = await play_turn(table, "I look around some more.")
    next_prompt = next(
        text for role, text in table.spawner.prompts[seen_so_far:] if role == "master"
    )
    assert "You asked the worldsmith for a person" not in next_prompt
    assert next_state.commissions == []


async def test_a_worldsmith_that_cannot_write_the_commission_leaves_the_turn_playable(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    commissioned = tool_call(
        "commission", kind="person", brief="A witness who saw who broke the seal.", later=False
    )
    table.spawner.turns.append(table.plays((commissioned,)))

    state = await play_turn(table, "I call for a witness.")

    master_prompts = [text for role, text in table.spawner.prompts if role == "master"]
    assert len(master_prompts) == 2
    assert "it could not be written" in master_prompts[1]
    assert state.commissions == []
