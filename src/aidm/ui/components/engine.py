from nicegui import ui

from aidm.core.base import EngineId
from aidm.core.registry import plugin_for


def show_engine_badge(engine: EngineId) -> None:
    label, colour = plugin_for(engine).badge
    ui.badge(label).props(f"color={colour} text-color=white").classes(
        "text-sm font-bold q-px-md q-py-sm"
    )
