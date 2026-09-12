import binascii
import logging
from base64 import b64decode, b64encode
from collections.abc import Sequence
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path
from typing import Self

from httpx import HTTPError
from pydantic import JsonValue

from aidm.app.providers import Claims, post_bearer
from aidm.config import MediaConfig, ProviderConfig, Settings
from aidm.core.entities import Loose, Refusal, Slug, parse_json
from aidm.core.io import FileStore, publish
from aidm.core.views import NarratorView, Subject

LOGGER = logging.getLogger(__name__)

ICON_DIR = "icons"
SUFFIXES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
SCENE_RATIO = "16:9"
ICON_RATIO = "1:1"
MAX_REFERENCES = 4


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    data: bytes
    suffix: str


@dataclass(slots=True)
class Illustrator:
    """Scene art and entity icons, both cached on disk and never regenerated once written."""

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
    ) -> Self | None:
        """Share authored icons across games while keeping generated canon and scenes per save."""
        if not settings.media.enabled:
            return None
        return cls(
            config=settings.media,
            provider=settings.providers.for_name(settings.media.provider),
            saves=store.media_dir(slug),
            icon_dirs=icon_dirs,
            style=style,
        )

    def scene_art(self, scene: NarratorView) -> Path | None:
        return _existing(self.saves, scene_key(scene))

    def icon(self, entity_id: Slug) -> Path | None:
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
            subject.label: icon
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
        """A loser of the claim race goes without rather than waiting."""
        found = self.icon(subject.id)
        if found is not None:
            return found
        # An entity id is `[a-z0-9_-]+`, so the colon keeps icon claims off the scene keys.
        with self.claims.hold(f"icon:{subject.id}") as drawing:
            if not drawing:
                return None
            generated = await self._generate(_icon_request(subject, self.style), ICON_RATIO)
        # Authored directories stay authored: a drawn icon is the save's own.
        path = self.saves / ICON_DIR / f"{subject.id}{generated.suffix}"
        publish(path, lambda staged: staged.write_bytes(generated.data))
        return path

    async def _generate(
        self, prompt: str, ratio: str, references: Sequence[Path] = ()
    ) -> GeneratedImage:
        parts: list[JsonValue] = [{"type": "text", "text": prompt}]
        parts.extend(
            {"type": "image_url", "image_url": {"url": _data_uri(path)}} for path in references
        )
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
        "Draw one wide, borderless view of this place from the eye level of someone there. "
        "Show a single scene, not a portrait or comic panel.",
        f"The place: {scene.title} — {scene.situation}",
        *(f"Present: {subject.label} — {subject.detail}" for subject in scene.subjects),
    ]
    if narration:
        lines.append(f"What just happened: {narration}")
    if referenced:
        lines.append(
            f"Use the attached images as likeness references in this order: "
            f"{', '.join(referenced)}. Keep each appearance consistent."
        )
    lines.append(style)
    return "\n".join(lines)


def _icon_request(subject: Subject, style: str) -> str:
    return (
        f"Draw a borderless portrait token of {subject.label} — {subject.detail}. "
        f"Centre the subject alone, filling the square on a plain background. "
        f"Include only props they carry. {style}"
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
