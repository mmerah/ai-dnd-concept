"""Speech: lines read one by one as they land, a stop button, a read-from-here button per line.

Needs `qa/serve.sh --speech`; `run_all.sh` starts the server that way for this scenario.
"""

import sys
import time
from pathlib import Path

from playwright.sync_api import Locator, Page

sys.path.insert(0, str(Path(__file__).parent))
from drive import BASE, Session, run, submit, wait_idle

GAME = BASE + "/game/whispering-vault/kael"
STOP = 'button[aria-label="Stop reading"]'
READ = 'button[aria-label="Read from here"]'


def playing(page: Page) -> str:
    """The clip's file name while a line is read; empty otherwise."""
    return page.evaluate(
        "() => { const a = document.querySelector('audio');"
        " return a && !a.paused ? a.src.split('/').pop() : ''; }"
    )


def icons(page: Page) -> list[str]:
    return [button.locator("i").inner_text() for button in page.locator(READ).all()]


def watch(page: Page, seconds: float) -> list[str]:
    """Each clip read in turn, in order, without repeats."""
    heard: list[str] = []
    deadline = time.time() + seconds
    while time.time() < deadline:
        clip = playing(page)
        if clip and (not heard or heard[-1] != clip):
            heard.append(clip)
        page.wait_for_timeout(100)
    return heard


def reads(page: Page) -> Locator:
    return page.locator(READ)


def body(s: Session) -> None:
    page = s.page()
    page.goto(GAME)
    wait_idle(page)
    heard = watch(page, 6)
    s.note(f"opening read: {heard}")
    s.check(len(heard) == 2, f"the opening's two lines were not read in turn: {heard}")
    s.check(
        page.locator(STOP).count() == 0 or not page.locator(STOP).is_visible(),
        "stop button shown with nothing being read",
    )
    s.check(
        icons(page) == ["play_arrow", "play_arrow"],
        f"read buttons after the opening: {icons(page)}",
    )

    # A turn with three lines: the first plays while the others still generate.
    submit(page, 'I search the desk. [say mara "Careful, there."]')
    started = time.time()
    first = ""
    while time.time() - started < 12 and not first:
        first = playing(page)
        page.wait_for_timeout(100)
    s.check(bool(first), "no line was read after the turn")
    s.check(
        reads(page).count() < 5,
        f"all lines had landed before the first was read: {reads(page).count()}",
    )
    s.check(page.locator(STOP).is_visible(), "stop button hidden while a line is read")
    s.check("stop" in icons(page), f"no line marked as being read: {icons(page)}")
    s.shot(page, "reading")
    heard = [first, *watch(page, 8)]
    heard = [clip for index, clip in enumerate(heard) if index == 0 or clip != heard[index - 1]]
    s.note(f"turn read: {heard}")
    s.check(len(heard) == 3, f"the turn's three lines were not read in turn: {heard}")
    wait_idle(page)
    s.check(reads(page).count() == 5, f"read buttons after the turn: {reads(page).count()}")

    # Stop from the header, then from the line's own button.
    reads(page).first.click()
    page.wait_for_timeout(400)
    s.check(bool(playing(page)), "the first line's button did not start it")
    s.check(icons(page)[0] == "stop", f"the line read does not show stop: {icons(page)}")
    s.shot(page, "read-from-first")
    page.locator(STOP).click()
    page.wait_for_timeout(400)
    s.check(not playing(page), "the header stop did not stop the reading")
    s.check(not page.locator(STOP).is_visible(), "stop button still shown after stopping")
    reads(page).nth(3).click()
    page.wait_for_timeout(400)
    s.check(icons(page)[3] == "stop", f"read from the fourth line: {icons(page)}")
    reads(page).nth(3).click()
    page.wait_for_timeout(400)
    s.check(not playing(page), "the line's own button did not stop it")

    # Reading from a line goes on to the lines after it, then ends.
    reads(page).nth(3).click()
    heard = watch(page, 5)
    s.check(len(heard) == 2 and not playing(page), f"reading from the fourth line: {heard}")

    # A reload never reads a cached clip; a restart reads the new opening.
    page.reload()
    wait_idle(page)
    s.check(watch(page, 4) == [], "a cached clip was read on a page load")
    page.locator('button:has(i:text("more_vert"))').click()
    page.get_by_text("Restart this game").click()
    page.get_by_role("button", name="Restart", exact=True).click()
    heard = watch(page, 8)
    s.note(f"opening read after restart: {heard}")
    s.check(len(heard) == 2, f"the opening was not read after a restart: {heard}")


run("speech", body)
