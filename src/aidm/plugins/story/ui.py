from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal

from nicegui import ui

from aidm.kernel.engine import AdvancementSubmit, CurrentState, entered_text

from .advancement import (
    AcquireGear,
    AddTag,
    IncreaseMaximumStress,
    RaiseApproach,
    RemoveBurden,
    RewriteBurden,
    StoryAdvancementDecision,
    available,
    burdens,
    describe_choice,
    dump_decision,
    raisable_approaches,
    stress_raisable,
    validate_choice,
)
from .state import (
    GROWTH_REQUIRED,
    StoryActorState,
    StoryActorTag,
    StoryApproach,
    StoryGearTag,
    player_state,
)

_TAG_KINDS: dict[str, Literal["edge", "bond"]] = {"edge": "edge", "bond": "bond"}


@dataclass(frozen=True, slots=True)
class _Ctx:
    state: CurrentState
    submit: AdvancementSubmit
    refresh: Callable[[], None]


def advancement_panel(
    state: CurrentState,
    submit: AdvancementSubmit,
    refresh: Callable[[], None],
) -> None:
    current = state()
    player = player_state(current)
    ready = available(current)
    headline = "Story growth ready" if ready else "Story growth"
    ui.label(f"{current.player.name} — {headline}").classes("text-sm font-bold")
    ui.linear_progress(value=player.growth_marks / GROWTH_REQUIRED, show_value=False).classes(
        "w-full"
    )
    ui.label(f"{player.growth_marks} of {GROWTH_REQUIRED} growth marks.").classes(
        "text-sm opacity-70"
    )
    if not ready:
        ui.label("A setback on a player risk earns growth.").classes("text-sm opacity-70")
        return

    ctx = _Ctx(state=state, submit=submit, refresh=refresh)
    ui.label("Choose one advancement").classes("text-h6 q-mt-md")
    with ui.column().classes("w-full").style("gap: 0.75rem"):
        _approach_card(ctx, player)
        _add_tag_card(ctx)
        active_burdens = burdens(player)
        if active_burdens:
            _remove_burden_card(ctx, active_burdens)
            _rewrite_burden_card(ctx, active_burdens)
        _acquire_gear_card(ctx)
        if stress_raisable(player):
            _stress_card(ctx)


@contextmanager
def _card(heading: str) -> Generator[None]:
    with ui.card().classes("w-full"):
        ui.label(heading).classes("font-bold")
        yield


def _offer(
    label: str,
    ctx: _Ctx,
    build: Callable[[], StoryAdvancementDecision | None],
) -> None:
    ui.button(label, on_click=lambda: _review(ctx, build)).props("color=primary")


def _approach_card(ctx: _Ctx, player: StoryActorState) -> None:
    options = raisable_approaches(player)
    if not options:
        return
    approach_by_key: dict[str, StoryApproach] = {name: name for name, _ in options}
    with _card("Raise an approach"):
        approach = ui.select(
            {name: f"{name.capitalize()} ({score:+d} → {score + 1:+d})" for name, score in options},
            label="Approach",
        ).classes("w-full")

        def build() -> StoryAdvancementDecision | None:
            key = entered_text(approach.value)
            chosen = approach_by_key.get(key) if key is not None else None
            return None if chosen is None else RaiseApproach(approach=chosen)

        _offer("Review approach increase", ctx, build)


def _add_tag_card(ctx: _Ctx) -> None:
    with _card("Add an edge or bond"):
        id_input = ui.input("Id (lowercase words joined by hyphens)").classes("w-full")
        name_input = ui.input("Name").classes("w-full")
        kind_select = ui.select(
            {kind: kind.capitalize() for kind in _TAG_KINDS}, label="Kind"
        ).classes("w-full")
        description_input = ui.input("Description").classes("w-full")

        def build() -> StoryAdvancementDecision | None:
            tag_id = entered_text(id_input.value)
            name = entered_text(name_input.value)
            kind_key = entered_text(kind_select.value)
            kind = _TAG_KINDS.get(kind_key) if kind_key is not None else None
            description = entered_text(description_input.value)
            if tag_id is None or name is None or kind is None or description is None:
                return None
            return AddTag(id=tag_id, name=name, kind=kind, description=description)

        _offer("Review new tag", ctx, build)


def _remove_burden_card(ctx: _Ctx, active_burdens: tuple[StoryActorTag, ...]) -> None:
    with _card("Remove a burden"):
        burden_select = ui.select(
            {tag.id: tag.name for tag in active_burdens}, label="Burden"
        ).classes("w-full")

        def build() -> StoryAdvancementDecision | None:
            tag_id = entered_text(burden_select.value)
            return None if tag_id is None else RemoveBurden(id=tag_id)

        _offer("Review removing burden", ctx, build)


def _rewrite_burden_card(ctx: _Ctx, active_burdens: tuple[StoryActorTag, ...]) -> None:
    with _card("Rewrite a burden"):
        burden_select = ui.select(
            {tag.id: tag.name for tag in active_burdens}, label="Burden"
        ).classes("w-full")
        name_input = ui.input("Rewritten name").classes("w-full")
        description_input = ui.input("Rewritten description").classes("w-full")

        def build() -> StoryAdvancementDecision | None:
            tag_id = entered_text(burden_select.value)
            name = entered_text(name_input.value)
            description = entered_text(description_input.value)
            if tag_id is None or name is None or description is None:
                return None
            return RewriteBurden(id=tag_id, name=name, description=description)

        _offer("Review rewritten burden", ctx, build)


def _acquire_gear_card(ctx: _Ctx) -> None:
    with _card("Acquire Story gear"):
        item_name_input = ui.input("Item name").classes("w-full")
        item_brief_input = ui.input("Item brief").classes("w-full")
        gear_name_input = ui.input("Gear benefit name").classes("w-full")
        gear_description_input = ui.input("Gear benefit description").classes("w-full")

        def build() -> StoryAdvancementDecision | None:
            item_name = entered_text(item_name_input.value)
            item_brief = entered_text(item_brief_input.value)
            gear_name = entered_text(gear_name_input.value)
            gear_description = entered_text(gear_description_input.value)
            if (
                item_name is None
                or item_brief is None
                or gear_name is None
                or gear_description is None
            ):
                return None
            return AcquireGear(
                item_name=item_name,
                item_brief=item_brief,
                gear=StoryGearTag(name=gear_name, description=gear_description),
            )

        _offer("Review new gear", ctx, build)


def _stress_card(ctx: _Ctx) -> None:
    with _card("Increase maximum stress"):
        _offer("Review resilience increase", ctx, IncreaseMaximumStress)


def _review(ctx: _Ctx, build: Callable[[], StoryAdvancementDecision | None]) -> None:
    player = player_state(ctx.state())
    try:
        decision = build()
        if decision is None:
            ui.notify("Complete every field first.", type="warning")
            return
        validate_choice(player, decision)
    except ValueError as error:
        ui.notify(str(error), type="negative", multi_line=True)
        return
    _confirm(ctx, player, decision)


def _confirm(ctx: _Ctx, player: StoryActorState, decision: StoryAdvancementDecision) -> None:
    with ui.dialog() as dialog, ui.card():
        ui.label("Confirm Story advancement").classes("text-h6")
        ui.label(describe_choice(player, decision))
        with ui.row().classes("w-full justify-end").style("gap: 0.75rem"):
            ui.button("Back", on_click=dialog.close).props("flat")
            ui.button(
                "Confirm advancement",
                on_click=lambda: _commit(ctx, decision, dialog),
            ).props("color=primary")
    dialog.open()


def _commit(ctx: _Ctx, decision: StoryAdvancementDecision, dialog: ui.dialog) -> None:
    if ctx.submit(dump_decision(decision)):
        dialog.close()
        ctx.refresh()
