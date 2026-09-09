"""The Silent Relay (24XX): jobs, hire, defend, succession."""

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
    log,
    run,
    submit,
    wait_idle,
)

GAME = BASE + "/game/silent-relay/kael"


def body(s: Session) -> None:
    page = s.page()
    page.goto(GAME)
    wait_idle(page)
    s.shot(page, "opened")
    side = clean(drawer_text(page))
    s.check("ship" in side.lower() and "Hull armor" in side, f"ship panel: {side[:500]}")
    s.check("Credits ₡2" in side, "credits missing")

    submit(page, 'I ask around.\n!job verb=find where="the docking ring"')
    wait_idle(page)
    s.check("the docking ring — d6" in " ".join(cards(page)), f"find card: {cards(page)[-2:]}")
    submit(page, 'I take the job.\n!job verb=take terms="Fix the relay for 20 credits"')
    wait_idle(page)
    s.check("job fix the relay" in clean(drawer_text(page)).lower(), "job panel missing")
    s.shot(page, "job")
    submit(page, 'I hire Vessa.\n!hire entity_id=vessa-rune terms="Fly us out"')
    wait_idle(page, timeout=40)
    side = clean(drawer_text(page))
    s.check(
        "party" in side.lower() and "Vessa Rune" in side and "Medic" in side,
        f"party panel: {side[:600]}",
    )
    s.shot(page, "hired")
    submit(
        page,
        'Done.\n!job verb=finish raises=\'[{"actor_id":null,"skill":"Climbing"},{"actor_id":"vessa-rune","skill":"Medicine"}]\'',  # noqa: E501
    )
    wait_idle(page)
    last = [e for e in log() if e["role"] == "master"][-1]
    s.note(f"finish: {last['calls'][-1][2][:200]}")
    joined = " ".join(cards(page))
    s.check("Job done" in joined and "+₡" in joined, f"finish cards: {cards(page)[-4:]}")
    s.check("job fix" not in clean(drawer_text(page)).lower(), "job panel stayed after finish")
    s.shot(page, "finished")
    submit(
        page,
        'The hull takes it.\n!change verb=defend item_id=hull-armor\n!change verb=gain_item name="Coil of rope" cost=1\n!change verb=change_hindrances gained=\'["Bruised"]\'',  # noqa: E501
    )
    wait_idle(page)
    joined = " ".join(cards(page))
    s.check(
        "Hull armor breaks" in joined
        and "Gained Coil of rope" in joined
        and "Hindered: Bruised" in joined,
        f"change cards: {cards(page)[-4:]}",
    )
    side = clean(drawer_text(page))
    s.check("broken" in side and "Bruised" in side, f"sheet after changes: {side[:600]}")
    s.shot(page, "changed")

    # Death with a hired member alive: succession, not an ending.
    submit(page, "The warden fires.\n!change verb=kill entity_id=player")
    page.wait_for_timeout(4000)
    s.shot(page, "succession")
    text = clean(page.inner_text("body"))
    s.check("Who leads now?" in text, "succession decision missing")
    s.check("You died." not in text, "the game ended although a member could lead")
    s.check(composer(page).is_disabled(), "composer open on the succession decision")
    page.locator(".game-decision button", has_text="Vessa Rune").click()
    page.wait_for_timeout(4000)
    wait_idle(page)
    s.shot(page, "new-lead")
    s.check("Vessa Rune leads now" in " ".join(cards(page)), f"lead card: {cards(page)[-3:]}")
    side = clean(drawer_text(page))
    sheet = side.split("SHIP")[0]  # the character card, before the panel that follows it
    s.check("Vessa Rune" in sheet, f"the new lead does not head the drawer: {side[:400]}")
    s.check("Medic" in sheet, "the sheet is not the new lead's")
    submit(page, "I take stock.")
    wait_idle(page)
    s.check(
        "Vessa Rune" in clean(page.inner_text(".game-transcript"))[-600:],
        "the new lead's bubble is not named after her",
    )
    s.note(f"last bubbles: {bubbles(page)[-3:]}")


run("24xx", body)
