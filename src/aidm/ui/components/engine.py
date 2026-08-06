from nicegui import ui


def show_engine_badge(badge: tuple[str, str]) -> None:
    label, colour = badge
    ui.badge(label).props(f"color={colour} text-color=white").classes(
        "text-sm font-bold q-px-md q-py-sm"
    )
