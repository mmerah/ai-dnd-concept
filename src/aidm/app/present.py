import binascii
import logging
import wave
from asyncio import to_thread
from base64 import b64decode, b64encode
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path
from typing import Any, Self

from httpx import HTTPError
from pydantic import JsonValue

from aidm.app.providers import Claims, post_bearer
from aidm.config import MediaConfig, ProviderConfig, Settings, SpeechConfig
from aidm.core.entities import Loose, Refusal, Slug, parse_json
from aidm.core.io import FileStore, publish
from aidm.core.play import Exchange
from aidm.core.views import NarratorView, Subject

LOGGER = logging.getLogger(__name__)

ICON_DIR = "icons"
SUFFIXES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
SCENE_RATIO = "16:9"
ICON_RATIO = "1:1"
MAX_REFERENCES = 4
SPEECH_DIR = "speech"
SAMPLE_WIDTH = 2  # 16-bit PCM


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    data: bytes
    suffix: str


@dataclass(frozen=True, slots=True)
class Illustrator:
    config: MediaConfig
    provider: ProviderConfig
    saves: Path
    icon_dirs: tuple[Path, ...]
    style: str
    claims: Claims = field(default_factory=Claims)

    @classmethod
    def open(
        cls,
        settings: Settings,
        store: FileStore,
        slug: str,
        *,
        style: str,
        icon_dirs: tuple[Path, ...],
    ) -> Self:
        """Authored icons are shared between games. Drawn art stays with the save."""
        return cls(
            config=settings.media,
            provider=settings.providers.for_name(settings.media.provider),
            saves=store.media_dir(slug),
            icon_dirs=icon_dirs,
            style=style,
        )

    def scene_art(self, scene: NarratorView) -> Path | None:
        return _existing(self.saves, scene_key(scene)) if self.config.enabled else None

    def icon(self, entity_id: Slug) -> Path | None:
        if not self.config.enabled:
            return None
        for directory in (*self.icon_dirs, self.saves / ICON_DIR):
            found = _existing(directory, entity_id)
            if found is not None:
                return found
        return None

    async def illustrate(self, scene: NarratorView, player: Subject, narration: str) -> None:
        key = scene_key(scene)
        try:
            with self.claims.hold(key) as drawing:
                # The chat avatar wants the player's icon even when this scene is cached.
                await self._drawn_icon(player)
                if drawing and _existing(self.saves, key) is None:
                    await self._draw(scene, key, narration)
        except (HTTPError, OSError, Refusal) as failed:
            LOGGER.warning("image generation failed: %s", failed)

    async def _draw(self, scene: NarratorView, key: str, narration: str) -> None:
        icons = {
            subject.name: icon
            for subject in scene.subjects[:MAX_REFERENCES]
            if (icon := await self._drawn_icon(subject)) is not None
        }
        generated = await self._generate(
            illustration_request(scene, narration, self.style, tuple(icons)),
            SCENE_RATIO,
            tuple(icons.values()),
        )
        publish(
            self.saves / f"{key}{generated.suffix}",
            lambda staged: staged.write_bytes(generated.data),
        )

    async def _drawn_icon(self, subject: Subject) -> Path | None:
        """The loser of the claim race gets no icon and does not wait."""
        found = self.icon(subject.id)
        if found is not None:
            return found
        # An entity id is `[a-z0-9_-]+`, so the colon keeps icon claims off the scene keys.
        with self.claims.hold(f"icon:{subject.id}") as drawing:
            if not drawing:
                return None
            generated = await self._generate(_icon_request(subject, self.style), ICON_RATIO)
            # Authored directories stay authored: a drawn icon belongs to the save.
            path = self.saves / ICON_DIR / f"{subject.id}{generated.suffix}"
            publish(path, lambda staged: staged.write_bytes(generated.data))
            return path

    async def _generate(
        self, prompt: str, ratio: str, references: Sequence[Path] = ()
    ) -> GeneratedImage:
        parts: list[JsonValue] = [{"type": "text", "text": prompt}]
        uris = await to_thread(lambda: [_data_uri(path) for path in references])
        parts.extend({"type": "image_url", "image_url": {"url": uri}} for uri in uris)
        content = await post_bearer(
            self.provider,
            "/chat/completions",
            {
                "model": self.config.model,
                "modalities": ["image", "text"],
                "image_config": {"aspect_ratio": ratio},
                "messages": [{"role": "user", "content": parts}],
            },
            self.config.timeout,
        )
        url = parse_json(_ImageReply, content).url()
        if url is None:
            raise Refusal("image reply held no image")
        return _decode(url)


@dataclass(frozen=True, slots=True)
class Reader:
    config: SpeechConfig
    provider: ProviderConfig
    saves: Path
    voice: str
    claims: Claims = field(default_factory=Claims)

    @classmethod
    def open(cls, settings: Settings, store: FileStore, slug: str, *, voice: str) -> Self:
        return cls(
            config=settings.speech,
            provider=settings.providers.for_name(settings.speech.provider),
            saves=store.media_dir(slug) / SPEECH_DIR,
            voice=voice,
        )

    def clips(self, exchange: Exchange) -> tuple[Path | None, ...]:
        if not self.config.enabled:
            return (None,) * len(exchange.lines)
        return tuple(
            path if (path := self._path(voice, text)).is_file() else None
            for voice, text in requests_of(exchange, self.voice, self.config.voices)
        )

    async def read(self, exchange: Exchange) -> None:
        """A failed line costs a log line and ends the reading: speech is outside the game."""
        for voice, text in requests_of(exchange, self.voice, self.config.voices):
            path = self._path(voice, text)
            if path.is_file():
                continue
            try:
                with self.claims.hold(path.stem) as reading:
                    if reading:
                        await self._generate(path, voice, text)
            except (HTTPError, OSError, Refusal, wave.Error) as failed:
                LOGGER.warning("speech generation failed: %s", failed)
                return

    async def _generate(self, path: Path, voice: str, text: str) -> None:
        pcm = await post_bearer(
            self.provider,
            "/audio/speech",
            speech_body(self.config.model, voice, text),
            self.config.timeout,
        )

        def write(staged: Path) -> None:
            with wave.open(str(staged), "wb") as clip_file:
                clip_file.setnchannels(1)
                clip_file.setsampwidth(SAMPLE_WIDTH)
                clip_file.setframerate(self.config.sample_rate)
                clip_file.writeframes(pcm)

        publish(path, write)

    def _path(self, voice: str, text: str) -> Path:
        return self.saves / f"{clip_key(self.config.model, voice, text)}.wav"


@dataclass(frozen=True, slots=True)
class Presenter:
    illustrator: Illustrator
    reader: Reader

    @classmethod
    def open(
        cls,
        settings: Settings,
        store: FileStore,
        slug: str,
        *,
        style: str,
        icon_dirs: tuple[Path, ...],
        voice: str,
    ) -> Self:
        return cls(
            illustrator=Illustrator.open(settings, store, slug, style=style, icon_dirs=icon_dirs),
            reader=Reader.open(settings, store, slug, voice=voice),
        )

    @property
    def enabled(self) -> bool:
        return self.illustrator.config.enabled or self.reader.config.enabled

    def present(
        self, view: NarratorView, player: Subject, newest: Exchange | None
    ) -> tuple[Coroutine[Any, Any, None], ...]:
        art = ()
        if self.illustrator.config.enabled:
            narration = "" if newest is None else newest.narration()
            art = (self.illustrator.illustrate(view, player, narration),)
        return (*art, *self.speak(newest))

    def speak(self, newest: Exchange | None) -> tuple[Coroutine[Any, Any, None], ...]:
        if newest is None or not self.reader.config.enabled:
            return ()
        return (self.reader.read(newest),)


class _ImageUrl(Loose):
    url: str


class _Image(Loose):
    image_url: _ImageUrl


class _Message(Loose):
    images: tuple[_Image, ...] = ()


class _ImageChoice(Loose):
    message: _Message


class _ImageReply(Loose):
    choices: tuple[_ImageChoice, ...] = ()

    def url(self) -> str | None:
        images = self.choices[0].message.images if self.choices else ()
        return images[0].image_url.url if images else None


def scene_key(scene: NarratorView) -> str:
    """Hashed because `place` names a file."""
    return sha1(scene.place.encode(), usedforsecurity=False).hexdigest()[:12]


def illustration_request(
    scene: NarratorView, narration: str, style: str, referenced: Sequence[str] = ()
) -> str:
    lines = [
        "Draw one wide view of this place, with no border. Use the eye level of a person who "
        "is there. Draw one scene. Do not draw a portrait. Do not draw a comic panel.",
        f"The place: {scene.title} — {scene.situation}",
        *(f"Present: {subject.name} — {subject.brief}" for subject in scene.subjects),
    ]
    if narration:
        lines.append(f"What just happened: {narration}")
    if referenced:
        lines.append(
            f"The attached images show how these subjects look, in this order: "
            f"{', '.join(referenced)}. Keep the look of each subject the same."
        )
    lines.append(style)
    return "\n".join(lines)


def voice_of(speaker_id: Slug | None, narrator: str, pool: Sequence[str]) -> str:
    """A speaker keeps one voice from the pool across turns."""
    if speaker_id is None:
        return narrator
    return pool[int(sha1(speaker_id.encode(), usedforsecurity=False).hexdigest(), 16) % len(pool)]


def requests_of(
    exchange: Exchange, narrator: str, pool: Sequence[str]
) -> tuple[tuple[str, str], ...]:
    return tuple((voice_of(line.speaker_id, narrator, pool), line.text) for line in exchange.lines)


def clip_key(model: str, voice: str, text: str) -> str:
    """The clip names a file, so the model, the voice and the text hash to twelve hex chars."""
    return sha1("\n".join((model, voice, text)).encode(), usedforsecurity=False).hexdigest()[:12]


def speech_body(model: str, voice: str, text: str) -> dict[str, str]:
    return {"model": model, "input": text, "voice": voice, "response_format": "pcm"}


def _icon_request(subject: Subject, style: str) -> str:
    return (
        f"Draw a portrait token of {subject.name} — {subject.brief}, with no border. "
        f"Put the subject alone in the centre and fill the square. Use a plain background. "
        f"Show only the items that the subject carries. {style}"
    )


def _decode(url: str) -> GeneratedImage:
    header, _, payload = url.partition(",")
    suffix = SUFFIXES.get(header.removeprefix("data:").removesuffix(";base64"))
    if suffix is None or not payload:
        raise Refusal(f"image reply is not a supported data uri: {header[:40]!r}")
    try:
        data = b64decode(payload)
    except binascii.Error as broken:
        raise Refusal(f"image reply is not base64: {broken}") from broken
    return GeneratedImage(data=data, suffix=suffix)


def _data_uri(path: Path) -> str:
    media_type = next(name for name, suffix in SUFFIXES.items() if suffix == path.suffix)
    return f"data:{media_type};base64,{b64encode(path.read_bytes()).decode()}"


def _existing(directory: Path, stem: str) -> Path | None:
    """The reply names the format, so a cached file is found by stem rather than assumed png."""
    candidates = (directory / f"{stem}{suffix}" for suffix in SUFFIXES.values())
    return next((path for path in candidates if path.is_file()), None)
