import logging
import wave
from collections.abc import Sequence
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path

from aidm.config import ProviderConfig, Settings, SpeechConfig
from aidm.core.io import FileStore
from aidm.core.model import AnyScenario
from aidm.core.play import Exchange, Speaker

from .media import claim, post_bearer

LOGGER = logging.getLogger(__name__)

SPEECH_DIR = "speech"
SAMPLE_WIDTH = 2  # 16-bit PCM


@dataclass(frozen=True, slots=True)
class Reader:
    """Spoken exchanges, cached on disk and never regenerated once written."""

    config: SpeechConfig
    provider: ProviderConfig
    saves: Path
    voice: str
    generating: set[str] = field(default_factory=set)

    def clip(self, exchange: Exchange) -> Path | None:
        path = self._path(self._key(exchange))
        return path if path.is_file() else None

    def pending(self, exchange: Exchange) -> bool:
        return self._key(exchange) in self.generating

    async def read(self, exchange: Exchange) -> None:
        """A failed generation costs a log line and nothing else: speech is outside the game."""
        requests = requests_of(exchange, self.voice, self.config.voices)
        if not requests:
            return
        key = clip_key(self.config.model, requests)
        path = self._path(key)
        if path.is_file() or not claim(self.generating, key):
            return
        try:
            chunks = [
                await post_bearer(
                    self.provider,
                    "/audio/speech",
                    speech_body(self.config.model, voice, text),
                    self.config.timeout,
                )
                for voice, text in requests
            ]
            self.saves.mkdir(parents=True, exist_ok=True)
            # Written beside, then moved: a write that dies half-way must not cache a broken clip.
            part = path.with_suffix(".part")
            with wave.open(str(part), "wb") as clip_file:
                clip_file.setnchannels(1)
                clip_file.setsampwidth(SAMPLE_WIDTH)
                clip_file.setframerate(self.config.sample_rate)
                clip_file.writeframes(b"".join(chunks))
            _ = part.replace(path)
        except Exception:
            LOGGER.exception("speech generation failed")
        finally:
            # After the write, so `pending` covers generation for the file's whole lifetime.
            self.generating.discard(key)

    def _key(self, exchange: Exchange) -> str:
        return clip_key(self.config.model, requests_of(exchange, self.voice, self.config.voices))

    def _path(self, key: str) -> Path:
        return self.saves / f"{key}.wav"


def open_reader(
    settings: Settings, store: FileStore, slug: str, scenario: AnyScenario
) -> Reader | None:
    """None unless `settings.speech.enabled`; the voice is the scenario's or the settings'."""
    if not settings.speech.enabled:
        return None
    return Reader(
        config=settings.speech,
        provider=settings.providers.for_name(settings.speech.provider),
        saves=store.media_dir(slug) / SPEECH_DIR,
        voice=scenario.voice or settings.speech.voice,
    )


def voice_of(speaker: Speaker | None, narrator: str, pool: Sequence[str]) -> str:
    """The narrator's voice for narration; a speaker keeps one voice from the pool across turns."""
    if speaker is None:
        return narrator
    return pool[int(sha1(speaker.id.encode(), usedforsecurity=False).hexdigest(), 16) % len(pool)]


def requests_of(
    exchange: Exchange, narrator: str, pool: Sequence[str]
) -> tuple[tuple[str, str], ...]:
    """(voice, text) per line, in order."""
    return tuple((voice_of(line.speaker, narrator, pool), line.text) for line in exchange.lines)


def clip_key(model: str, lines: Sequence[tuple[str, str]]) -> str:
    """The clip names a file, so the model and every (voice, text) hash to twelve hex chars."""
    joined = "\n".join(f"{voice}|{text}" for voice, text in lines)
    return sha1(f"{model}\n{joined}".encode(), usedforsecurity=False).hexdigest()[:12]


def speech_body(model: str, voice: str, text: str) -> dict[str, str]:
    return {"model": model, "input": text, "voice": voice, "response_format": "pcm"}
