import json
from asyncio import CancelledError, Event, sleep
from dataclasses import dataclass
from pathlib import Path
from random import Random

import pytest
from support.game import TARGET, open_game, session, with_entity
from support.table import (
    BREATHLESS,
    ScriptedSpawner,
    narrated,
    offline_settings,
    open_table,
    play_turn,
    the_way_on,
    tool_call,
    updated,
)

from aidm.app.roles import REQUESTED, Roles
from aidm.app.runtime import GameService, Runtime
from aidm.app.spawn import RunResult, Tools
from aidm.config import Role
from aidm.core.entities import Refusal
from aidm.core.io import FileStore
from aidm.core.model import AnyGame, Generation, ScenarioMeta
from aidm.core.play import Answer
from aidm.engines.base import PLAYER_ID
from aidm.engines.breathless.world import BreathlessGame
from aidm.engines.loner3e.world import Loner3eCast


class _UnsavableStore(FileStore):
    """Overrides `save` alone: `FileStore` is frozen and slotted, so this cannot monkeypatch it."""

    def write(self, _slug: str, _state: AnyGame, /) -> None:
        raise OSError("disk is gone")


def test_opening_does_not_save_and_restart_discards_durable_state(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    game = session(tmp_path)
    assert store.slugs() == ()

    store.write(TARGET.slug, game.state.model_copy(update={"notes": ["kept"]}).commit())
    assert session(tmp_path).state.notes == ["kept"]

    game = session(tmp_path)
    game.restart()
    assert game.state.notes == []
    assert store.read(TARGET.slug) is None


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
        (
            {
                "scenario": ScenarioMeta(
                    title="Another Vault", premise="Elsewhere.", scope="A single visit, brief."
                )
            },
            "Another Vault",
        ),
    ),
    ids=("another origin", "a scenario edited since the save"),
)
def test_resume_refuses_a_save_that_is_not_this_game(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    game = session(tmp_path)
    FileStore(tmp_path).write(TARGET.slug, game.state.model_copy(update=change).commit())

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

    history = table.service.state.exchanges()
    assert [exchange.mark for exchange in history] == ["opening"]
    assert len(history) == 1

    await table.service.open()
    assert len(table.service.state.exchanges()) == 1


async def test_an_opening_the_narrator_will_not_write_commits_nothing(tmp_path: Path) -> None:
    """The premise still stands in for it; a page reload asks again."""
    table = open_game(tmp_path)

    await table.service.open()

    assert table.service.state.exchanges() == ()
    assert not table.service.busy


async def test_a_failed_commit_still_frees_the_game(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.service.store = _UnsavableStore(table.service.store.directory)

    with pytest.raises(OSError):
        _ = await play_turn(table, "I take the map.")

    assert (table.service.busy, table.service.turn) == (False, None)


def _scene(**changes: object) -> str:
    scene = {
        "place": "abbots-study",
        "title": "The Abbot's Study, Disturbed",
        "situation": "A second crew has forced the outer door, and torchlight swings wild across "
        "the ledgers while Mara flattens herself against the shelves.",
        "present": ["mara"],
        "hidden": [],
        "focus": "Can you deal with the second crew before they find the stair down?",
        "recap": "The player was keeping watch on the study door when a second crew broke in.",
        "arc": "",
    }
    return json.dumps(scene | changes)


async def test_a_complication_writes_and_installs_at_the_same_place(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    place = table.state.payload.run.place
    here_before = list(table.state.payload.run.here)
    table.spawner.answers["worldsmith"] = [_scene()]

    state = await play_turn(
        table,
        "I keep watch on the study door.",
        tool_call("next_scene", complication="A second crew breaches the study door."),
        arrival="Torchlight swings wild across the ledgers.",
    )

    exchanges = state.exchanges()
    assert len(exchanges) == 2
    assert exchanges[0].words == "I keep watch on the study door."
    assert exchanges[1].mark == "story"
    assert state.payload.run.place == place
    assert all(entity_id in state.payload.cast for entity_id in here_before)
    assert [role for role, _ in table.spawner.prompts] == ["master", "worldsmith", "narrator"]
    assert state.generation is None


async def test_a_write_requested_after_something_told_ends_the_narration_there(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await play_turn(
        table,
        "I go down.",
        tool_call("next_scene", pursuit="Down the stair."),
        arrival="Rain takes the arcade.",
    )

    roles = [role for role, _ in table.spawner.prompts]
    assert roles == ["master", "narrator", "worldsmith", "narrator"]
    leaving = table.spawner.prompt("narrator")
    assert "the player has left this place" in leaving
    assert REQUESTED in leaving


async def test_a_complication_does_not_refill_the_players_spent_luck(tmp_path: Path) -> None:
    """The scene turns, it does not end: a complication runs no scene-closing refill."""
    table = open_game(tmp_path)
    table.state.payload.player.luck.current = 2
    table.service.save(table.state)
    table.spawner.answers["worldsmith"] = [_scene()]

    state = await play_turn(
        table,
        "I keep watch on the study door.",
        tool_call("next_scene", complication="A second crew breaches the study door."),
        arrival="Torchlight swings wild across the ledgers.",
    )

    installed = state.exchanges()[-1]
    assert installed.mark == "story"
    assert state.payload.player.luck.current == 2


async def test_a_failed_write_after_a_complication_leaves_the_turn_committed(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    title = table.state.payload.run.title

    state = await play_turn(
        table,
        "I keep watch on the study door.",
        tool_call("next_scene", complication="A second crew breaches the study door."),
    )

    exchange = state.exchanges()[-1]
    assert exchange.mark == "story"
    assert exchange.facts[0].card == (
        "Nothing new came down on this place after all. You are still where you were."
    )
    assert state.generation is None
    assert state.payload.run.title == title


async def test_a_failed_write_after_a_hire_names_the_hire(tmp_path: Path) -> None:
    table = open_table(tmp_path, engine_id=BREATHLESS, state_type=BreathlessGame)

    state = await play_turn(
        table,
        "I ask Ovid to guide us across the flats.",
        tool_call("hire", entity_id="ovid-sarn", terms="Guide us across the flats."),
    )

    exchange = state.exchanges()[-1]
    assert exchange.facts[0].card == "The hire could not be written; nobody signed on."
    assert state.generation is None


async def test_a_complication_after_an_offer_clears_it_only_once_installed(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    complication = tool_call("next_scene", complication="A second crew breaches the study door.")
    _ = await play_turn(table, "I have what I came for.", the_way_on())

    state = await play_turn(table, "I keep watch.", complication)
    assert state.payload.run.offered

    table.spawner.answers["worldsmith"] = [_scene()]
    state = await play_turn(table, "I keep watching.", complication, arrival="Torchlight.")
    assert not state.payload.run.offered
    assert state.payload.run.title == "The Abbot's Study, Disturbed"


async def test_no_generation_runs_once_the_game_is_over(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    state = await play_turn(
        table,
        "I keep watch, whatever comes.",
        tool_call("kill", entity_id=PLAYER_ID),
        tool_call("next_scene", complication="A second crew breaches the study door."),
    )

    assert table.service.engine.over(state) is not None
    assert not any(role == "worldsmith" for role, _ in table.spawner.prompts)
    assert len(state.payload.runs) == 1
    assert state.generation is None
    assert table.saved().generation is None


def test_a_save_never_carries_a_request(tmp_path: Path) -> None:
    game = session(tmp_path)
    draft = game.state.draft()
    draft.generation = Generation(operation="complication", detail="A crew breaks in.")
    FileStore(tmp_path).write(TARGET.slug, draft)

    assert "generation" not in json.loads(FileStore(tmp_path).read(TARGET.slug) or "")


@dataclass(slots=True)
class _TurnLandsFirst:
    """Commits an unrelated turn before answering, so `interject` sees history move on."""

    service: GameService
    inner: ScriptedSpawner

    async def run(
        self, role: Role, prompt: str, session: str | None, tools: Tools | None = None
    ) -> RunResult:
        if role == "narrator":
            self.service.save(
                self.service.engine.close(self.service.state.draft(), (), (), mark="story")
            )
        return await self.inner.run(role, prompt, session, tools)


@dataclass(slots=True)
class _StillSpeaking:
    """Never answers the member: their interjection stays in flight until something silences it."""

    inner: ScriptedSpawner
    cancelled: bool = False

    async def run(
        self, role: Role, prompt: str, session: str | None, tools: Tools | None = None
    ) -> RunResult:
        if role == "narrator" and prompt.startswith("YOUR ROLE:\nYou are Vessa Rune"):
            try:
                await Event().wait()
            except CancelledError:
                self.cancelled = True
                raise
        return await self.inner.run(role, prompt, session, tools)


def _party_of_one(service: GameService) -> Loner3eCast:
    """One chatty companion, met and travelling: she passes the d10 on three faces in ten."""
    member = Loner3eCast(
        id="vessa-rune",
        name="Vessa Rune",
        brief="A sharp-eyed pilot.",
        known=True,
        chattiness="chatty",
    )
    state = with_entity(service.state, member)
    draft = state.draft()
    draft.payload.party.append(member.id)
    service.save(draft.commit())
    return member


async def test_a_member_who_passes_the_d10_speaks_after_the_turn(tmp_path: Path) -> None:
    table = open_game(tmp_path, rng=Random(1))
    member = _party_of_one(table.service)
    table.spawner.answers["narrator"] = [
        json.dumps(
            {
                "lines": [{"speaker_id": member.id, "text": "Careful out there."}],
                "proposal": "I check the airlock seal.",
            }
        )
    ]

    await table.service.interject()

    prompt = table.spawner.prompt("narrator")
    assert f"YOUR ROLE:\nYou are {member.name}. {member.brief}" in prompt
    exchange = table.service.state.exchanges()[-1]
    assert exchange.mark == "interjection"
    assert [line.speaker_id for line in exchange.lines] == [member.id]
    assert exchange.proposal == "I check the airlock seal."
    assert table.service.phase is None


async def test_nobody_passing_the_d10_spawns_no_narrator(tmp_path: Path) -> None:
    table = open_game(tmp_path, rng=Random(0))
    _party_of_one(table.service)

    await table.service.interject()

    assert table.spawner.prompts == []
    assert table.service.state.exchanges() == ()


async def test_a_turn_that_lands_first_drops_the_interjection(tmp_path: Path) -> None:
    table = open_game(tmp_path, rng=Random(1))
    member = _party_of_one(table.service)
    table.spawner.answers["narrator"] = [narrated("Wait.", member.id)]
    table.service.roles = Roles(_TurnLandsFirst(table.service, table.spawner))

    await table.service.interject()

    assert table.service.state.exchanges()[-1].mark == "story"


async def test_an_answer_with_no_lines_records_nothing(tmp_path: Path) -> None:
    table = open_game(tmp_path, rng=Random(1))
    _party_of_one(table.service)
    before = table.service.state.exchanges()
    table.spawner.answers["narrator"] = [json.dumps({"lines": []})]

    await table.service.interject()

    assert table.service.state.exchanges() == before


async def test_interjections_disabled_starts_no_background_task(tmp_path: Path) -> None:
    table = open_game(tmp_path, rng=Random(1))
    _party_of_one(table.service)
    table.service.interjections = False

    _ = await play_turn(table, "I wait.", narration="Nothing stirs.")

    assert not table.service.speaking


async def test_a_new_turn_silences_the_member_still_speaking(tmp_path: Path) -> None:
    table = open_game(tmp_path, rng=Random(1))
    _party_of_one(table.service)
    stalled = _StillSpeaking(table.spawner)
    table.service.roles = Roles(stalled)
    _ = await play_turn(table, "I wait.", narration="Nothing stirs.")
    await sleep(0)
    assert table.service.speaking
    table.service.interjections = False

    _ = await play_turn(table, "I wait on.", narration="Still nothing.")
    await sleep(0)

    assert not table.service.speaking
    assert stalled.cancelled


async def test_reload_settings_cancels_an_evicted_sessions_background_task(
    tmp_path: Path,
) -> None:
    spawner = ScriptedSpawner()
    runtime = Runtime(updated(offline_settings(), saves_dir=tmp_path), spawner)
    opened = runtime.session(TARGET)
    opened.rng = Random(1)
    _party_of_one(opened)
    opened.roles = Roles(_StillSpeaking(spawner))
    spawner.answers["narrator"] = [narrated("Nothing stirs.")]

    await opened.play(Answer(text="I wait."))
    await sleep(0)
    assert opened.speaking

    runtime.reload_settings()

    assert not opened.speaking
