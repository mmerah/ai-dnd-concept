"""The real app, served with scripted roles in place of the AI. For UI checks, not for play.

    uv run python qa/server.py --port 8123 --work /tmp/aidm-qa

The work directory gets copies of the shipped scenarios and characters, an empty saves folder,
and the `.env` the settings page writes. `/qa/log` lists every spawn the roles answered.
"""

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path
from random import Random

from nicegui import app, ui

sys.path.insert(0, str(Path(__file__).parent))
from agents import ScriptedAgents, Transport  # noqa: E402

from aidm.app.runtime import Runtime  # noqa: E402
from aidm.config import Settings  # noqa: E402
from aidm.ui.app import _register_pages  # noqa: E402  # pyright: ignore[reportPrivateUsage]

REPOSITORY_ROOT = Path(__file__).parents[1]


class QaRuntime(Runtime):
    """Keeps the scripted roles across a settings reload, which rebuilds the real spawner."""

    stubbed: ScriptedAgents | None = None

    def reload_settings(self) -> None:
        super().reload_settings()
        if self.stubbed is not None:
            self.spawner = self.stubbed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--transport", choices=("direct", "mcp"), default="direct")
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument("--fresh", action="store_true", help="wipe the work directory first")
    parsed = parser.parse_args()
    work: Path = parsed.work.resolve()
    if parsed.fresh and work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    for name in ("scenarios", "characters"):
        if not (work / name).exists():
            shutil.copytree(REPOSITORY_ROOT / name, work / name)
    (work / "saves").mkdir(exist_ok=True)
    os.chdir(work)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings(
        saves_dir=work / "saves",
        scenarios_dir=work / "scenarios",
        characters_dir=work / "characters",
        server_port=parsed.port,
    )
    transport: Transport = parsed.transport
    agents = ScriptedAgents(port=parsed.port, transport=transport, delay=parsed.delay)
    runtime = QaRuntime(settings, agents)
    runtime.stubbed = agents
    agents.runtime = runtime
    _register_pages(runtime)

    @app.get("/qa/log")
    def _log() -> list[dict[str, object]]:  # pyright: ignore[reportUnusedFunction]
        return [
            {
                "role": spoken.role,
                "answer": spoken.answer,
                "error": spoken.error,
                "calls": spoken.calls,
                "prompt": spoken.prompt,
            }
            for spoken in agents.log
        ]

    @app.get("/qa/chatty/{slug}")
    def _chatty(slug: str) -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """Seed the game's dice so the next party member passes the interjection d10."""
        session = runtime._sessions.get(slug)  # pyright: ignore[reportPrivateUsage]
        if session is None:
            return {"seeded": "no such session"}
        session.rng = Random(2)
        return {"seeded": slug}

    @app.get("/qa/faults")
    def _faults() -> dict[str, list[str]]:  # pyright: ignore[reportUnusedFunction]
        return {role: list(armed) for role, armed in agents.faults.items()}

    ui.run(  # pyright: ignore[reportUnknownMemberType]
        title="AI Dungeon Master (QA)",
        port=parsed.port,
        reload=False,
        show=False,
        show_welcome_message=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
