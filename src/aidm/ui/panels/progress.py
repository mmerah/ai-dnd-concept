from nicegui import ui

from ...content.records.character import ProgressionChoice
from ...domain.models.progression import MAX_LEVEL, Decisions
from ...engine import features
from ...engine.features import OwnedFeature
from ...engine.progression import AdvancementPlan, LevelBenefits, LevelUpPreview
from ...engine.ruleset import FeatureProfile
from ..session import Session
from .state import state_panel


@ui.refreshable
def progress_panel(session: Session) -> None:
    player = session.app.state.player
    current = player.progression
    if current is None:
        ui.label("This character has no class, so there is nothing to advance.")
        return
    ui.label(f"{player.name} — level {current.level}").classes("text-sm font-bold")
    if current.level >= MAX_LEVEL:
        ui.label(f"Level {MAX_LEVEL} is the last.").classes("opacity-60")
        _owned_features(session)
        return
    if not current.level_up_available:
        ui.label("No level-up has been awarded yet. Keep playing.").classes("opacity-60")
        _owned_features(session)
        return

    try:
        preview = session.app.level_up_preview()
    except ValueError as exc:
        ui.label(f"Cannot read level {current.level + 1}: {exc}").classes("text-negative")
        return
    _level_up(session, preview)
    ui.separator().classes("q-my-md")
    _owned_features(session)


def _level_up(session: Session, preview: LevelUpPreview) -> None:
    benefits = preview.benefits
    ui.label(f"Level {benefits.level} preview").classes("text-h6 q-mt-md")
    ui.label("Review the automatic benefits, then make every required choice.").classes(
        "text-sm opacity-70"
    )
    _automatic_gains(benefits)
    picks = _choices(preview.choices)
    ui.button(
        f"Review and confirm level {benefits.level}",
        on_click=lambda: _review(session, picks),
    ).classes("q-mt-md").props("color=primary")


def _automatic_gains(benefits: LevelBenefits) -> None:
    ui.label("Automatic gains").classes("text-sm font-bold q-mt-md")
    with ui.card().classes("w-full"):
        ui.label("Hit points").classes("font-bold")
        ui.label(
            f"Roll 1d{benefits.hit_die} + Constitution modifier after choices (minimum 1)."
        ).classes("text-sm")
        if benefits.retroactive_hp_gain:
            ui.label(
                f"Constitution increase adds {benefits.retroactive_hp_gain} HP for earlier levels."
            ).classes("text-sm")
        if benefits.prof_bonus_after > benefits.prof_bonus_before:
            ui.label(
                f"Proficiency bonus increases from +{benefits.prof_bonus_before} "
                f"to +{benefits.prof_bonus_after}."
            ).classes("text-sm")
        for slots in benefits.spell_slot_changes:
            ui.label(
                f"Level {slots.spell_level} spell slots: {slots.before} → {slots.after}."
            ).classes("text-sm")
    ui.label("New features").classes("text-sm font-bold q-mt-md")
    if not benefits.features:
        ui.label("No new class or subclass features at this level.").classes("text-sm opacity-60")
        return
    with ui.column().classes("w-full").style("gap: 0.75rem"):
        for profile in benefits.features:
            _feature_card(profile)


def _choices(choices: tuple[ProgressionChoice, ...]) -> dict[str, list[ui.select]]:
    ui.label("Choices").classes("text-sm font-bold q-mt-md")
    if not choices:
        ui.label("No decisions are required at this level.").classes("text-sm opacity-60")
        return {}
    picks: dict[str, list[ui.select]] = {}
    with ui.column().classes("w-full").style("gap: 0.75rem"):
        for choice in choices:
            with ui.card().classes("w-full"):
                ui.label(choice.prompt.capitalize()).classes("font-bold")
                ui.label(
                    f"Choose {choice.choose}"
                    + (" different options." if choice.distinct else " options.")
                ).classes("text-xs opacity-60")
                picks[choice.id] = _selects(choice)
    return picks


def _owned_features(session: Session) -> None:
    ui.label("Current class features").classes("text-sm font-bold q-mt-md")
    with ui.column().classes("w-full").style("gap: 0.75rem"):
        for status in session.app.owned_features():
            _feature_card(status.profile, _uses(status))


def _uses(status: OwnedFeature) -> str:
    pool = status.pool
    if pool is None:
        return ""
    return f"{pool.remaining}/{pool.maximum} uses — recharges on a {pool.recharge} rest"


def _feature_card(profile: FeatureProfile, uses: str = "") -> None:
    with ui.card().classes("w-full"):
        ui.label(profile.name).classes("font-bold")
        ui.label(features.actionability(profile)).classes("text-xs opacity-60")
        if uses:
            ui.label(uses).classes("text-xs opacity-60")
        ui.label(profile.desc).classes("text-sm whitespace-pre-line")


def _selects(choice: ProgressionChoice) -> list[ui.select]:
    """Use separate selects because a choice may repeat an option."""
    return [
        ui.select(
            options={option.key: option.label for option in choice.options},
            label=f"{choice.prompt} ({n + 1} of {choice.choose})",
        ).classes("w-full")
        for n in range(choice.choose)
    ]


def _review(session: Session, picks: dict[str, list[ui.select]]) -> None:
    if any(select.value is None for selects in picks.values() for select in selects):
        ui.notify("Choose every required option before confirming.", type="warning")
        return
    decisions = {id: tuple(str(s.value) for s in selects) for id, selects in picks.items()}
    try:
        plan = session.app.level_up_plan(decisions)
    except ValueError as exc:
        ui.notify(str(exc), type="negative", multi_line=True)
        return
    _confirmation(session, plan, decisions)


def _confirmation(session: Session, plan: AdvancementPlan, decisions: Decisions) -> None:
    with (
        ui.dialog() as dialog,
        ui.card().style(
            "height: 85vh; width: min(48rem, 95vw); display: flex; flex-direction: column;"
        ),
    ):
        ui.label(f"Confirm level {plan.benefits.level}").classes("text-h6")
        with ui.scroll_area().style("flex: 1; min-height: 0;"):
            _automatic_gains(plan.benefits)
            if plan.selections:
                ui.label("Your choices").classes("text-sm font-bold q-mt-md")
                with ui.column().classes("w-full").style("gap: 0.5rem"):
                    for selection in plan.selections:
                        ui.label(
                            f"{selection.prompt.capitalize()}: {', '.join(selection.labels)}"
                        ).classes("text-sm")
        with ui.element("div").style(
            "position: sticky; bottom: 0; padding-top: 1rem; "
            "border-top: 1px solid var(--q-dark-page);"
        ):
            with ui.row().classes("w-full justify-end").style("gap: 0.75rem"):
                ui.button("Back", on_click=dialog.close).props("flat")
                ui.button(
                    f"Confirm level {plan.benefits.level}",
                    on_click=lambda: _advance(session, decisions, dialog),
                ).props("color=primary")
    dialog.open()


def _advance(session: Session, decisions: Decisions, dialog: ui.dialog) -> None:
    if session.busy:
        ui.notify("Finish the current turn before confirming the level-up.", type="warning")
        return
    try:
        session.app.advance(decisions)
    except ValueError as exc:
        ui.notify(str(exc), type="negative", multi_line=True)
        return
    dialog.close()
    progress_panel.refresh()
    state_panel.refresh()
