import logging
import wave
from collections.abc import Sequence
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path
from typing import Self

from httpx import HTTPError

from aidm.app.providers import Claims, post_bearer
from aidm.config import ProviderConfig, Settings, SpeechConfig
from aidm.core.entities import Refusal, Slug
from aidm.core.io import FileStore, publish
from aidm.core.play import Exchange

LOGGER = logging.getLogger(__name__)

SPEECH_DIR = "speech"
SAMPLE_WIDTH = 2  # 16-bit PCM


@dataclass(slots=True)
class Reader:
    """Spoken exchanges, cached on disk and never regenerated once written."""

    config: SpeechConfig
    provider: ProviderConfig
    saves: Path
    voice: str
    claims: Claims = field(default_factory=Claims)

    @classmethod
    def open(cls, settings: Settings, store: FileStore, slug: str, *, voice: str) -> Self | None:
        if not settings.speech.enabled:
            return None
        return cls(
            config=settings.speech,
            provider=settings.providers.for_name(settings.speech.provider),
            saves=store.media_dir(slug) / SPEECH_DIR,
            voice=voice,
        )

    def clip(self, exchange: Exchange) -> Path | None:
        requests = requests_of(exchange, self.voice, self.config.voices)
        path = self._path(clip_key(self.config.model, requests))
        return path if path.is_file() else None

    async def read(self, exchange: Exchange) -> None:
        """A failed generation costs a log line and nothing else: speech is outside the game."""
        requests = requests_of(exchange, self.voice, self.config.voices)
        if not requests:
            return
        key = clip_key(self.config.model, requests)
        path = self._path(key)
        if path.is_file():
            return
        try:
            with self.claims.hold(key) as reading:
                if not reading:
                    return
                chunks = [
                    await post_bearer(
                        self.provider,
                        "/audio/speech",
                        speech_body(self.config.model, voice, text),
                        self.config.timeout,
                    )
                    for voice, text in requests
                ]

                def write(staged: Path) -> None:
                    with wave.open(str(staged), "wb") as clip_file:
                        clip_file.setnchannels(1)
                        clip_file.setsampwidth(SAMPLE_WIDTH)
                        clip_file.setframerate(self.config.sample_rate)
                        clip_file.writeframes(b"".join(chunks))

                publish(path, write)
        except (HTTPError, OSError, Refusal, wave.Error) as failed:
            LOGGER.warning("speech generation failed: %s", failed)

    def _path(self, key: str) -> Path:
        return self.saves / f"{key}.wav"


def voice_of(speaker_id: Slug | None, narrator: str, pool: Sequence[str]) -> str:
    """The narrator's voice for narration; a speaker keeps one voice from the pool across turns."""
    if speaker_id is None:
        return narrator
    return pool[int(sha1(speaker_id.encode(), usedforsecurity=False).hexdigest(), 16) % len(pool)]


def requests_of(
    exchange: Exchange, narrator: str, pool: Sequence[str]
) -> tuple[tuple[str, str], ...]:
    return tuple((voice_of(line.speaker_id, narrator, pool), line.text) for line in exchange.lines)


def clip_key(model: str, lines: Sequence[tuple[str, str]]) -> str:
    """The clip names a file, so the model and every (voice, text) hash to twelve hex chars."""
    joined = "\n".join(f"{voice}|{text}" for voice, text in lines)
    return sha1(f"{model}\n{joined}".encode(), usedforsecurity=False).hexdigest()[:12]


def speech_body(model: str, voice: str, text: str) -> dict[str, str]:
    return {"model": model, "input": text, "voice": voice, "response_format": "pcm"}
