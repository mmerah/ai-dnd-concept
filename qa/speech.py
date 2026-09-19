"""Placeholder speech for the QA server: a short tone per line, written offline after a pause.

Real generation needs a key and a network. The page only needs clips that land one by one.
"""

import math
import struct
import wave
from asyncio import sleep
from pathlib import Path
from typing import override

from aidm.app.present import SAMPLE_WIDTH, Reader
from aidm.core.io import publish

SECONDS = 1.5
DELAY = 1.0
PITCH = 220.0
LOUDNESS = 0.2


class PlaceholderReader(Reader):
    """Each line takes a second to land, so the page is seen reading while later lines generate."""

    @override
    async def _generate(self, path: Path, voice: str, text: str) -> None:
        del voice, text
        await sleep(DELAY)
        rate = self.config.sample_rate

        def write(staged: Path) -> None:
            with wave.open(str(staged), "wb") as clip_file:
                clip_file.setnchannels(1)
                clip_file.setsampwidth(SAMPLE_WIDTH)
                clip_file.setframerate(rate)
                clip_file.writeframes(tone(rate))

        publish(path, write)


def tone(rate: int) -> bytes:
    frames = int(rate * SECONDS)
    peak = int(32767 * LOUDNESS)
    return b"".join(
        struct.pack("<h", int(peak * math.sin(2 * math.pi * PITCH * index / rate)))
        for index in range(frames)
    )
