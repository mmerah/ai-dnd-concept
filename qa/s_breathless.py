"""The Drowned Road (Breathless): loot decisions, breath, stunts, stress, hire."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from drive import (
    BASE,
    Session,
    cards,
    clean,
    composer,
    drawer_text,
    log,
    placeholder,
    run,
    submit,
    wait_idle,
)

GAME = BASE + "/game/drowned-road/kael"


def decision_open(page) -> bool:  # noqa: ANN001
    return "the game is waiting on you" in clean(page.inner_text("body"))


def body(s: Session) -> None:
    page = s.page()
    page.goto(GAME)
    wait_idle(page)
    s.shot(page, "opened")
    side = clean(drawer_text(page))
    s.check("backpack" in side.lower() and "Loot die d12" in side, f"sheet panels: {side[:400]}")

    # 1. Loot until something is found: an option-only decision.
    found = False
    for attempt in range(4):
        submit(page, f'I scavenge for a flare ({attempt}).\n!loot_check item="Flare gun"')
        page.wait_for_timeout(3500)
        if decision_open(page):
            found = True
            break
        wait_idle(page)
    s.shot(page, "loot-found")
    s.check(found, "no loot decision after four scavenges")
    if found:
        s.check(composer(page).is_disabled(), "composer open on the loot decision")
        s.check(
            placeholder(page) == "Choose an option above.", f"placeholder: {placeholder(page)!r}"
        )
        labels = [clean(t) for t in page.locator(".game-decision button").all_inner_texts()]
        s.note(f"loot options: {labels}")
        page.locator(".game-decision button", has_text="Take it").click()
        page.wait_for_timeout(4000)
        wait_idle(page)
        s.check("Took Flare gun" in " ".join(cards(page)), f"take card missing: {cards(page)[-3:]}")
        s.check("Flare gun" in clean(drawer_text(page)), "backpack panel missing the find")
        s.shot(page, "loot-taken")

    # 2. Catch breath: dice reset, a complication is noted to the master.
    submit(page, "I catch my breath.\n!catch_breath")
    wait_idle(page)
    s.check("Caught breath" in " ".join(cards(page)), f"breath card missing: {cards(page)[-2:]}")
    s.check("Loot die d12" in clean(drawer_text(page)), "loot die not reset")
    master = [e for e in log() if e["role"] == "master"]
    submit(page, "I look at the water.\n!none")
    wait_idle(page)
    master = [e for e in log() if e["role"] == "master"]
    s.check(
        "Catching breath brings a new complication" in master[-1]["prompt"],
        "the complication note did not reach the next master",
    )

    # 3. A stunt, then a second stunt is refused.
    submit(
        page,
        'I leap the gap.\n!roll what="Leap the gap" stunt=true\n!roll what="Leap again" stunt=true',
    )
    wait_idle(page)
    last = [e for e in log() if e["role"] == "master"][-1]
    s.check(
        any("stunt is spent" in c[2] for c in last["calls"]),
        f"second stunt not refused: {last['calls']}",
    )
    s.check("Stunt spent" in clean(drawer_text(page)), "stunt not shown spent on the sheet")

    # 4. Stress to vulnerable, a dangerous fail notes the master.
    submit(page, 'The bell rings.\n!change verb=change_stress amount=4 why="the bell"')
    wait_idle(page)
    s.check("vulnerable" in clean(drawer_text(page)), "vulnerable not shown")
    s.shot(page, "vulnerable")

    # 5. Hire: the worldsmith writes a sheet; the member joins.
    submit(page, 'I hire Ovid.\n!hire entity_id=ovid-sarn terms="Guide me through the flats"')
    wait_idle(page, timeout=40)
    s.shot(page, "hired")
    side = clean(drawer_text(page))
    s.check(
        "party" in side.lower() and "Ovid Sarn" in side and "Nurse" in side,
        f"party panel: {side[:600]}",
    )
    # A helped roll.
    submit(
        page,
        'We push the cart together.\n!roll what="Push the cart" skill=bash helped_by=ovid-sarn',
    )
    wait_idle(page)
    s.check("helped by Ovid Sarn" in " ".join(cards(page)), f"helped roll card: {cards(page)[-2:]}")

    # 6. An item roll wearing to d4 makes the item go.
    for _ in range(3):
        submit(page, 'I swing the bat.\n!roll what="Swing" item_id=pry-bar')
        wait_idle(page)
    s.note(f"item cards: {[c for c in cards(page) if 'gone' in c or 'Pry' in c][-3:]}")

    # 7. Reveal hidden Marta, then the player dies.
    submit(page, "Marta rises.\n!change verb=reveal entity_id=drowned-marta")
    wait_idle(page)
    submit(page, "She takes me.\n!change verb=kill entity_id=player")
    page.wait_for_timeout(4000)
    s.shot(page, "dead")
    s.check("You died." in clean(page.inner_text("body")), "over label missing")
    s.check(composer(page).is_disabled(), "composer open after death")


run("breathless", body)
