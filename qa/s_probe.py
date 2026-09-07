"""Smaller probes: markdown and long words in prose, focus across the creation form's
refresh, a failed hire's card, and the composer after a reload mid-turn."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from drive import (
    BASE,
    Session,
    bubbles,
    cards,
    clean,
    composer,
    drawer_text,
    open_drawer,
    run,
    submit,
    wait_idle,
)


def body(s: Session) -> None:
    page = s.page()
    page.goto(BASE + "/game/buried-keep/kael")
    wait_idle(page, timeout=40)

    # 1. Prose with markdown and html: the chat shows it verbatim, the journal renders markdown.
    submit(page, "I say **bold** and *soft* and <b>tag</b> and <script>alert(1)</script>.\n!none")
    wait_idle(page)
    chat = bubbles(page)[-2]
    s.note(f"chat bubble: {chat!r}")
    s.check("**bold**" in chat and "<b>tag</b>" in chat, "chat did not show the text verbatim")
    open_drawer(page)
    page.get_by_role("tab", name="journal").click()
    page.wait_for_timeout(400)
    page.locator(".q-expansion-item").first.click()
    page.wait_for_timeout(400)
    s.shot(page, "journal-markdown")
    journal_html = page.locator(".q-expansion-item").first.inner_html()
    s.note(
        f"journal html sample: {journal_html[journal_html.find('bold') - 60 : journal_html.find('bold') + 60]!r}"  # noqa: E501
    )
    s.check(
        "<strong>bold</strong>" not in journal_html,
        "the journal renders the narrator's text as markdown",
    )
    s.check("<script>" not in journal_html, "the journal lets script tags through")
    page.get_by_role("tab", name="scene").click()

    # 2. A long unbroken word: the bubble must not overflow the page.
    long_word = "x" * 300
    submit(page, f"I shout {long_word}.\n!none")
    wait_idle(page)
    s.shot(page, "long-word")
    s.check(
        page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"),
        "a long word makes the page scroll sideways",
    )
    overflow = page.evaluate(
        "Array.from(document.querySelectorAll('.q-message-text-content')).some(e => e.scrollWidth > e.clientWidth + 2)"  # noqa: E501
    )
    s.check(not overflow, "a long word overflows its bubble")

    # 3. A failed hire: what card does the player read?
    submit(page, 'I hire Grix.\n!fail worldsmith\n!hire entity_id=grix terms="Carry the torch"')
    wait_idle(page, timeout=40)
    s.shot(page, "hire-failed")
    s.note(f"cards after a failed hire: {cards(page)[-2:]}")
    s.check(
        "Grix" in cards(page)[-1],
        f"the failed-hire card does not name the hire: {cards(page)[-1]!r}",
    )
    s.check("Party" not in clean(drawer_text(page)), "a failed hire still joined the party")

    # 4. The composer after a reload mid-turn: the sent words stay in the box.
    submit(page, "I look about slowly.\n!slow narrator\n!none")
    page.wait_for_timeout(1500)
    page.reload()
    page.wait_for_timeout(1500)
    s.check(composer(page).is_disabled(), "composer open mid-turn after a reload")
    wait_idle(page, timeout=60)
    s.shot(page, "after-reload-turn")
    s.check(
        composer(page).input_value() == "",
        f"the sent prompt stayed in the composer after a reload: {composer(page).input_value()!r}",
    )

    # 5. Creation form: does Tab keep focus when a blur re-renders the form?
    page.goto(BASE + "/create")
    page.wait_for_timeout(800)
    page.locator(".q-select:has(.q-field__label:text-is('Rules'))").click()
    page.locator(".q-menu .q-item", has_text="TUNNEL GOONS").first.click()
    page.wait_for_timeout(400)
    first = page.locator(".q-field:has(.q-field__label:text-is('Item 1')) input")
    first.click()
    first.type("Torch")
    page.keyboard.press("Tab")
    page.wait_for_timeout(800)
    focused = page.evaluate(
        "document.activeElement && document.activeElement.getAttribute('aria-label')"
    )
    s.note(f"focused after Tab from Item 1: {focused!r}")
    s.check(focused == "Item 2", f"Tab from Item 1 lost the focus: {focused!r}")
    s.check(first.input_value() == "Torch", "the typed item was lost on the re-render")
    s.shot(page, "create-focus")


run("probe", body)
