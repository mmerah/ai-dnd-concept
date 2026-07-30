from dataclasses import dataclass
from typing import Protocol

from nicegui import ui


class EngineIdentity(Protocol):
    id: str
    rules_version: int


@dataclass(frozen=True, slots=True)
class EngineAppearance:
    label: str
    colour: str


def engine_appearance(engine: EngineIdentity) -> EngineAppearance:
    match engine.id:
        case "story":
            name, colour = "STORY", "deep-purple-6"
        case "dnd5e":
            name, colour = "D&D 5E", "red-9"
        case _:
            name, colour = engine.id.upper(), "grey-8"
    return EngineAppearance(
        label=f"{name} · RULES V{engine.rules_version}",
        colour=colour,
    )


def show_engine_badge(engine: EngineIdentity) -> None:
    appearance = engine_appearance(engine)
    ui.badge(appearance.label).props(f"color={appearance.colour} text-color=white").classes(
        "text-sm font-bold q-px-md q-py-sm"
    )
