from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui

from aidm_5e.advancement import Dnd5eAdvancementDecisions
from aidm_5e.content.records.character import ProgressionChoice
from aidm_5e.engine.features import actionability
from aidm_5e.engine.progression import (
    AdvancementPlan,
    LevelBenefits,
)
from aidm_5e.factory import Dnd5eEngine

from ..session_model import Session
from .flow import confirm_advancement


@dataclass(frozen=True, slots=True)
class Dnd5eAdvancementUi:
    engine: Dnd5eEngine

    def render(self, session: Session, refresh: Callable[[], None]) -> None:
        status = self.engine.advancement.status(session.app.state)
        ui.label(f"{session.app.state.player.name} — {status.headline}").classes(
            "text-sm font-bold"
        )
        ui.linear_progress(value=status.progress, show_value=False).classes("w-full")
        for line in status.detail:
            ui.label(line).classes("text-sm opacity-70 whitespace-pre-line")
        if not self.engine.advancement.available(session.app.state):
            return
        try:
            preview = self.engine.advancement.preview(session.app.state)
        except ValueError as error:
            ui.label(f"Cannot read the advancement: {error}").classes("text-negative text-sm")
            return
        self._benefits(preview.benefits)
        picks = self._choices(preview.choices)
        ui.button(
            f"Review level {preview.benefits.level}",
            on_click=lambda: self._review(session, refresh, picks),
        ).classes("q-mt-md").props("color=primary")

    @staticmethod
    def _benefits(benefits: LevelBenefits) -> None:
        ui.label(f"Level {benefits.level} preview").classes("text-h6 q-mt-md")
        with ui.card().classes("w-full"):
            ui.label(f"Hit die: d{benefits.hit_die} (rolled by the engine on confirm)").classes(
                "text-sm"
            )
            if benefits.retroactive_hp_gain:
                ui.label(
                    f"Retroactive hit points from a raised constitution: "
                    f"+{benefits.retroactive_hp_gain}"
                ).classes("text-sm")
            if benefits.prof_bonus_after > benefits.prof_bonus_before:
                ui.label(
                    f"Proficiency +{benefits.prof_bonus_before} → +{benefits.prof_bonus_after}"
                ).classes("text-sm")
            for slots in benefits.spell_slot_changes:
                ui.label(f"Level {slots.slot_level} slots: {slots.before} → {slots.after}").classes(
                    "text-sm"
                )
            for feature in benefits.features:
                ui.label(f"{feature.name} — {actionability(feature)}").classes("font-bold")
                ui.label(feature.desc).classes("text-sm whitespace-pre-line")

    @staticmethod
    def _choices(choices: tuple[ProgressionChoice, ...]) -> dict[str, list[ui.select]]:
        if not choices:
            ui.label("No decisions are required.").classes("text-sm opacity-60")
            return {}
        picks: dict[str, list[ui.select]] = {}
        with ui.column().classes("w-full").style("gap: 0.75rem"):
            for choice in choices:
                with ui.card().classes("w-full"):
                    ui.label(choice.prompt.capitalize()).classes("font-bold")
                    if choice.distinct and choice.choose > 1:
                        ui.label(f"Choose {choice.choose} different options.").classes(
                            "text-xs opacity-60"
                        )
                    picks[choice.id] = [
                        ui.select(
                            options={option.key: option.label for option in choice.options},
                            label=f"{choice.prompt} ({number + 1} of {choice.choose})",
                        ).classes("w-full")
                        for number in range(choice.choose)
                    ]
        return picks

    def _review(
        self,
        session: Session,
        refresh: Callable[[], None],
        picks: dict[str, list[ui.select]],
    ) -> None:
        if any(select.value is None for selects in picks.values() for select in selects):
            ui.notify("Choose every required option.", type="warning")
            return
        decisions = Dnd5eAdvancementDecisions(
            decisions={
                choice_id: tuple(str(select.value) for select in selects)
                for choice_id, selects in picks.items()
            }
        )
        try:
            plan = self.engine.advancement.plan(session.app.state, decisions)
        except ValueError as error:
            ui.notify(str(error), type="negative", multi_line=True)
            return
        confirm_advancement(
            session,
            decisions,
            refresh,
            title=f"Confirm level {plan.benefits.level}",
            confirm_label=f"Confirm level {plan.benefits.level}",
            body=lambda: self._plan(plan),
        )

    def _plan(self, plan: AdvancementPlan) -> None:
        self._benefits(plan.benefits)
        for selection in plan.selections:
            ui.label(f"{selection.prompt.capitalize()}: {', '.join(selection.labels)}").classes(
                "text-sm"
            )
