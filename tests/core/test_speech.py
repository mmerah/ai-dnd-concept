import wave
from asyncio import gather
from pathlib import Path

import pytest
from pydantic import SecretStr
from support.loner import session as loner_session
from support.table import CHARACTERS, SCENARIOS, EnvFileFreeSettings

from aidm.app.launch import LaunchTarget
from aidm.app.speech import (
    Reader,
    clip_key,
    open_reader,
    requests_of,
    speech_body,
    voice_of,
)
from aidm.config import ProviderConfig, Providers, SpeechConfig
from aidm.core.entities import EntityId
from aidm.core.io import FileStore
from aidm.core.play import Exchange, Line, SpokenLine

NARRATOR = "Kore"
POOL = ("Kore", "Puck", "Charon", "Zephyr", "Fenrir")
KAEL = EntityId("kael")


def _exchange() -> Exchange:
    return Exchange(
        prompt="wait",
        lines=(
            SpokenLine(text="The door groans open."),
            SpokenLine(speaker_id=KAEL, speaker="Kael", text="I step through."),
        ),
    )


def _reader(tmp_path: Path) -> Reader:
    return Reader(
        config=SpeechConfig(enabled=True),
        provider=ProviderConfig(base_url="https://example.invalid/v1", api_key=SecretStr("test")),
        saves=tmp_path / "save.media" / "speech",
        voice=NARRATOR,
    )


def test_speech_body_carries_the_request_shape() -> None:
    body = speech_body("gemini-tts", "Kore", "Hello there.")
    assert body["model"] == "gemini-tts"
    assert body["input"] == "Hello there."
    assert body["voice"] == "Kore"
    assert body["response_format"] == "pcm"


def test_voice_of_gives_the_narrator_for_narration_and_a_stable_pool_member_for_a_speaker() -> None:
    assert voice_of(None, NARRATOR, POOL) == NARRATOR
    first = voice_of(KAEL, NARRATOR, POOL)
    assert first in POOL
    assert voice_of(KAEL, NARRATOR, POOL) == first
    assert voice_of(EntityId("mara"), NARRATOR, POOL) in POOL


def test_clip_key_is_twelve_hex_chars_and_changes_with_model_voice_or_text() -> None:
    lines = (("Kore", "Hello."), ("Puck", "Hi."))
    key = clip_key("gemini-tts", lines)
    assert len(key) == 12
    assert all(char in "0123456789abcdef" for char in key)
    assert clip_key("other-model", lines) != key
    assert clip_key("gemini-tts", (("Zephyr", "Hello."), ("Puck", "Hi."))) != key
    assert clip_key("gemini-tts", (("Kore", "Bye."), ("Puck", "Hi."))) != key


async def test_read_writes_a_wav_and_caches_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exchange = _exchange()
    requests = requests_of(exchange, NARRATOR, POOL)
    chunks = {"first": b"\x01\x02\x03\x04", "second": b"\x05\x06\x07\x08"}
    bodies: list[dict[str, str]] = []

    async def _fake_post_bearer(
        _provider: ProviderConfig, path: str, body: dict[str, str], _timeout: float
    ) -> bytes:
        assert path == "/audio/speech"
        bodies.append(body)
        return chunks["first"] if len(bodies) == 1 else chunks["second"]

    monkeypatch.setattr("aidm.app.speech.post_bearer", _fake_post_bearer)
    reader = _reader(tmp_path)
    await reader.read(exchange)

    clip = reader.clip(exchange)
    assert clip is not None
    assert clip.suffix == ".wav"
    assert clip.is_relative_to(tmp_path)
    with wave.open(str(clip), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == reader.config.sample_rate
        assert wav.readframes(wav.getnframes()) == chunks["first"] + chunks["second"]
    assert len(bodies) == 2
    assert bodies[0]["voice"] == requests[0][0] == NARRATOR
    assert bodies[1]["voice"] == requests[1][0]

    await reader.read(exchange)
    assert len(bodies) == 2


async def test_read_leaves_no_file_when_generation_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exchange = _exchange()

    async def _raising(
        _provider: ProviderConfig, _path: str, _body: dict[str, str], _timeout: float
    ) -> bytes:
        raise RuntimeError("boom")

    monkeypatch.setattr("aidm.app.speech.post_bearer", _raising)
    reader = _reader(tmp_path)
    await reader.read(exchange)

    assert reader.clip(exchange) is None


def test_open_reader_is_none_when_off_and_takes_the_scenarios_voice(tmp_path: Path) -> None:
    target = LaunchTarget(scenario_id="whispering-vault", character_id="kael")
    store = FileStore(tmp_path)
    on = EnvFileFreeSettings(
        saves_dir=tmp_path,
        scenarios_dir=SCENARIOS,
        characters_dir=CHARACTERS,
        speech=SpeechConfig(enabled=True),
        providers=Providers(
            openrouter=ProviderConfig(
                base_url="https://example.invalid/v1", api_key=SecretStr("test")
            )
        ),
    )
    reader = open_reader(on, store, target.slug, voice="Puck")
    assert reader is not None
    assert reader.voice == "Puck"

    reader = open_reader(on, store, target.slug, voice=on.speech.voice)
    assert reader is not None
    assert reader.voice == on.speech.voice

    off = EnvFileFreeSettings(
        saves_dir=tmp_path, scenarios_dir=SCENARIOS, characters_dir=CHARACTERS
    )
    assert open_reader(off, store, target.slug, voice=on.speech.voice) is None


async def test_speak_reads_and_caches_the_newest_committed_exchange(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = loner_session(tmp_path)
    draft = session.state.draft()
    session.commit(session.engine.close(draft, "wait", (Line(text="The door groans open."),), ()))

    async def _fake_post_bearer(
        _provider: ProviderConfig, _path: str, _body: dict[str, str], _timeout: float
    ) -> bytes:
        return b"\x01\x02\x03\x04"

    monkeypatch.setattr("aidm.app.speech.post_bearer", _fake_post_bearer)
    session.reader = _reader(tmp_path)

    session.speak()
    await gather(*session._background)  # pyright: ignore[reportPrivateUsage]

    exchange = session.engine.history(session.state)[-1]
    assert session.newest_clip() == session.reader.clip(exchange)
    assert session.newest_clip() is not None
