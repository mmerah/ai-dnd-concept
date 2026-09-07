"""The settings page: tabs, no-op save, a real save, validation, busy and stale refusals."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from drive import BASE, Session, clean, composer, notifications, placeholder, run, submit, wait_idle

WORK = Path(os.environ.get("QA_WORK", "/tmp/aidm-qa-work"))


def switch(page, label: str):  # noqa: ANN001, ANN202
    return page.locator(".q-toggle", has_text=label)


def body(s: Session) -> None:
    page = s.page()
    page.goto(BASE + "/settings")
    page.wait_for_timeout(1200)
    s.shot(page, "settings")
    tabs = [clean(t).lower() for t in page.locator(".q-tab").all_inner_texts()]
    s.note(f"tabs: {tabs}")
    s.check(
        tabs
        == [
            "providers",
            "roles",
            "media",
            "speech",
            "interjections",
            "source max chars",
            "server port",
        ],
        f"unexpected tabs: {tabs}",
    )
    page.get_by_role("button", name="Save").click()
    page.wait_for_timeout(600)
    s.check("Nothing changed." in notifications(page), f"no-op save: {notifications(page)}")

    # Roles tab: the nested expansions and the provider select.
    page.get_by_role("tab", name="roles").click()
    page.wait_for_timeout(500)
    s.shot(page, "roles")
    page.locator(".q-expansion-item", has_text="master").first.locator(".q-item").first.click()
    page.wait_for_timeout(500)
    s.shot(page, "roles-master")
    roles = clean(page.locator(".q-tab-panels").inner_text())
    s.check(
        "provider" in roles and "model" in roles and "effort" in roles,
        f"master fields: {roles[:300]}",
    )

    # A number out of range: validation refuses the save.
    timeout_box = page.locator(".q-tab-panel .q-field", has_text="timeout").first.locator("input")
    timeout_box.fill("0")
    page.get_by_role("button", name="Save").click()
    page.wait_for_timeout(800)
    s.shot(page, "invalid-timeout")
    notes = notifications(page)
    s.check(
        any("greater than 0" in n or "validation" in n.lower() for n in notes),
        f"invalid timeout not refused: {notes}",
    )
    s.check(
        not (WORK / ".env").exists() or "TIMEOUT=0" not in (WORK / ".env").read_text(),
        ".env written despite invalid settings",
    )
    page.reload()
    page.wait_for_timeout(1000)

    # Media enabled without a key: the model validator refuses.
    page.get_by_role("tab", name="media").click()
    page.wait_for_timeout(400)
    switch(page, "enabled").click()
    page.get_by_role("button", name="Save").click()
    page.wait_for_timeout(800)
    notes = notifications(page)
    s.check(any("api_key" in n for n in notes), f"media without a key not refused: {notes}")
    s.shot(page, "media-no-key")
    page.reload()
    page.wait_for_timeout(1000)

    # A real change: interjections off. Applied, the page reloads, .env holds the key.
    page.get_by_role("tab", name="interjections").click()
    page.wait_for_timeout(400)
    switch(page, "interjections").click()
    page.get_by_role("button", name="Save").click()
    page.wait_for_timeout(800)
    page.wait_for_timeout(2000)
    env = (WORK / ".env").read_text() if (WORK / ".env").exists() else ""
    s.check(
        "INTERJECTIONS='false'" in env or "INTERJECTIONS=false" in env, f".env after save: {env!r}"
    )
    page.get_by_role("tab", name="interjections").click()
    page.wait_for_timeout(400)
    s.check(
        switch(page, "interjections").get_attribute("aria-checked") == "false",
        "the switch does not show the saved value after the reload",
    )
    s.shot(page, "interjections-off")

    # A secret: typed once, stored, never read back.
    page.get_by_role("tab", name="providers").click()
    page.wait_for_timeout(400)
    page.locator(".q-expansion-item", has_text="openrouter").first.locator(".q-item").first.click()
    page.wait_for_timeout(500)
    s.shot(page, "providers-open")
    key_box = page.locator(".q-tab-panel .q-field", has_text="api key").first.locator("input")
    s.check(
        key_box.get_attribute("placeholder") == "not set",
        f"key placeholder: {key_box.get_attribute('placeholder')!r}",
    )
    key_box.fill("sk-test-123")
    page.get_by_role("button", name="Save").click()
    page.wait_for_timeout(2000)
    env = (WORK / ".env").read_text()
    s.check("PROVIDERS__OPENROUTER__API_KEY='sk-test-123'" in env, f".env after key: {env!r}")
    page.get_by_role("tab", name="providers").click()
    page.wait_for_timeout(400)
    page.locator(".q-expansion-item", has_text="openrouter").first.locator(".q-item").first.click()
    page.wait_for_timeout(500)
    key_box = page.locator(".q-tab-panel .q-field", has_text="api key").first.locator("input")
    s.check(
        key_box.get_attribute("placeholder") == "set — type to replace",
        "stored key placeholder wrong",
    )
    s.check(key_box.input_value() == "", "the stored key was read back into the page")
    s.shot(page, "key-stored")

    # Media can now be enabled (the key is there); its model default appears.
    page.get_by_role("tab", name="media").click()
    page.wait_for_timeout(400)
    switch(page, "enabled").click()
    page.get_by_role("button", name="Save").click()
    page.wait_for_timeout(2500)
    env = (WORK / ".env").read_text()
    s.check("MEDIA__ENABLED='true'" in env, f"media enable: {env!r}")

    # Busy: a game mid-turn refuses the save.
    game = s.page()
    game.goto(BASE + "/game/whispering-vault/kael")
    game.wait_for_timeout(4000)
    s.shot(game, "game-after-settings")
    s.note(
        f"game state: placeholder={placeholder(game)!r} spinner={game.locator('.q-spinner').count()} notes={notifications(game)}"  # noqa: E501
    )
    wait_idle(game, timeout=60)
    submit(game, "I linger.\n!slow narrator\n!none")
    game.wait_for_timeout(2500)
    s.shot(game, "game-busy")
    page.get_by_role("tab", name="interjections").click()
    page.wait_for_timeout(400)
    switch(page, "interjections").click()
    page.get_by_role("button", name="Save").click()
    page.wait_for_timeout(800)
    notes = notifications(page)
    s.check(any("in flight" in n for n in notes), f"busy save not refused: {notes}")
    s.shot(page, "busy-save")
    wait_idle(game, timeout=60)
    page.reload()
    page.wait_for_timeout(1000)

    # Stale: after a save applies, the open game page must be reloaded.
    page.get_by_role("tab", name="interjections").click()
    page.wait_for_timeout(400)
    switch(page, "interjections").click()
    page.get_by_role("button", name="Save").click()
    page.wait_for_timeout(1500)
    submit(game, "I try to play on.", wait=False)
    game.wait_for_timeout(1000)
    notes = notifications(game)
    s.check(any("settings changed" in n.lower() for n in notes), f"stale game not warned: {notes}")
    s.shot(game, "stale-game")
    game.reload()
    game.wait_for_timeout(1500)
    wait_idle(game)
    s.check(
        composer(game).input_value() == "I try to play on.", "draft lost across the stale reload"
    )
    submit(game, "I try to play on.")
    wait_idle(game)
    s.check(
        "I try to play on." in clean(game.inner_text(".game-transcript")),
        "could not play after the reload",
    )

    # Illustration enabled: the game page runs the media poll; art requests fail quietly.
    game.wait_for_timeout(3500)
    s.shot(game, "media-on")


run("settings", body)
