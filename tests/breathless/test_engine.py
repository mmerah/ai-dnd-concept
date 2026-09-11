from support.breathless import DAX, ENGINE, small_world
from support.table import BREATHLESS, change, game, narrowed

from aidm.core.views import PanelRow
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.breathless.world import STARTING_ITEM, BreathlessGame
from aidm.engines.scenes.packs import SRD_PACK
from aidm.engines.seam import AnyEngine

FIRE_AXE = "fire-axe"
OVID = "ovid-sarn"
SRD = ENGINE.packs["srd"]
PICKS = {
    "pack": "srd",
    "pronouns": "she/her",
    "job": SRD.jobs[0],
    "skill-d10": "bash",
    "skill-d8": "dash",
    "skill-d6": "sneak",
    "item": SRD.weapons[0],
}


def _breathless_game() -> tuple[AnyEngine, BreathlessGame]:
    engine, state = game(BREATHLESS)
    state = narrowed(state, BreathlessGame)
    return engine, state


def test_the_shipped_game_begins_with_the_srd_pack_and_the_players_item() -> None:
    _, state = _breathless_game()
    assert state.packs == (SRD_PACK,)
    world = state.payload
    sheet = world.player.require_sheet()
    assert sheet.items[FIRE_AXE].die == STARTING_ITEM
    assert sheet.pronouns == "he/him"
    assert sheet.job == "Park Ranger"
    assert PLAYER_ID not in world.present()


def test_join_party_lands_a_party_joined_fact_and_adds_the_member() -> None:
    engine, state = _breathless_game()
    draft = state.draft()

    _ = change(engine, draft, "join_party", entity_id=OVID)

    assert OVID in draft.payload.party


def test_the_player_views_backpack_panel_lists_items_and_the_med_kit() -> None:
    world = small_world()
    world.payload.player.require_sheet().med_kit = True
    view = ENGINE.player_view(world)
    backpack = next(panel for panel in view.panels if panel.title == "Backpack")
    assert PanelRow(label="Wrench", detail="d10") in backpack.rows
    assert PanelRow(label="Med kit", detail="held") in backpack.rows


def test_master_sections_never_lists_the_player_under_here() -> None:
    sections = dict(ENGINE.master_sections(small_world()))
    assert "Jax" not in sections["HERE WITH THE PLAYER"]
    assert "Mira" in sections["HERE WITH THE PLAYER"]


def test_master_sections_lists_the_backpack() -> None:
    world = small_world()
    world.payload.player.require_sheet().med_kit = True
    sections = dict(ENGINE.master_sections(world))
    assert sections["BACKPACK"] == "- Wrench[wrench] — d10\n- med kit"


def test_entity_line_marks_a_dead_one_after_the_brief() -> None:
    dead = Person(id=DAX, name="Dax", brief="A looter", known=True, alive=False)
    line = dead.line()
    assert line.startswith("- Dax[dax] — A looter (dead)")


def test_skill_steps_exclude_earlier_picks() -> None:
    steps = ENGINE.creation_steps(PICKS)
    d8_ids = {option.id for option in next(s for s in steps if s.id == "skill-d8").options}
    d6_ids = {option.id for option in next(s for s in steps if s.id == "skill-d6").options}
    assert "bash" not in d8_ids
    assert {"bash", "dash"} & d6_ids == set()


def test_create_character_round_trip() -> None:
    character = ENGINE.create_character("Jax", "A wiry mechanic", PICKS)
    sheet = character.payload.require_sheet()
    assert sheet.skills == {"bash": 10, "dash": 8, "sneak": 6, "shoot": 4, "think": 4, "sway": 4}
    assert sheet.worn == sheet.skills
    assert [(item.name, item.die) for item in sheet.items.values()] == [
        (SRD.weapons[0], STARTING_ITEM)
    ]


def test_preview_character_shows_the_backpack_row() -> None:
    character = ENGINE.create_character("Jax", "A wiry mechanic", PICKS)
    rows = ENGINE.preview_character(character)
    assert ("Backpack", SRD.weapons[0]) in rows
