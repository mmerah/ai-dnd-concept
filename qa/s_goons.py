"""The Buried Keep (Tunnel Goons): map, fights, hire, interjection, level-up, more map."""

import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import Locator, Page

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
    notifications,
    placeholder,
    run,
    send,
    submit,
    wait_idle,
)

GAME = BASE + "/game/buried-keep/kael"


def option(page: Page, label: str) -> Locator:
    return page.locator(".game-decision button", has_text=label)


def body(s: Session) -> None:
    page = s.page()
    page.goto(GAME)
    wait_idle(page)
    s.shot(page, "opened")
    side = clean(drawer_text(page))
    s.check("ways out the root corridor" in side.lower(), f"ways out panel: {side[-300:]}")
    s.check("carrying" in side.lower() and "Pry Bar" in side, "carrying panel missing")

    # 1. Move: the header, the trail and the ways out follow.
    submit(page, "I go down the corridor.\n!move to_id=corridor")
    wait_idle(page)
    s.shot(page, "moved")
    s.check(
        "The Root Corridor" in clean(page.inner_text(".game-scene")),
        "scene header did not follow the move",
    )
    s.check("Arrived at The Root Corridor" in " ".join(cards(page)), "arrival card missing")
    side = clean(drawer_text(page))
    s.check(
        "Crawler" in side or "crawler" in side.lower(),
        f"the crawler is not shown here: {side[:400]}",
    )
    s.check(
        "trail the collapsed archway the root corridor" in side.lower(),
        f"trail wrong: {side[-200:]}",
    )

    # 2. A dangerous fight roll against an npc: health moves.
    submit(
        page,
        'I stab the crawler.\n!roll what="Stab the crawler" ability=brute against=crawler dangerous=true items=\'["pry-bar-melee-weapon"]\'',  # noqa: E501
    )
    wait_idle(page)
    s.shot(page, "fight")
    s.check(any("against" in c for c in cards(page)), f"fight card missing: {cards(page)[-2:]}")

    # 3. Hire Grix back at the entrance: the worldsmith writes abilities.
    submit(page, "Back to the archway.\n!move to_id=entrance")
    wait_idle(page)
    submit(page, 'I hire Grix.\n!hire entity_id=grix terms="Carry the torch for a share"')
    wait_idle(page, timeout=40)
    s.shot(page, "hired")
    side = clean(drawer_text(page))
    s.check(
        "party" in side.lower() and "Grix" in side and "Brute" in side,
        f"party panel missing Grix's sheet: {side[:500]}",
    )
    s.check("signs on" in " ".join(cards(page)), f"hire card missing: {cards(page)[-3:]}")
    text = clean(page.inner_text(".game-transcript"))
    s.check("(the story goes on)" in text, "the hire's own exchange is missing")

    # 4. An interjection: seed the dice so Grix passes the d10, then play a turn.
    urllib.request.urlopen(f"{BASE}/qa/chatty/buried-keep--kael").read()
    submit(page, "I wait and listen.\n!none")
    wait_idle(page)
    page.wait_for_timeout(3500)
    s.shot(page, "interjection")
    text = clean(page.inner_text(".game-transcript"))
    s.check("(the party speaks)" in text, "no interjection landed")
    s.check("[party] I have a thought" in text, "the member's line missing")
    accept = page.get_by_role("button", name="Accept")
    s.check(accept.count() == 1, "no Accept button on the proposal")
    s.check("Grix proposes:" in text, f"proposal text missing: {text[-300:]}")
    if accept.count():
        accept.click()
        page.wait_for_timeout(500)
        wait_idle(page)
        s.shot(page, "accepted")
        s.check(
            "We follow the party member's suggestion." in " ".join(bubbles(page)),
            "accepted proposal not played as the prompt",
        )
        s.check(
            page.get_by_role("button", name="Accept").count() == 0,
            "Accept button stayed after the turn",
        )

    # 5. Level up: an option-only decision, the composer closed, then Grix's turn.
    submit(page, "The adventure ends here.\n!level_up")
    wait_idle(page) if False else page.wait_for_timeout(4000)
    s.shot(page, "level-up")
    text = clean(page.inner_text("body"))
    s.check("Level up: Kael" in text, "level-up decision missing")
    s.check(
        composer(page).is_disabled() and send(page).is_disabled(),
        "composer open on an option-only decision",
    )
    s.check(placeholder(page) == "Choose an option above.", f"placeholder: {placeholder(page)!r}")
    s.check(option(page, "Brute +1, Health +1").count() == 1, "level option missing")
    option(page, "Brute +1, Health +1").click()
    page.wait_for_timeout(4000)
    s.shot(page, "level-up-grix")
    text = clean(page.inner_text("body"))
    s.check(
        "Level 2: Brute +1, Health +1" in " ".join(cards(page)),
        f"level card missing: {cards(page)[-3:]}",
    )
    s.check("Level up: Grix" in text, "Grix's level-up did not follow")
    s.check(
        "Brute +1, Health +1" in " ".join(bubbles(page)),
        "the chosen option is not the player's bubble",
    )
    grix_option = option(page, "Erudite +1, Inventory +1")
    s.note(f"grix options: {grix_option.count()}")
    grix_option.first.click()
    page.wait_for_timeout(4000)
    wait_idle(page)
    s.shot(page, "level-up-done")
    s.check(
        "the game is waiting on you" not in clean(page.inner_text("body")),
        "a level-up decision stayed open",
    )
    side = clean(drawer_text(page))
    s.check("Health 11/11" in side, f"health did not rise: {side[:300]}")
    s.check("Level 2" in side, "level did not rise")

    # 6. Rest.
    submit(page, "We rest.\n!change verb=rest")
    wait_idle(page)
    s.check("Rested" in " ".join(cards(page)), "rest card missing")

    # 7. Walk the whole map so the frontier runs out: More map appears.
    for words, to in (("corridor", "corridor"), ("storeroom", "storeroom")):
        submit(page, f"To the {words}.\n!move to_id={to}")
        wait_idle(page)
    submit(page, "I take the rope.\n!change verb=move_item item_id=rope-coil to=player")
    wait_idle(page)
    s.check(
        "Took rope" in " ".join(cards(page)).lower() or "Took" in " ".join(cards(page)),
        f"take card missing: {cards(page)[-2:]}",
    )
    submit(page, "I force the cell door.\n!change verb=unlock_way to_id=sealed-cell")
    wait_idle(page)
    s.check("unlocked" in " ".join(cards(page)), f"unlock card missing: {cards(page)[-2:]}")
    submit(page, "Into the cell.\n!move to_id=sealed-cell")
    wait_idle(page)
    submit(page, "I search the cell.\n!change verb=reveal entity_id=tarnished-flask")
    wait_idle(page)
    s.check("found" in " ".join(cards(page)), f"found card missing: {cards(page)[-2:]}")
    for to in ("storeroom", "corridor", "cellar"):
        submit(page, f"To the {to}.\n!move to_id={to}")
        wait_idle(page)
    s.shot(page, "frontier-out")
    text = clean(page.inner_text("body"))
    s.check(
        "THERE IS MORE BEYOND HERE" in text.upper(), "More-map banner missing when the map ran out"
    )
    more = page.locator(".game-composer button", has_text="More map")
    s.check(more.count() == 1 and more.is_visible(), "More map button missing")
    # Send (not the action) still plays a normal turn while the map is out.
    submit(page, "I look for the lurker.\n!change verb=reveal entity_id=lurker")
    wait_idle(page)
    s.check(
        "Lurker" in clean(drawer_text(page)) or "lurker" in clean(drawer_text(page)).lower(),
        "revealed npc missing from Here",
    )
    # The action with the words: the worldsmith writes, no turn, then a turn on the words.
    composer(page).fill("Through the roots to the east.")
    more.click()
    page.wait_for_timeout(800)
    s.shot(page, "more-map-working")
    phases: set[str] = set()
    for _ in range(100):
        phases.add(placeholder(page))
        if (
            not composer(page).is_disabled()
            and page.locator(".q-spinner:visible:not(.q-img .q-spinner)").count() == 0
        ):
            break
        page.wait_for_timeout(200)
    wait_idle(page)
    s.note(f"phases during more map: {phases}")
    s.check(any("Worldsmith" in p for p in phases), "worldsmith phase not shown for more map")
    s.shot(page, "more-map-done")
    s.check(
        page.locator(".game-composer button", has_text="More map").count() == 0,
        "More map stayed after the extension",
    )
    s.check(
        "Through the roots to the east." in " ".join(bubbles(page)),
        "the more-map words were not played as a turn",
    )
    prompts = [e for e in log() if e["role"] == "master"]
    s.check("qa-room-" in prompts[-1]["prompt"], "the master was not shown the new way")
    written = [e for e in log() if e["role"] == "worldsmith"][-1]["answer"]
    room = json.loads(written)["start"]
    submit(page, f"East then.\n!move to_id={room}")
    wait_idle(page)
    s.check(
        "QA Room" in clean(page.inner_text(".game-scene")), "could not walk into the written room"
    )
    s.shot(page, "new-room")

    # 8. Two games at once: a second tab on another game while this one plays is refused.
    other = s.page()
    other.goto(BASE + "/game/whispering-vault/kael")
    wait_idle(other)
    submit(page, "I take a long look.\n!slow narrator\n!none", wait=True)
    page.wait_for_timeout(500)
    submit(other, "I act while the keep is busy.", wait=False)
    other.wait_for_timeout(1000)
    notes = notifications(other)
    s.check(any("in flight" in n for n in notes), f"no busy refusal on the second game: {notes}")
    s.shot(other, "busy-refused")
    wait_idle(page, timeout=60)


run("goons", body)
