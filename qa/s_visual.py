"""Screenshots of every page under each engine's theme, at a desktop and a phone width."""

import sys
from pathlib import Path

from playwright.sync_api import Page

sys.path.insert(0, str(Path(__file__).parent))
from drive import BASE, Device, Session, submit, wait_idle

GAMES = {
    "loner": "/game/whispering-vault/kael",
    "goons": "/game/buried-keep/kael",
    "breathless": "/game/drowned-road/kael",
    "24xx": "/game/silent-relay/kael",
}
PHONE: Device = {
    "viewport": {"width": 390, "height": 664},
    "device_scale_factor": 2,
    "is_mobile": True,
    "has_touch": True,
}


def theme_of(page: Page) -> str:
    return page.evaluate(
        "[...document.querySelector('.q-layout').classList].filter(c => c.startsWith('game-theme-')).join(' ')"  # noqa: E501
    )


def body(s: Session) -> None:
    page = s.page()
    for name, path in GAMES.items():
        page.goto(BASE + path)
        wait_idle(page, timeout=40)
        submit(page, "I look around and try something.")
        wait_idle(page)
        page.wait_for_timeout(3000)
        s.note(f"{name}: theme class {theme_of(page)!r}")
        s.check(theme_of(page).startswith("game-theme-"), f"{name}: no theme class on the layout")
        s.shot(page, f"{name}-game")
    # The launcher follows the picked scenario.
    page.goto(BASE + "/")
    page.wait_for_timeout(1000)
    s.note(f"home: theme class {theme_of(page)!r}")
    s.shot(page, "home")
    page.locator(".q-select").first.click()
    page.locator(".q-menu .q-item", has_text="The Silent Relay").first.click()
    page.wait_for_timeout(600)
    s.note(f"home after picking 24XX: theme class {theme_of(page)!r}")
    s.check(
        theme_of(page) == "game-theme-twentyfourxx", "home did not re-theme for the picked scenario"
    )
    s.shot(page, "home-24xx")
    for path, name in (("/settings", "settings"), ("/create", "create"), ("/scenario", "scenario")):
        page.goto(BASE + path)
        page.wait_for_timeout(1000)
        s.note(f"{name}: theme class {theme_of(page)!r}")
        s.shot(page, name)
    page.goto(BASE + "/create")
    page.wait_for_timeout(800)
    page.locator(".q-select:has(.q-field__label:text-is('Rules'))").click()
    page.locator(".q-menu .q-item", has_text="BREATHLESS").first.click()
    page.wait_for_timeout(600)
    s.check(
        theme_of(page) == "game-theme-breathless", "create did not re-theme for the picked rules"
    )
    s.shot(page, "create-breathless")
    # The restart dialog and a notification under a theme.
    page.goto(BASE + GAMES["goons"])
    wait_idle(page, timeout=40)
    page.locator(".q-header button").last.click()
    page.get_by_text("Restart this game").click()
    page.wait_for_timeout(500)
    s.shot(page, "goons-restart-dialog")
    page.get_by_role("button", name="Keep playing").click()
    submit(page, "I try something.\n!crash")
    page.wait_for_timeout(2500)
    s.shot(page, "goons-crash-toast")
    # A phone, two engines.
    context = s.browser.new_context(**PHONE)
    phone = context.new_page()
    phone.set_default_timeout(15000)
    for name in ("loner", "24xx"):
        phone.goto(BASE + GAMES[name])
        wait_idle(phone, timeout=40)
        s.shot(phone, f"phone-{name}")
        phone.locator('button:has(i:text("menu_book"))').click()
        phone.wait_for_timeout(600)
        s.shot(phone, f"phone-{name}-drawer")
        phone.locator(".game-drawer button:has(i:text('close'))").click()
        phone.wait_for_timeout(400)
    phone.goto(BASE + "/")
    phone.wait_for_timeout(800)
    s.shot(phone, "phone-home")
    context.close()


from drive import run  # noqa: E402

run("visual", body)
