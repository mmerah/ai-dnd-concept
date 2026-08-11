from collections.abc import Callable

from nicegui import ui

from aidm.app.session import GameSession
from aidm.state.effects import SheetDelta
from aidm.state.sheet import AdvancementOffer
from aidm.ui.busy import refuse_if_busy, working


def advancement_panel(session: GameSession, refresh: Callable[[], None]) -> None:
    """One panel for every engine; nothing is committed until the player confirms the draft."""
    offer = session.offer()
    if offer is None:
        ui.label("No advancement is on offer.").classes("opacity-70")
        return
    _summary(session, offer)
    if session.drafted is None:
        _intent_form(session, refresh)
    else:
        _review(session, session.drafted, refresh)


def _summary(session: GameSession, offer: AdvancementOffer) -> None:
    ui.label(f"{session.state.player.name} — advancement ready").classes("text-sm font-bold")
    ui.label(offer.prompt).classes("text-sm")
    if offer.text:
        ui.label(offer.text).classes("text-sm opacity-70 whitespace-pre-wrap")
    if offer.options:
        ui.label(f"Pick exactly {offer.choose} of:").classes("text-sm opacity-70 mt-2")
        for option in offer.options:
            ui.label(f"- {option}").classes("text-sm opacity-70")


def _intent_form(session: GameSession, refresh: Callable[[], None]) -> None:
    box = ui.textarea("How do you want to grow?").classes("w-full mt-3").props("outlined")

    async def propose() -> None:
        intent = (box.value or "").strip()
        if not intent:
            ui.notify("Say how you want to grow first.", type="warning")
            return
        # Checked at click time: a turn may have started after the panel rendered.
        if refuse_if_busy(session):
            return
        async with working(session):
            session.drafted = await session.propose(intent)
        refresh()

    ui.button("Propose", on_click=propose).props("color=primary")


def _review(session: GameSession, drafted: SheetDelta, refresh: Callable[[], None]) -> None:
    ui.label("Proposed changes").classes("text-sm font-bold mt-3")
    try:
        lines = [f"- {fact.trace}" for fact in session.preview(drafted)]
    except ValueError as stale:
        # A turn since the proposal may have changed the sheet from under the draft.
        lines = [f"This proposal no longer applies: {stale}. Discard it and propose again."]
    for line in lines:
        ui.label(line).classes("text-sm whitespace-pre-wrap")

    def discard() -> None:
        session.drafted = None
        refresh()

    def confirm() -> None:
        if refuse_if_busy(session):
            return
        try:
            _ = session.apply_proposal(drafted)
        except ValueError as error:
            ui.notify(str(error), type="negative", multi_line=True)
            return
        session.drafted = None
        refresh()

    with ui.row().classes("w-full mt-3").style("gap: 0.75rem"):
        ui.button("Discard", on_click=discard).props("flat")
        ui.button("Confirm advancement", on_click=confirm).props("color=primary")
