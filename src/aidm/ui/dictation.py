from nicegui import ui


class Dictation(ui.element, component="dictation.js"):
    """A mic button that dictates into `target`'s draft, via the browser's own SpeechRecognition."""

    def __init__(self, target: ui.element) -> None:
        super().__init__()
        self._props["target"] = f"c{target.id}"
