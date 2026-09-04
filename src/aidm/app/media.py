import logging
from base64 import b64decode, b64encode
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path

from httpx import AsyncClient
from pydantic import JsonValue

from aidm.app.launch import LaunchTarget
from aidm.config import MediaConfig, ProviderConfig, Settings
from aidm.core.entities import EntityId, Loose
from aidm.core.io import FileStore
from aidm.core.views import NarratorView, Subject

LOGGER = logging.getLogger(__name__)

ICON_DIR = "icons"
SUFFIXES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


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
    generating: set[str] = field(default_factory=set)

    def scene_art(self, scene: NarratorView) -> Path | None:
        return _existing(self.saves, scene_key(scene))

    def icon(self, entity_id: EntityId) -> Path | None:
        """What the chat shows as an avatar: a cached icon only, never a generation."""
        for directory in (*self.icon_dirs, self.saves / ICON_DIR):
            found = _existing(directory, entity_id)
            if found is not None:
                return found
        return None

    async def illustrate(self, scene: NarratorView, player: Subject, narration: str) -> None:
        key = scene_key(scene)
        drawing = _existing(self.saves, key) is None and claim(self.generating, key)
        # The chat avatar wants the player's icon even when this scene's art is already cached.
        await self._drawn_icon(player)
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
        # An entity id is `[a-z0-9_-]+`, so the colon keeps icon claims off the scene keys.
        claim_key = f"icon:{subject.id}"
        if not claim(self.generating, claim_key):
            return None
        try:
            generated = await self._generate(
                _icon_request(subject, self.style), self.config.icon_ratio
            )
        finally:
            self.generating.discard(claim_key)
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
        parts: list[JsonValue] = [{"type": "text", "text": prompt}]
        parts.extend(
            {"type": "image_url", "image_url": {"url": _data_uri(path)}} for path in references
        )
        try:
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
            url = _ImageReply.model_validate_json(content).url()
            if url is None:
                LOGGER.warning("image reply held no image")
                return None
            return _decode(url)
        except Exception:
            LOGGER.exception("image generation failed")
            return None


class _ImageUrl(Loose):
    url: str


class _Image(Loose):
    image_url: _ImageUrl


class _Message(Loose):
    images: tuple[_Image, ...] = ()


class _Choice(Loose):
    message: _Message


class _ImageReply(Loose):
    choices: tuple[_Choice, ...] = ()

    def url(self) -> str | None:
        images = self.choices[0].message.images if self.choices else ()
        return images[0].image_url.url if images else None


def claim(generating: set[str], key: str) -> bool:
    # Synchronous: an await between the read and the write would let two callers both pay.
    if key in generating:
        return False
    generating.add(key)
    return True


async def post_bearer(
    provider: ProviderConfig, path: str, body: Mapping[str, JsonValue], timeout: float
) -> bytes:
    """One bearer POST; the caller parses the bytes, since one reply is JSON, another audio."""
    async with AsyncClient(timeout=timeout) as client:
        reply = await client.post(
            f"{provider.base_url}{path}",
            headers={"Authorization": f"Bearer {provider.api_key.get_secret_value()}"},
            json=body,
        )
        reply.raise_for_status()
        return reply.content


def open_illustrator(
    settings: Settings,
    target: LaunchTarget,
    store: FileStore,
    *,
    style: str,
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
        style=style,
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
        f"The place: {scene.title} — {scene.situation}",
        *(f"Present: {subject.name} — {subject.brief}" for subject in scene.subjects),
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
    path.write_bytes(data)
