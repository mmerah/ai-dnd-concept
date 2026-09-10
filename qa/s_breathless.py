"""The Drowned Road (Breathless): the loot decision, answered."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from drive import BASE, Session, cards, clean, drawer_text, open_drawer, run, submit, wait_idle

GAME = BASE + "/game/drowned-road/kael"


def body(s: Session) -> None:
    page = s.page()
    page.goto(GAME)
    wait_idle(page)

    # Loot until something is found: an option-only decision.
    found = False
    for attempt in range(4):
        submit(page, f'I scavenge for a flare ({attempt}).\n!loot_check item="Flare gun"')
        page.wait_for_timeout(3500)
        if "the game is waiting on you" in clean(page.inner_text("body")):
            found = True
            break
        wait_idle(page)
    s.check(found, "no loot decision after four scavenges")
    if found:
        page.locator(".game-decision button", has_text="Take it").click()
        page.wait_for_timeout(4000)
        wait_idle(page)
        s.check("Took Flare gun" in " ".join(cards(page)), f"take card missing: {cards(page)[-3:]}")
        s.check("Flare gun" in clean(drawer_text(page)), "backpack panel missing the find")
    open_drawer(page)
    s.shot(page, "loot-taken")


run("breathless", body)
