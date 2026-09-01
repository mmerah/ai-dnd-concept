import logging
import re
from base64 import b64decode, b64encode
from collections.abc import Sequence
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path

from httpx import AsyncClient
from pydantic import BaseModel, ConfigDict

from aidm.config import MediaConfig, ProviderConfig, Settings
from aidm.core.io import FileStore
from aidm.core.model import AnyCharacter, AnyScenario
from aidm.core.views import NarratorView, Subject

from .launch import LaunchTarget

LOGGER = logging.getLogger(__name__)

ICON_DIR = "icons"
SUFFIXES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
_FILENAME_SAFE = re.compile(r"[a-z0-9_-]+")


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    data: bytes
    suffix: str


@dataclass(frozen=True, slots=True)
class Illustrator:
    """Scene art and entity icons, both cached on disk and never regenerated once written."""

    config: MediaConfig
    provider: ProviderConfig
    saves: Path
    icon_dirs: tuple[Path, ...]
    style: str
    generating: set[str] = field(default_factory=set)

    def scene_art(self, scene: NarratorView) -> Path | None:
        return _existing(self.saves, scene_key(scene))

    def scene_pending(self, scene: NarratorView) -> bool:
        """Only in-flight scenes wait; missing inactive scenes have failed."""
        return scene_key(scene) in self.generating

    def icon(self, entity_id: str) -> Path | None:
        """What the chat shows as an avatar: a cached icon only, never a generation."""
        if _FILENAME_SAFE.fullmatch(entity_id) is None:
            LOGGER.warning("entity id %r cannot name a file; no icon", entity_id)
            return None
        for directory in (*self.icon_dirs, self.saves / ICON_DIR):
            found = _existing(directory, entity_id)
            if found is not None:
                return found
        return None

    def _claim(self, key: str) -> bool:
        # Synchronous: an await between the read and the write would let two callers both pay.
        if key in self.generating:
            return False
        self.generating.add(key)
        return True

    async def illustrate(self, scene: NarratorView, player: Subject, narration: str) -> None:
        key = scene_key(scene)
        drawing = _existing(self.saves, key) is None and self._claim(key)
        # The chat avatar wants the player's icon even when this scene's art is already cached.
        _ = await self._drawn_icon(player)
        if not drawing:
            return
        try:
            await self._draw(scene, key, narration)
        finally:
            self.generating.discard(key)

    async def _draw(self, scene: NarratorView, key: str, narration: str) -> None:
        icons = {
            subject.name: icon
            for subject in scene.subjects[: self.config.max_references]
            if (icon := await self._drawn_icon(subject)) is not None
        }
        generated = await self._generate(
            illustration_request(scene, narration, self.style, tuple(icons)),
            self.config.scene_ratio,
            tuple(icons.values()),
        )
        if generated is not None:
            _write(self.saves / f"{key}{generated.suffix}", generated.data)

    async def _drawn_icon(self, subject: Subject) -> Path | None:
        """The cached icon, or one drawn now and kept; a loser of the race goes without."""
        found = self.icon(subject.id)
        if found is not None:
            return found
        # `icon` cannot tell an unsafe id from a missing file, so generation is guarded again.
        if _FILENAME_SAFE.fullmatch(subject.id) is None:
            return None
        # An entity id is `[a-z0-9_-]+`, so the colon keeps icon claims off the scene keys.
        claim = f"icon:{subject.id}"
        if not self._claim(claim):
            return None
        try:
            generated = await self._generate(
                _icon_request(subject, self.style), self.config.icon_ratio
            )
        finally:
            self.generating.discard(claim)
        if generated is None:
            return None
        # Authored directories stay authored: a drawn icon is the save's own.
        path = self.saves / ICON_DIR / f"{subject.id}{generated.suffix}"
        _write(path, generated.data)
        return path

    async def _generate(
        self, prompt: str, ratio: str, references: Sequence[Path] = ()
    ) -> GeneratedImage | None:
        """A failed generation costs a log line and nothing else: media is outside the game."""
        content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
        content.extend(
            {"type": "image_url", "image_url": {"url": _data_uri(path)}} for path in references
        )
        try:
            async with AsyncClient(timeout=self.config.timeout) as client:
                reply = await client.post(
                    f"{self.provider.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.provider.api_key.get_secret_value()}"},
                    json={
                        "model": self.config.model,
                        "modalities": ["image", "text"],
                        "image_config": {"aspect_ratio": ratio},
                        "messages": [{"role": "user", "content": content}],
                    },
                )
                _ = reply.raise_for_status()
                url = _ImageReply.model_validate_json(reply.content).url()
                if url is None:
                    LOGGER.warning("image reply held no image")
                    return None
                return _decode(url)
        except Exception:
            LOGGER.exception("image generation failed")
            return None


class _ImageUrl(BaseModel):
    url: str


class _Image(BaseModel):
    image_url: _ImageUrl


class _Message(BaseModel):
    model_config = ConfigDict(extra="ignore")

    images: tuple[_Image, ...] = ()


class _Choice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: _Message


class _ImageReply(BaseModel):
    model_config = ConfigDict(extra="ignore")

    choices: tuple[_Choice, ...] = ()

    def url(self) -> str | None:
        images = self.choices[0].message.images if self.choices else ()
        return images[0].image_url.url if images else None


def open_illustrator(
    settings: Settings,
    target: LaunchTarget,
    scenario: AnyScenario,
    character: AnyCharacter,
    store: FileStore,
) -> Illustrator | None:
    """Share authored icons across games while keeping generated canon and scenes per save."""
    if not settings.media.enabled:
        return None
    scenario_icons = settings.scenarios_dir / target.scenario_id / ICON_DIR
    character_icons = settings.characters_dir / target.character_id / ICON_DIR
    return Illustrator(
        config=settings.media,
        provider=settings.providers.for_name(settings.media.provider),
        saves=store.media_dir(target.slug),
        icon_dirs=(scenario_icons, character_icons),
        style=scenario.art_style or settings.media.style,
    )


def scene_key(scene: NarratorView) -> str:
    """The engine's own key, hashed because it names a file and an id may not be safe as one."""
    return sha1(scene.place.encode(), usedforsecurity=False).hexdigest()[:12]


def illustration_request(
    scene: NarratorView, narration: str, style: str, referenced: Sequence[str] = ()
) -> str:
    lines = [
        "Draw one wide, borderless view of this place from the eye level of someone there. "
        "Show a single scene, not a portrait or comic panel.",
        scene.art_prompt,
    ]
    if narration:
        lines.append(f"What just happened: {narration}")
    if referenced:
        # Map attachments to names so recurring characters retain their likeness.
        lines.append(
            f"Use the attached images as likeness references in this order: "
            f"{', '.join(referenced)}. Keep each appearance consistent."
        )
    lines.append(style)
    return "\n".join(lines)


def _icon_request(subject: Subject, style: str) -> str:
    return (
        f"Draw a borderless portrait token of {subject.name} — {subject.brief}. "
        f"Centre the subject alone, filling the square on a plain background. "
        f"Include only props they carry. {style}"
    )


def _decode(url: str) -> GeneratedImage | None:
    header, _, payload = url.partition(",")
    suffix = SUFFIXES.get(header.removeprefix("data:").removesuffix(";base64"))
    if suffix is None or not payload:
        LOGGER.warning("image reply is not a supported data uri: %r", header[:40])
        return None
    return GeneratedImage(data=b64decode(payload), suffix=suffix)


def _data_uri(path: Path) -> str:
    media_type = next(name for name, suffix in SUFFIXES.items() if suffix == path.suffix)
    return f"data:{media_type};base64,{b64encode(path.read_bytes()).decode()}"


def _existing(directory: Path, stem: str) -> Path | None:
    """The reply names the format, so a cached file is found by stem rather than assumed png."""
    candidates = (directory / f"{stem}{suffix}" for suffix in SUFFIXES.values())
    return next((path for path in candidates if path.is_file()), None)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_bytes(data)
