import wave
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import SecretStr
from support.game import session as loner_session
from support.table import drain

from aidm.app.present import Reader, clip_key, requests_of, speech_body
from aidm.config import ProviderConfig, SpeechConfig
from aidm.core.entities import Refusal
from aidm.core.play import Exchange, SpokenLine

NARRATOR = "Kore"
POOL = ("Kore", "Puck", "Charon", "Zephyr", "Fenrir")
KAEL = "kael"


def _exchange() -> Exchange:
    return Exchange(
        words="wait",
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


async def test_read_writes_one_wav_per_line_in_order_and_caches_each(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exchange = _exchange()
    requests = requests_of(exchange, NARRATOR, POOL)
    chunks = (b"\x01\x02\x03\x04", b"\x05\x06\x07\x08")
    bodies: list[dict[str, str]] = []
    reader = _reader(tmp_path)
    landed_before_second: list[tuple[Path | None, ...]] = []

    async def _fake_post_bearer(
        _provider: ProviderConfig, path: str, body: dict[str, str], _timeout: float
    ) -> bytes:
        assert path == "/audio/speech"
        bodies.append(body)
        if len(bodies) == 2:
            landed_before_second.append(reader.clips(exchange))
        return chunks[len(bodies) - 1]

    monkeypatch.setattr("aidm.app.present.post_bearer", _fake_post_bearer)
    await reader.read(exchange)

    clips = reader.clips(exchange)
    assert len(clips) == 2
    for clip, chunk in zip(clips, chunks, strict=True):
        assert clip is not None
        assert clip.suffix == ".wav"
        assert clip.is_relative_to(tmp_path)
        with wave.open(str(clip), "rb") as wav:
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.getframerate() == reader.config.sample_rate
            assert wav.readframes(wav.getnframes()) == chunk
    # The first line was on disk before the second was asked for: it plays while the rest generate.
    assert landed_before_second == [(clips[0], None)]
    assert len(bodies) == 2
    assert requests[0][0] == NARRATOR
    assert bodies[0] == speech_body(reader.config.model, *requests[0])
    assert bodies[0]["response_format"] == "pcm"
    assert bodies[0]["input"] == requests[0][1]
    assert bodies[0]["model"] == reader.config.model
    assert bodies[1]["voice"] == requests[1][0]
    assert clips[0] is not None
    assert clips[0].stem == clip_key(reader.config.model, *requests[0])

    await reader.read(exchange)
    assert len(bodies) == 2


async def test_a_failed_line_ends_the_reading_and_keeps_the_lines_before_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exchange = Exchange(
        words="wait",
        lines=(
            SpokenLine(text="The door groans open."),
            SpokenLine(speaker_id=KAEL, speaker="Kael", text="I step through."),
            SpokenLine(text="Dust falls."),
        ),
    )
    bodies: list[dict[str, str]] = []

    async def _fake_post_bearer(
        _provider: ProviderConfig, _path: str, body: dict[str, str], _timeout: float
    ) -> bytes:
        bodies.append(body)
        if len(bodies) == 2:
            raise Refusal("the voice is out")
        return b"\x01\x02"

    monkeypatch.setattr("aidm.app.present.post_bearer", _fake_post_bearer)
    reader = _reader(tmp_path)
    await reader.read(exchange)

    clips = reader.clips(exchange)
    assert clips[0] is not None
    assert clips[1:] == (None, None)
    assert len(bodies) == 2


def test_a_reader_switched_off_has_no_clip_for_any_line(tmp_path: Path) -> None:
    reader = replace(_reader(tmp_path), config=SpeechConfig(enabled=False))
    assert reader.clips(_exchange()) == (None, None)


async def test_speak_reads_and_caches_the_newest_committed_exchange(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = loner_session(tmp_path)
    draft = session.state.draft()
    session.save(
        session.engine.close(draft, (SpokenLine(text="The door groans open."),), (), words="wait")
    )

    async def _fake_post_bearer(
        _provider: ProviderConfig, _path: str, _body: dict[str, str], _timeout: float
    ) -> bytes:
        return b"\x01\x02\x03\x04"

    monkeypatch.setattr("aidm.app.present.post_bearer", _fake_post_bearer)
    session.presenter = replace(session.presenter, reader=_reader(tmp_path))

    exchange = session.state.exchanges()[-1]
    session.present()
    await drain(session)

    assert session.clips(exchange) == session.presenter.reader.clips(exchange)
    assert session.clips(exchange) != (None,)
