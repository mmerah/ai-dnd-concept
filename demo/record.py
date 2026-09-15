"""Records the demo game as a GIF: capture at 2x, then crop, ease, style and encode.

    uv run --group qa python demo/record.py --out docs/demo.gif

The server from `server.py` must already be up. Nothing here touches the app: it drives the
page like a player, screenshots it, and does the camera work offline on the frames.
"""

import argparse
import io
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from playwright.sync_api import Locator, Page, sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from script import BEATS, CHARACTER, SCENARIO, Focus

CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
VIEWPORT = (1152, 720)
SCALE = 1.5  # master frames are the viewport at 1.5x, captured at 2x and downsampled
OUT_WIDTH = 800
BACKDROP = (18, 14, 26)
MARGIN = 20
PADDING = 26  # master pixels kept around whatever the camera is holding
RADIUS = 14
COLORS = 96
MOVE_FPS = 16
BURST_FPS = 10
ZOOM = {"page": 1.0, "scene": 1.35, "card": 1.55, "sheet": 1.45, "composer": 1.7}

type Rect = tuple[float, float, float, float]


@dataclass(slots=True)
class Cel:
    """One frame of the finished GIF: a captured frame, a crop, and how long it shows."""

    frame: int
    rect: Rect
    delay: int
    cursor: tuple[float, float] | None = None
    ripple: float = 0.0


@dataclass(slots=True)
class Recorder:
    page: Page
    frames: Path
    cels: list[Cel] = field(default_factory=list)
    taken: int = 0
    rect: Rect = (0.0, 0.0, VIEWPORT[0] * SCALE, VIEWPORT[1] * SCALE)
    cursor: tuple[float, float] | None = None

    def capture(self) -> int:
        """One master frame on disk, downsampled from the 2x screenshot."""
        raw = self.page.screenshot()
        path = self.frames / f"{self.taken:04d}.png"
        with Image.open(io.BytesIO(raw)) as shot:
            master = shot.convert("RGB").resize(  # pyright: ignore[reportUnknownMemberType]
                (round(VIEWPORT[0] * SCALE), round(VIEWPORT[1] * SCALE)), Image.Resampling.LANCZOS
            )
            master.save(path)
        self.taken += 1
        return self.taken - 1

    def hold(self, seconds: float) -> None:
        self.cels.append(Cel(self.capture(), self.rect, round(seconds * 1000), self.cursor))

    def burst(self, seconds: float, fps: float = BURST_FPS) -> None:
        delay = round(1000 / fps)
        deadline = time.time() + seconds
        while time.time() < deadline:
            self.cels.append(Cel(self.capture(), self.rect, delay, self.cursor))

    def burst_until(self, idle: Callable[[], bool], limit: float = 40) -> None:
        delay = round(1000 / BURST_FPS)
        deadline = time.time() + limit
        while time.time() < deadline and not idle():
            self.cels.append(Cel(self.capture(), self.rect, delay, self.cursor))

    def move(self, target: Rect, seconds: float = 0.55) -> None:
        """Eased camera move, synthesised from one frame so a still page costs one screenshot."""
        frame = self.capture()
        start = self.rect
        steps = max(2, round(seconds * MOVE_FPS))
        delay = round(1000 / MOVE_FPS)
        for step in range(1, steps + 1):
            progress = _eased(step / steps)
            between = tuple(a + (b - a) * progress for a, b in zip(start, target, strict=True))
            self.cels.append(Cel(frame, _rect(between), delay, self.cursor))
        self.rect = target

    def look(self, focus: Focus, seconds: float = 0.55) -> None:
        self.move(self.framed(focus), seconds)

    def framed(self, focus: Focus) -> Rect:
        """Holds the whole target with room around it, and zooms no closer than its cap."""
        if focus == "page":
            return (0.0, 0.0, VIEWPORT[0] * SCALE, VIEWPORT[1] * SCALE)
        wide, high = VIEWPORT[0] * SCALE, VIEWPORT[1] * SCALE
        box = _union(_targets(self.page, focus))
        if box is None:
            return (0.0, 0.0, wide, high)
        width = max(
            (box[2] - box[0]) * SCALE + PADDING * 2,
            ((box[3] - box[1]) * SCALE + PADDING * 2) * wide / high,
            wide / ZOOM[focus],
        )
        height = width * high / wide
        centre_x = (box[0] + box[2]) / 2 * SCALE
        centre_y = (box[1] + box[3]) / 2 * SCALE
        return _rect(
            (
                centre_x - width / 2,
                centre_y - height / 2,
                centre_x + width / 2,
                centre_y + height / 2,
            )
        )

    def point(self, locator: Locator) -> None:
        box = _box(locator)
        self.cursor = ((box[0] + box[2]) / 2 * SCALE, (box[1] + box[3]) / 2 * SCALE)

    def click(self, locator: Locator) -> None:
        self.point(locator)
        frame = self.capture()
        for step in range(5):
            self.cels.append(
                Cel(frame, self.rect, round(1000 / MOVE_FPS), self.cursor, (step + 1) / 5)
            )
        locator.click()


def _eased(progress: float) -> float:
    return 4 * progress**3 if progress < 0.5 else 1 - (-2 * progress + 2) ** 3 / 2


def _rect(raw: tuple[float, ...]) -> Rect:
    """Keeps the viewport's shape and stays inside the master frame."""
    wide, high = VIEWPORT[0] * SCALE, VIEWPORT[1] * SCALE
    left, top, right, _ = raw
    width = min(max(right - left, 200.0), wide)
    height = width * high / wide
    if height > high:
        height = high
        width = height * wide / high
    left = min(max(left, 0.0), wide - width)
    top = min(max(top, 0.0), high - height)
    return (left, top, left + width, top + height)


def _box(locator: Locator) -> tuple[float, float, float, float]:
    box = locator.bounding_box()
    assert box is not None
    return (box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"])


def _union(locators: list[Locator]) -> tuple[float, float, float, float] | None:
    boxes = [_box(one) for one in locators if one.count() > 0 and one.is_visible()]
    if not boxes:
        return None
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _targets(page: Page, focus: Focus) -> list[Locator]:
    """What the camera must hold: the change, plus the line that explains it."""
    bubbles = page.locator(".game-transcript .q-message-text-content")
    match focus:
        case "card":
            return [page.locator(".game-transcript .game-card").last, bubbles.last]
        case "scene":
            return [bubbles.nth(-3), bubbles.last]
        case "sheet":
            return [page.locator(".game-drawer-panel")]
        case "composer":
            return [page.locator(".game-composer")]
        case "page":
            return [page.locator("body")]


def style(crop: Image.Image, cel: Cel, size: tuple[int, int]) -> Image.Image:
    """The app image on a flat backdrop: rounded, shadowed, with the cursor where it was."""
    inner = (size[0] - MARGIN * 2, size[1] - MARGIN * 2)
    shot = crop.resize(inner, Image.Resampling.LANCZOS)  # pyright: ignore[reportUnknownMemberType]
    canvas = Image.new("RGB", size, BACKDROP)
    canvas.paste(_shadow(size, inner), (0, 0), _shadow(size, inner).split()[3])
    canvas.paste(shot, (MARGIN, MARGIN), _corners(inner))
    if cel.cursor is not None:
        _draw_cursor(canvas, cel, size, inner)
    return canvas


def compose(cels: list[Cel], frames: Path, size: tuple[int, int]) -> list[Image.Image]:
    made: list[Image.Image] = []
    cache: dict[int, Image.Image] = {}
    for cel in cels:
        if cel.frame not in cache:
            cache.clear()
            cache[cel.frame] = Image.open(frames / f"{cel.frame:04d}.png").convert("RGB")
        box = (round(cel.rect[0]), round(cel.rect[1]), round(cel.rect[2]), round(cel.rect[3]))
        made.append(style(cache[cel.frame].crop(box), cel, size))
    return made


def fade(made: list[Image.Image], cels: list[Cel], steps: int = 5) -> None:
    """A short dip to the backdrop, so the loop back to the opening is not a cut."""
    last = made[-1]
    ground = Image.new("RGB", last.size, BACKDROP)
    for step in range(1, steps + 1):
        made.append(Image.blend(last, ground, step / steps))
        cels.append(Cel(cels[-1].frame, cels[-1].rect, 70))


def write_gif(made: list[Image.Image], cels: list[Cel], out: Path) -> None:
    palette = made[len(made) // 2].quantize(colors=COLORS, method=Image.Quantize.MEDIANCUT)
    flat = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in made]
    flat[0].save(
        out,
        save_all=True,
        append_images=flat[1:],
        duration=[cel.delay for cel in cels],
        loop=0,
        optimize=True,
        disposal=1,
    )


def write_webp(made: list[Image.Image], cels: list[Cel], out: Path) -> None:
    made[0].save(
        out,
        save_all=True,
        append_images=made[1:],
        duration=[cel.delay for cel in cels],
        loop=0,
        quality=72,
        method=4,
    )


def idle(page: Page) -> bool:
    composer = page.locator(".game-composer textarea")
    spinning = page.locator(".q-spinner:visible:not(.q-img .q-spinner)").count() > 0
    return not spinning and composer.count() > 0 and not composer.is_disabled()


def play(recorder: Recorder) -> None:
    """The demo itself: the opening, then every beat, with the camera on what changed."""
    page = recorder.page
    recorder.burst(1.0)
    recorder.burst_until(lambda: idle(page), limit=90)
    recorder.hold(0.5)
    recorder.look("scene", 0.6)
    recorder.hold(3.4)
    recorder.look("page", 0.5)
    composer = page.locator(".game-composer textarea")
    for beat in BEATS:
        recorder.point(composer)
        _type(recorder, composer, beat.player)
        recorder.click(page.locator('button[aria-label="Send"]'))
        recorder.burst(0.4)
        recorder.burst_until(lambda: idle(page), limit=90)
        recorder.cursor = None
        recorder.hold(0.4)
        recorder.look(beat.focus, 0.6)
        recorder.hold(beat.hold)
        if beat is not BEATS[-1]:
            recorder.look("page", 0.5)
    recorder.look("page", 0.7)
    recorder.hold(2.4)


def _type(recorder: Recorder, box: Locator, text: str) -> None:
    box.click()
    for start in range(0, len(text), 3):
        box.type(text[start : start + 3], delay=8)
        recorder.cels.append(Cel(recorder.capture(), recorder.rect, 55, recorder.cursor))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8124")
    parser.add_argument("--out", type=Path, default=Path("docs/demo.gif"))
    parser.add_argument("--frames", type=Path, default=Path("/tmp/aidm-demo-frames"))
    parser.add_argument("--webp", action="store_true", help="also write a .webp beside the gif")
    parsed = parser.parse_args()
    frames: Path = parsed.frames
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    size = (OUT_WIDTH, round(OUT_WIDTH * VIEWPORT[1] / VIEWPORT[0]))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROMIUM)
        context = browser.new_context(
            viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]}, device_scale_factor=2
        )
        page = context.new_page()
        page.set_default_timeout(60000)
        page.goto(f"{parsed.base}/game/{SCENARIO}/{CHARACTER}")
        page.wait_for_selector(".game-transcript")
        page.wait_for_timeout(600)
        recorder = Recorder(page=page, frames=frames)
        play(recorder)
        browser.close()
    made = compose(recorder.cels, frames, size)
    fade(made, recorder.cels)
    out: Path = parsed.out
    out.parent.mkdir(parents=True, exist_ok=True)
    write_gif(made, recorder.cels, out)
    seconds = sum(cel.delay for cel in recorder.cels) / 1000
    print(f"{out}: {len(made)} frames, {seconds:.1f}s, {out.stat().st_size / 1e6:.2f} MB")
    if parsed.webp:
        webp = out.with_suffix(".webp")
        write_webp(made, recorder.cels, webp)
        print(f"{webp}: {webp.stat().st_size / 1e6:.2f} MB")


def _corners(size: tuple[int, int]) -> Image.Image:
    if size not in _MASKS:
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), RADIUS, fill=255)
        _MASKS[size] = mask
    return _MASKS[size]


def _shadow(size: tuple[int, int], inner: tuple[int, int]) -> Image.Image:
    if size not in _SHADOWS:
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle(
            (MARGIN, MARGIN + 6, MARGIN + inner[0], MARGIN + inner[1] + 6),
            RADIUS + 4,
            fill=(0, 0, 0, 170),
        )
        _SHADOWS[size] = layer.filter(ImageFilter.GaussianBlur(11))
    return _SHADOWS[size]


def _draw_cursor(
    canvas: Image.Image, cel: Cel, size: tuple[int, int], inner: tuple[int, int]
) -> None:
    assert cel.cursor is not None
    width = cel.rect[2] - cel.rect[0]
    at_x = MARGIN + (cel.cursor[0] - cel.rect[0]) / width * inner[0]
    at_y = MARGIN + (cel.cursor[1] - cel.rect[1]) / (cel.rect[3] - cel.rect[1]) * inner[1]
    if not (0 <= at_x <= size[0] and 0 <= at_y <= size[1]):
        return
    draw = ImageDraw.Draw(canvas, "RGBA")
    if cel.ripple:
        spread = 10 + 26 * cel.ripple
        fade = round(150 * (1 - cel.ripple))
        draw.ellipse(
            (at_x - spread, at_y - spread, at_x + spread, at_y + spread),
            outline=(220, 200, 255, fade),
            width=3,
        )
    arrow = [(at_x, at_y), (at_x, at_y + 17), (at_x + 4.4, at_y + 12.6), (at_x + 10.4, at_y + 12.2)]
    draw.polygon(arrow, fill=(250, 248, 255, 245), outline=(30, 20, 45, 220))


_MASKS: dict[tuple[int, int], Image.Image] = {}
_SHADOWS: dict[tuple[int, int], Image.Image] = {}


if __name__ == "__main__":
    main()
