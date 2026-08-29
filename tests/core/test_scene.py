import pytest
from core_test_support import initialized

from aidm.state.entities import PLAYER_ID, CheckedEntityId, EntityId
from aidm.state.scene import Scene, SceneSection, VisibleScene

HIDDEN = EntityId("vault")


def _scene(
    *,
    public: frozenset[CheckedEntityId] = frozenset(),
    present: frozenset[CheckedEntityId] = frozenset(),
    subjects: tuple[CheckedEntityId, ...] = (),
) -> Scene:
    return Scene(
        key="study",
        label="The Study",
        sections=(
            SceneSection(title="PLAYER", player="Kael stands here."),
            SceneSection(title="HIDDEN", director="A vault waits below."),
        ),
        public_entity_ids=public,
        present_entity_ids=present,
        art_subject_ids=subjects,
    )


def test_revealed_from_refuses_an_unknown_id_in_any_set() -> None:
    _, state = initialized()
    assert not state.world.require(HIDDEN).known
    unmet = (
        _scene(public=frozenset({HIDDEN})),
        _scene(present=frozenset({HIDDEN})),
        _scene(subjects=(HIDDEN,)),
    )
    for scene in unmet:
        with pytest.raises(ValueError, match="has not met"):
            _ = VisibleScene.revealed_from(scene, state.world)
    with pytest.raises(ValueError, match="does not hold"):
        _ = VisibleScene.revealed_from(_scene(public=frozenset({EntityId("nobody")})), state.world)


def test_revealed_from_drops_director_text() -> None:
    _, state = initialized()
    visible = VisibleScene.revealed_from(_scene(present=frozenset({PLAYER_ID})), state.world)
    assert visible.sections == (("PLAYER", "Kael stands here."),)
