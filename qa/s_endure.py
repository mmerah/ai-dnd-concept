"""Long play on every engine: many turns, reloads between them, and the saves still load."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from drive import BASE, Session, bubbles, clean, composer, run, submit, wait_idle

WORK = Path(os.environ.get("QA_WORK", "/tmp/aidm-qa-work"))

RUNS: dict[str, tuple[str, ...]] = {
    "whispering-vault": (
        '!roll what="Listen at the door" actor_id=player question="Is anyone there?"',
        "!reveal entity_id=vault-map",
        '!drive entity_id=mara goal="Finish the catalogue"',
        "!change_tags entity_id=player kind=condition gained='[\"winded\"]'",
        "!restore_luck entity_id=player",
        '!roll what="Force the lid" actor_id=player question="Does it lift?"',
        "!change_tags entity_id=player kind=condition lost='[\"winded\"]'",
        '!roll what="Read the seal" actor_id=player question="Does it name a year?"',
    ),
    "buried-keep": (
        "!move to_id=corridor",
        '!roll what="Shoulder the door" ability=brute difficulty=8',
        "!move to_id=storeroom",
        "!rest",
        '!roll what="Search the shelves" ability=erudite difficulty=10',
        "!move to_id=corridor",
        "!meanwhile dweller_id=grix dweller_to=corridor",
        "!move to_id=entrance",
    ),
    "drowned-road": (
        '!roll what="Wade the flats" skill=dash',
        '!roll what="Wade again" skill=dash',
        '!roll what="Wade again" skill=dash',
        '!roll what="Wade again" skill=dash dangerous=true',
        "!catch_breath actor_id=player",
        '!change_stress actor_id=player amount=2 why="The cold"',
        '!roll what="Think it through" skill=think',
        '!ask_world question="Is the bell still ringing?" die=8',
    ),
    "silent-relay": (
        '!roll what="Slip the hatch" skill="Stealth"',
        '!gain_item name="Cutting torch"',
        '!roll what="Cut the lock" skill="Stealth"',
        '!drop_item item_id="cutting-torch"',
        '!spend amount=2 why="Docking fees"',
        "!change_hindrances gained='[\"Bruised\"]'",
        '!ask_world question="Are the relays still warm?"',
        '!roll what="Run the board" skill="Stealth"',
    ),
}


def body(s: Session) -> None:
    for scenario, scripts in RUNS.items():
        page = s.page()
        page.goto(f"{BASE}/game/{scenario}/kael")
        wait_idle(page, timeout=40)
        for index, script in enumerate(scripts):
            submit(page, f"Turn {index + 1} of {scenario}.\n{script}")
            wait_idle(page, timeout=60)
            text = clean(page.inner_text("body"))
            if not s.check(
                "Internal Server Error" not in text and "Traceback" not in text,
                f"{scenario} turn {index + 1} ({script}) broke the page",
            ):
                break
            if index % 3 == 2:  # a reload every third turn must not lose the story
                seen = len(bubbles(page))
                page.reload()
                wait_idle(page, timeout=40)
                s.check(
                    len(bubbles(page)) >= seen,
                    f"{scenario} lost {seen - len(bubbles(page))} bubbles on a reload",
                )
        s.check(
            not composer(page).is_disabled()
            or page.locator(".game-decision").count() > 0
            or "over" in clean(page.inner_text("body")).lower(),
            f"{scenario} left the composer shut with no decision and no ending",
        )
        s.note(f"{scenario}: {len(bubbles(page))} bubbles after {len(scripts)} turns")
        s.shot(page, f"endure-{scenario}")
        page.close()

    saves = sorted(WORK.glob("saves/*.json"))
    s.note(f"saves written: {[p.name for p in saves]}")
    s.check(len(saves) == len(RUNS), f"expected {len(RUNS)} saves, found {len(saves)}")


run("endure", body)
