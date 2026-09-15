"""The real app with the demo roles, served for the recorder.

    uv run python demo/server.py --port 8124 --work /tmp/aidm-demo

The dice are seeded, so the same recording comes out of every run.
"""

import argparse
import logging
import shutil
import sys
from os import chdir
from pathlib import Path
from random import Random
from typing import ClassVar

from nicegui import ui

sys.path.insert(0, str(Path(__file__).parent))
from roles import DemoAgents

from aidm.app.launch import LaunchTarget
from aidm.app.runtime import GameService, Runtime
from aidm.config import Settings
from aidm.ui import theme
from aidm.ui.app import _register_pages  # pyright: ignore[reportPrivateUsage]

REPOSITORY_ROOT = Path(__file__).parents[1]


class SeededRuntime(Runtime):
    """Seeds each game's dice once, so the same recording comes out of every run."""

    seed: ClassVar[int] = 7
    seeded: ClassVar[set[str]] = set()

    def session(self, target: LaunchTarget) -> GameService:
        service = super().session(target)
        if target.slug not in self.seeded:
            self.seeded.add(target.slug)
            service.rng = Random(self.seed)
            service.chatter = Random(self.seed)
        return service


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8124)
    parser.add_argument("--work", type=Path, default=Path("/tmp/aidm-demo"))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--delay", type=float, default=0.9)
    parsed = parser.parse_args()
    work: Path = parsed.work.resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for name in ("scenarios", "characters"):
        shutil.copytree(REPOSITORY_ROOT / name, work / name)
    (work / "saves").mkdir()
    chdir(work)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings(
        saves_dir=work / "saves",
        scenarios_dir=work / "scenarios",
        characters_dir=work / "characters",
        server_port=parsed.port,
    )
    agents = DemoAgents.load(delay=parsed.delay)
    SeededRuntime.seed = parsed.seed
    runtime = SeededRuntime(settings, lambda _: agents)
    agents.runtime = runtime
    _register_pages(runtime)
    theme.install()
    ui.run(  # pyright: ignore[reportUnknownMemberType]
        title="AI Dungeon Master",
        host=settings.server_host,
        port=parsed.port,
        reload=False,
        show=False,
        show_welcome_message=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
