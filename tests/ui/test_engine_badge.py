from aidm_ui.components.engine import engine_appearance


def test_each_installed_engine_gets_a_distinct_badge() -> None:
    story = engine_appearance("story")
    dnd5e = engine_appearance("dnd5e")

    assert story.label == "STORY"
    assert dnd5e.label == "D&D 5E"
    assert story.colour != dnd5e.colour
