import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Literal, TypeAliasType, get_args, get_origin

from nicegui import ui
from pydantic import BaseModel, SecretStr, ValidationError
from pydantic.fields import FieldInfo

from aidm.config import Settings, env_key, save_settings
from aidm.ui.widgets import page_body, page_header, page_intro

type Widget = ui.input | ui.switch | ui.select | ui.number
# A cleared box writes no key at all, which is the only way back to a field's own default.
type Changes = dict[tuple[str, ...], str | None]


class SettingsForm:
    def __init__(self, settings: Settings, apply: Callable[[], str | None]) -> None:
        self.settings = settings
        self.apply = apply
        self.boxes: dict[tuple[str, ...], Widget] = {}

    def build(self) -> None:
        groups = _shown(self.settings)
        # In the header, where a panel taller than the last one cannot move it.
        with page_header("Settings"):
            ui.space()
            ui.button("Save", icon="save", on_click=self.save).props("color=primary")
        with page_body():
            page_intro(
                "Configuration",
                "Settings",
                "Each box is one key in .env. Saving applies it; reopen an open game to pick "
                "it up. The server port applies at the next start.",
            )
            with ui.tabs().props("dense outside-arrows mobile-arrows").classes("w-full") as tabs:
                for name, _, _ in groups:
                    ui.tab(name, label=_label((name,)))
            with ui.tab_panels(tabs, value=groups[0][0]).classes("w-full game-card"):
                for name, field, value in groups:
                    with ui.tab_panel(name):
                        self.render(value, field, (name,))

    def render(self, value: object, field: FieldInfo, path: tuple[str, ...]) -> None:
        if not isinstance(value, BaseModel):
            self.boxes[path] = _widget(_label(path), field, value)
            return
        for name, nested, nested_value in _shown(value):
            if isinstance(nested_value, BaseModel):
                with ui.expansion(_label((*path, name))).classes("w-full game-card").props("dense"):
                    self.render(nested_value, nested, (*path, name))
            else:
                self.render(nested_value, nested, (*path, name))

    def save(self) -> None:
        changed = changes(self.settings, {path: box.value for path, box in self.boxes.items()})
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
            ui.notify(refusal_text(error), type="negative", multi_line=True)
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
    SettingsForm(settings, apply).build()


def changes(settings: Settings, typed: Mapping[tuple[str, ...], object]) -> Changes:
    changed: Changes = {}
    for path, value in typed.items():
        if env_key(path) in os.environ:
            continue
        stored = _stored(settings, path)
        if isinstance(stored, SecretStr):
            # The box starts blank, so only a typed key is a change.
            if isinstance(value, str) and value:
                changed[path] = value
        elif value != stored:
            changed[path] = None if value is None else _text(value)
    return changed


def refusal_text(error: ValidationError) -> str:
    return "\n".join(
        f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
        for issue in error.errors()
    )


def _shown(model: BaseModel) -> list[tuple[str, FieldInfo, object]]:
    """A directory is left out (repointing one hides the save library); a tuple has no widget."""
    return [
        (n, f, getattr(model, n))
        for n, f in type(model).model_fields.items()
        if not isinstance(getattr(model, n), Path | tuple)
    ]


def _label(path: tuple[str, ...]) -> str:
    spelled = path[-1].replace("_", " ")
    if env_key(path) in os.environ:
        return f"{spelled} — set in your shell, which wins"
    return spelled


def _widget(label: str, field: FieldInfo, value: object) -> Widget:
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
