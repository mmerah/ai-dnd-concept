import logging
import re
from base64 import b64decode, b64encode
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path

from httpx import AsyncClient
from pydantic import BaseModel, ConfigDict

from aidm.config import MediaConfig, ProviderConfig
from aidm.state.base import Entity, EntityId
from aidm.state.world import GameState
from aidm.turn.scene import VisibleScene

from .views import player_scene

LOGGER = logging.getLogger(__name__)

TIMEOUT = 180.0
ICON_DIR = "icons"
MAX_REFERENCES = 4
SUFFIXES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
STYLE = "Painterly fantasy illustration, muted colours, no text or lettering."
_FILENAME_SAFE = re.compile(r"[a-z0-9_-]+")


def scene_key(scene: VisibleScene) -> str:
    """What an image is of: the place and its revealed cast. Re-entering a scene reuses its file
    instead of paying for the same picture again."""
    parts = (scene.location.id, *sorted(entity.id for entity in scene.here))
    return sha1("|".join(parts).encode(), usedforsecurity=False).hexdigest()[:12]


def illustration_request(
    scene: VisibleScene, narration: str, referenced: Sequence[str] = ()
) -> str:
    lines = [
        "Draw one wide establishing view of the place below, as somebody standing in it sees it. "
        "Not a portrait, not a panel, no border.",
        f"The place: {scene.location.name} — {scene.location.brief}",
        *(f"Present: {entity.name} — {entity.brief}" for entity in scene.here),
    ]
    if narration:
        lines.append(f"What just happened: {narration}")
    if referenced:
        # Naming the attachments in order is what makes an icon a likeness rather than a mood
        # board: without it the same character is redrawn differently every scene.
        lines.append(
            f"The attached images are reference likenesses of, in order: {', '.join(referenced)}. "
            f"Keep each one's appearance."
        )
    lines.append(STYLE)
    return "\n".join(lines)


def icon_request(entity: Entity) -> str:
    return (
        f"Draw a portrait token, not a scene: {entity.name} — {entity.brief}. "
        f"The subject alone, centred and filling the square, on a plain flat background — "
        f"no setting, no other figures, no props beyond what it carries, no border. {STYLE}"
    )


@dataclass(frozen=True, slots=True)
class Generated:
    data: bytes
    suffix: str


@dataclass(frozen=True, slots=True)
class Illustrator:
    """Scene art and entity icons, both cached on disk and never regenerated once written."""

    config: MediaConfig
    provider: ProviderConfig
    saves: Path
    icon_dirs: Mapping[EntityId, Path]
    generating: set[str] = field(default_factory=set)

    def scene_art(self, state: GameState) -> Path | None:
        return _existing(self.saves, scene_key(player_scene(state)))

    def scene_pending(self, state: GameState) -> bool:
        """A scene with no file and no generation in flight is one that failed, not one to wait
        for: the page must stop showing a placeholder for it."""
        return scene_key(player_scene(state)) in self.generating

    def _icon_dir(self, entity_id: EntityId) -> Path | None:
        """None when the id cannot name a file; anything play invented lives under the save."""
        if _FILENAME_SAFE.fullmatch(entity_id) is None:
            LOGGER.warning("entity id %r cannot name a file; no icon", entity_id)
            return None
        return self.icon_dirs.get(entity_id, self.saves / ICON_DIR)

    def icon(self, entity_id: EntityId) -> Path | None:
        """What the chat shows as an avatar: a cached icon only, never a generation."""
        directory = self._icon_dir(entity_id)
        return None if directory is None else _existing(directory, entity_id)

    async def illustrate(self, state: GameState, narration: str) -> None:
        scene = player_scene(state)
        # The chat avatar wants the player's icon even when this scene's art is already cached.
        _ = await self._drawn_icon(scene.player)
        key = scene_key(scene)
        if key in self.generating or _existing(self.saves, key) is not None:
            return
        self.generating.add(key)
        try:
            await self._draw(scene, key, narration)
        finally:
            self.generating.discard(key)

    async def _draw(self, scene: VisibleScene, key: str, narration: str) -> None:
        subjects = sorted(
            (entity for entity in scene.here if entity.kind != "location"),
            key=lambda entity: entity.kind != "actor",
        )
        icons = {
            entity.name: icon
            for entity in subjects[:MAX_REFERENCES]
            if (icon := await self._drawn_icon(entity)) is not None
        }
        generated = await self._generate(
            illustration_request(scene, narration, tuple(icons)),
            self.config.scene_ratio,
            tuple(icons.values()),
        )
        if generated is not None:
            _write(self.saves / f"{key}{generated.suffix}", generated.data)

    async def _drawn_icon(self, entity: Entity) -> Path | None:
        """The cached icon, or one drawn now and kept."""
        directory = self._icon_dir(entity.id)
        if directory is None:
            return None
        found = _existing(directory, entity.id)
        if found is not None:
            return found
        generated = await self._generate(icon_request(entity), self.config.icon_ratio)
        if generated is None:
            return None
        path = directory / f"{entity.id}{generated.suffix}"
        _write(path, generated.data)
        return path

    async def _generate(
        self, prompt: str, ratio: str, references: Sequence[Path] = ()
    ) -> Generated | None:
        """A failed generation costs a log line and nothing else: media is outside the game."""
        content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
        content.extend(
            {"type": "image_url", "image_url": {"url": _data_uri(path)}} for path in references
        )
        try:
            async with AsyncClient(timeout=TIMEOUT) as client:
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


def _decode(url: str) -> Generated | None:
    header, _, payload = url.partition(",")
    suffix = SUFFIXES.get(header.removeprefix("data:").removesuffix(";base64"))
    if suffix is None or not payload:
        LOGGER.warning("image reply is not a supported data uri: %r", header[:40])
        return None
    return Generated(data=b64decode(payload), suffix=suffix)


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
