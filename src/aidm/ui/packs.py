from nicegui import ui

from aidm.app.runtime import Runtime
from aidm.core.entities import EngineId, Refusal, Slug
from aidm.ui.widgets import alert, note, page_body, page_header, page_intro

PACK_ROUTE = "/packs/{engine}/{pack}"
MONOSPACE = "font-family: ui-monospace, SFMono-Regular, Consolas, monospace"
BOX_ROWS = 12


class PackEditor:
    """Every field of one pack as a textarea; a written pack saves, a shipped one only reads."""

    def __init__(self, runtime: Runtime, engine_id: EngineId, pack_id: Slug) -> None:
        self.runtime = runtime
        self.engine_id = engine_id
        self.pack_id = pack_id
        self.boxes: dict[str, ui.textarea] = {}

    def build(self) -> None:
        """The engine and the pack are read once here: `ui` may name no engine type to be handed."""
        engine = self.runtime.engines.get(self.engine_id)
        if engine is None:
            raise Refusal(f"no rules {self.engine_id!r}")
        pack = engine.packs.installed.get(self.pack_id)
        if pack is None:
            raise Refusal(f"no pack {self.pack_id!r} for {self.engine_id!r}")
        written = self.pack_id in engine.packs.written
        page_header(pack.name, look=engine.look)
        with page_body():
            page_intro(
                "Pack",
                pack.name,
                f"{engine.title} · " + ("written in this app" if written else "shipped, read-only"),
            )
            with ui.card().classes("w-full"):
                for field_id, text in pack.boxes().items():
                    box = (
                        ui.textarea(label=_label(field_id), value=text)
                        .props(f"rows={BOX_ROWS} outlined")
                        .classes("w-full")
                        .style(MONOSPACE)
                    )
                    if not written:
                        box.props("readonly")
                    self.boxes[field_id] = box
                if written:
                    ui.button("Save", icon="save", on_click=self.save).props(
                        "color=primary"
                    ).classes("self-end")

    def save(self) -> None:
        values = {field_id: box.value or "" for field_id, box in self.boxes.items()}
        try:
            self.runtime.rewrite_pack(self.engine_id, self.pack_id, values)
        except Refusal as refused:
            alert(str(refused))
            return
        note("Saved.", good=True)


def pack_path(engine: EngineId, pack_id: Slug) -> str:
    return PACK_ROUTE.format(engine=engine, pack=pack_id)


def pack_page(runtime: Runtime, engine_id: EngineId, pack_id: Slug) -> None:
    """Raises `Refusal` for rules or a pack that is not installed; the route shows it."""
    PackEditor(runtime, engine_id, pack_id).build()


def _label(field_id: str) -> str:
    return field_id.replace("_", " ").capitalize()
