from dataclasses import dataclass

from nicegui import ui

from aidm.base import EngineId


@dataclass(frozen=True, slots=True)
class EngineAppearance:
    label: str
    colour: str


def engine_appearance(engine: EngineId) -> EngineAppearance:
    match engine:
        case "story":
            return EngineAppearance(label="STORY", colour="deep-purple-6")
        case "dnd5e":
            return EngineAppearance(label="D&D 5E", colour="red-9")


def show_engine_badge(engine: EngineId) -> None:
    appearance = engine_appearance(engine)
    ui.badge(appearance.label).props(f"color={appearance.colour} text-color=white").classes(
        "text-sm font-bold q-px-md q-py-sm"
    )
