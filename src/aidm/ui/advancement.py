from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui

from aidm.engine import AdvancementDecision
from aidm.engines.dnd5e.advancement import Dnd5eAdvancementDecisions
from aidm.engines.dnd5e.content.records.character import ProgressionChoice
from aidm.engines.dnd5e.engine import Dnd5eEngine
from aidm.engines.dnd5e.features import actionability
from aidm.engines.dnd5e.progression import AdvancementPlan, LevelBenefits
from aidm.engines.story.advancement import (
    AcquireGear,
    AddTag,
    IncreaseMaximumStress,
    RaiseApproach,
    RemoveBurden,
    RewriteBurden,
    StoryAdvancementDecision,
    StoryAdvancementPlan,
    StoryAdvancementPreview,
)
from aidm.engines.story.engine import StoryEngine
from aidm.engines.story.state import APPROACH_NAMES, StoryApproach, StoryGearTag

from .session import Session


@dataclass(frozen=True, slots=True)
class StoryAdvancementUi:
    engine: StoryEngine

    def render(self, session: Session, refresh: Callable[[], None]) -> None:
        status = self.engine.advancement.status(session.app.state)
        ui.label(f"{session.app.state.player.name} — {status.headline}").classes(
            "text-sm font-bold"
        )
        ui.linear_progress(value=status.progress, show_value=False).classes("w-full")
        for line in status.detail:
            ui.label(line).classes("text-sm opacity-70")
        if not self.engine.advancement.available(session.app.state):
            return
        try:
            preview = self.engine.advancement.preview(session.app.state)
        except ValueError as error:
            ui.label(f"Cannot read the advancement: {error}").classes("text-negative text-sm")
            return
        ui.label("Choose one advancement").classes("text-h6 q-mt-md")
        with ui.column().classes("w-full").style("gap: 0.75rem"):
            self._raise_approach(session, refresh, preview)
            self._add_tag(session, refresh)
            self._burdens(session, refresh, preview)
            self._gear(session, refresh)
            if preview.max_stress < preview.max_stress_limit:
                with ui.card().classes("w-full"):
                    ui.label("Increase maximum stress").classes("font-bold")
                    ui.button(
                        "Review resilience increase",
                        on_click=lambda: self._review(session, refresh, IncreaseMaximumStress()),
                    ).props("color=primary")

    def _raise_approach(
        self,
        session: Session,
        refresh: Callable[[], None],
        preview: StoryAdvancementPreview,
    ) -> None:
        scores = {name: preview.approaches.score(name) for name in APPROACH_NAMES}
        options = {
            name: f"{name.capitalize()} ({score:+d} → {score + 1:+d})"
            for name, score in scores.items()
            if score < preview.approach_limit
        }
        if not options:
            return
        with ui.card().classes("w-full"):
            ui.label("Raise an approach").classes("font-bold")
            selected = ui.select(options=options, label="Approach").classes("w-full")
            ui.button(
                "Review approach increase",
                on_click=lambda: self._raise_selected(session, refresh, selected.value),
            ).props("color=primary")

    def _raise_selected(
        self,
        session: Session,
        refresh: Callable[[], None],
        value: object,
    ) -> None:
        if value not in APPROACH_NAMES:
            ui.notify("Choose an approach first.", type="warning")
            return
        approach: StoryApproach = value
        self._review(session, refresh, RaiseApproach(approach=approach))

    def _add_tag(self, session: Session, refresh: Callable[[], None]) -> None:
        with ui.card().classes("w-full"):
            ui.label("Add an edge or bond").classes("font-bold")
            tag_id = ui.input(label="Id (lowercase words joined by hyphens)").classes("w-full")
            name = ui.input(label="Name").classes("w-full")
            kind = ui.select(
                options={"edge": "Edge", "bond": "Bond"},
                label="Kind",
            ).classes("w-full")
            description = ui.input(label="Description").classes("w-full")
            ui.button(
                "Review new tag",
                on_click=lambda: self._review_tag(
                    session,
                    refresh,
                    tag_id.value,
                    name.value,
                    kind.value,
                    description.value,
                ),
            ).props("color=primary")

    def _review_tag(
        self,
        session: Session,
        refresh: Callable[[], None],
        tag_id: object,
        name: object,
        kind: object,
        description: object,
    ) -> None:
        tag_id_value = _text(tag_id)
        name_value = _text(name)
        description_value = _text(description)
        if tag_id_value is None or name_value is None or description_value is None:
            ui.notify("Complete the tag fields.", type="warning")
            return
        if kind not in ("edge", "bond"):
            ui.notify("Choose edge or bond.", type="warning")
            return
        self._review(
            session,
            refresh,
            AddTag(
                id=tag_id_value,
                name=name_value,
                kind=kind,
                description=description_value,
            ),
        )

    def _burdens(
        self,
        session: Session,
        refresh: Callable[[], None],
        preview: StoryAdvancementPreview,
    ) -> None:
        burdens = {tag.id: tag.name for tag in preview.tags if tag.kind == "burden"}
        if not burdens:
            return
        with ui.card().classes("w-full"):
            ui.label("Change a burden").classes("font-bold")
            selected = ui.select(options=burdens, label="Burden").classes("w-full")
            ui.button(
                "Review removing burden",
                on_click=lambda: self._remove_burden(session, refresh, selected.value),
            )
            name = ui.input(label="Rewritten name").classes("w-full")
            description = ui.input(label="Rewritten description").classes("w-full")
            ui.button(
                "Review rewritten burden",
                on_click=lambda: self._rewrite_burden(
                    session,
                    refresh,
                    selected.value,
                    name.value,
                    description.value,
                ),
            )

    def _remove_burden(
        self,
        session: Session,
        refresh: Callable[[], None],
        tag_id: object,
    ) -> None:
        if not isinstance(tag_id, str):
            ui.notify("Choose a burden first.", type="warning")
            return
        self._review(session, refresh, RemoveBurden(id=tag_id))

    def _rewrite_burden(
        self,
        session: Session,
        refresh: Callable[[], None],
        tag_id: object,
        name: object,
        description: object,
    ) -> None:
        tag_id_value = _text(tag_id)
        name_value = _text(name)
        description_value = _text(description)
        if tag_id_value is None or name_value is None or description_value is None:
            ui.notify("Choose and complete the burden.", type="warning")
            return
        self._review(
            session,
            refresh,
            RewriteBurden(
                id=tag_id_value,
                name=name_value,
                description=description_value,
            ),
        )

    def _gear(self, session: Session, refresh: Callable[[], None]) -> None:
        with ui.card().classes("w-full"):
            ui.label("Acquire Story gear").classes("font-bold")
            item_name = ui.input(label="Item name").classes("w-full")
            item_brief = ui.input(label="Item brief").classes("w-full")
            gear_name = ui.input(label="Gear benefit name").classes("w-full")
            gear_description = ui.input(label="Gear benefit description").classes("w-full")
            ui.button(
                "Review new gear",
                on_click=lambda: self._review_gear(
                    session,
                    refresh,
                    item_name.value,
                    item_brief.value,
                    gear_name.value,
                    gear_description.value,
                ),
            ).props("color=primary")

    def _review_gear(
        self,
        session: Session,
        refresh: Callable[[], None],
        item_name: object,
        item_brief: object,
        gear_name: object,
        gear_description: object,
    ) -> None:
        item_name_value = _text(item_name)
        item_brief_value = _text(item_brief)
        gear_name_value = _text(gear_name)
        gear_description_value = _text(gear_description)
        if (
            item_name_value is None
            or item_brief_value is None
            or gear_name_value is None
            or gear_description_value is None
        ):
            ui.notify("Complete every gear field.", type="warning")
            return
        self._review(
            session,
            refresh,
            AcquireGear(
                item_name=item_name_value,
                item_brief=item_brief_value,
                gear=StoryGearTag(
                    name=gear_name_value,
                    description=gear_description_value,
                ),
            ),
        )

    def _review(
        self,
        session: Session,
        refresh: Callable[[], None],
        decision: StoryAdvancementDecision,
    ) -> None:
        try:
            plan = self.engine.advancement.plan(session.app.state, decision)
        except ValueError as error:
            ui.notify(str(error), type="negative", multi_line=True)
            return
        confirm_advancement(
            session,
            decision,
            refresh,
            title="Confirm Story advancement",
            confirm_label="Confirm advancement",
            body=lambda: self._summary(plan),
        )

    @staticmethod
    def _summary(plan: StoryAdvancementPlan) -> None:
        ui.label(plan.summary).classes("text-sm")


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


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


def confirm_advancement(
    session: Session,
    decision: AdvancementDecision,
    refresh: Callable[[], None],
    title: str,
    confirm_label: str,
    body: Callable[[], None],
) -> None:
    """Review and commit an advancement; shared by every engine's renderer."""
    with (
        ui.dialog() as dialog,
        ui.card().style(
            "height: 80vh; width: min(48rem, 95vw); display: flex; flex-direction: column;"
        ),
    ):
        ui.label(title).classes("text-h6")
        with ui.scroll_area().style("flex: 1; min-height: 0;"):
            body()
        with ui.element("div").style(
            "position: sticky; bottom: 0; padding-top: 1rem; "
            "border-top: 1px solid var(--q-dark-page);"
        ):
            with ui.row().classes("w-full justify-end").style("gap: 0.75rem"):
                ui.button("Back", on_click=dialog.close).props("flat")
                ui.button(
                    confirm_label,
                    on_click=lambda: _commit(session, decision, dialog, refresh),
                ).props("color=primary")
    dialog.open()


def _commit(
    session: Session,
    decision: AdvancementDecision,
    dialog: ui.dialog,
    refresh: Callable[[], None],
) -> None:
    if session.busy:
        ui.notify("Finish the current turn first.", type="warning")
        return
    try:
        _ = session.app.advance(decision)
    except (TypeError, ValueError) as error:
        ui.notify(str(error), type="negative", multi_line=True)
        return
    dialog.close()
    refresh()
