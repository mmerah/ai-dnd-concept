import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol, TypeAliasType, get_args, get_origin

from nicegui import ui
from pydantic import BaseModel, SecretStr, ValidationError
from pydantic.fields import FieldInfo

from aidm.config import Settings, env_key, save_settings
from aidm.ui.widgets import page_header

type Boxes = dict[tuple[str, ...], Box]
# A cleared box writes no key at all, which is the only way back to a field's own default.
type Changes = dict[tuple[str, ...], str | None]


class Box(Protocol):
    @property
    def value(self) -> object: ...


class SettingsForm:
    """One box per `.env` key; saving writes only the boxes whose value moved."""

    def __init__(self, settings: Settings, apply: Callable[[], str | None], boxes: Boxes) -> None:
        self.settings = settings
        self.apply = apply
        self.boxes = boxes

    def build(self) -> None:
        groups = _shown(self.settings)
        # In the header, where a panel taller than the last one cannot move it.
        with page_header("Settings"):
            ui.space()
            ui.button("Save", icon="save", on_click=self.save).props("color=primary")
        with ui.column().classes("w-full q-pa-lg items-center"):
            with ui.column().style("width: min(56rem, 100%); gap: 1rem"):
                ui.label(
                    "Each box is one key in .env. Saving applies it; reopen an open game to pick "
                    "it up. The server port applies at the next start, and .mcp.json must match it."
                ).classes("text-sm opacity-70")
                with ui.row().classes("w-full no-wrap items-start").style("gap: 1rem"):
                    with ui.tabs().props("vertical dense").classes("w-40") as tabs:
                        for name, field, _ in groups:
                            ui.tab(name, label=_label((name,), field))
                    with ui.tab_panels(tabs, value=groups[0][0]).classes("w-full"):
                        for name, field, value in groups:
                            with ui.tab_panel(name):
                                self.render(value, field, (name,))

    def render(self, value: object, field: FieldInfo, path: tuple[str, ...]) -> None:
        if not isinstance(value, BaseModel):
            self.boxes[path] = _widget(_label(path, field), field, value)
            return
        for name, nested, nested_value in _shown(value):
            if isinstance(nested_value, BaseModel):
                with ui.expansion(_label((*path, name), nested)).classes("w-full").props("dense"):
                    self.render(nested_value, nested, (*path, name))
            else:
                self.render(nested_value, nested, (*path, name))

    def changes(self) -> Changes:
        changed: Changes = {}
        for path, box in self.boxes.items():
            if env_key(path) in os.environ:
                continue
            stored = _stored(self.settings, path)
            typed = box.value
            if isinstance(stored, SecretStr):
                # The box starts blank, so only a typed key is a change.
                if isinstance(typed, str) and typed:
                    changed[path] = typed
            elif typed != stored:
                changed[path] = None if typed is None else _text(typed)
        return changed

    def save(self) -> None:
        changed = self.changes()
        if not changed:
            ui.notify("Nothing changed.", type="info")
            return
        merged = self.settings.model_dump()
        for path, typed in changed.items():
            node = merged
            for part in path[:-1]:
                node = node[part]
            node[path[-1]] = typed
        try:
            Settings.model_validate(merged)
        except ValidationError as error:
            ui.notify(str(error), type="negative", multi_line=True)
            return
        save_settings(changed)
        refusal = self.apply()
        if refusal is not None:
            ui.notify(
                f"{refusal} The keys are written; they apply on the next restart.", type="warning"
            )
            return
        ui.notify(f"Applied {len(changed)} keys.", type="positive")
        ui.navigate.reload()


def settings_page(settings: Settings, apply: Callable[[], str | None]) -> None:
    SettingsForm(settings, apply, {}).build()


def _shown(model: BaseModel) -> list[tuple[str, FieldInfo, object]]:
    """A directory is left out (repointing one hides the save library); a tuple has no widget."""
    fields = type(model).model_fields.items()
    return [
        (n, f, getattr(model, n))
        for n, f in fields
        if not isinstance(getattr(model, n), Path | tuple)
    ]


def _label(path: tuple[str, ...], field: FieldInfo) -> str:
    spelled = path[-1].replace("_", " ")
    if env_key(path) in os.environ:
        return f"{spelled} — set in your shell, which wins"
    return spelled


def _widget(label: str, field: FieldInfo, value: object) -> Box:
    bare = _unaliased(field.annotation)
    if bare is SecretStr:
        # Never read a stored key back into the DOM; blank means "leave the stored key alone".
        placeholder = "set — type to replace" if value else "not set"
        return ui.input(label, password=True, placeholder=placeholder).classes("w-full")
    if bare is bool:
        return ui.switch(label, value=value is True).classes("w-full")
    if get_origin(bare) is Literal:
        options = [str(option) for option in get_args(bare)]
        return ui.select(options, label=label, value=str(value)).classes("w-full")
    if bare is int or bare is float:
        number = value if isinstance(value, int | float) else None
        return ui.number(label, value=number).classes("w-full")
    return ui.input(label, value=_text(value)).classes("w-full")


def _unaliased(annotation: object) -> object:
    """`get_origin` of a PEP 695 alias is `None`, so the alias is read through."""
    return annotation.__value__ if isinstance(annotation, TypeAliasType) else annotation


def _text(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        # A number widget yields a float, and an int field rejects "20.0".
        return str(int(value))
    return "" if value is None else str(value)


def _stored(settings: Settings, path: tuple[str, ...]) -> object:
    """A function, not a local: assigning the walk would narrow `stored` back to `Settings`."""
    node: object = settings
    for part in path:
        node = getattr(node, part)
    return node
