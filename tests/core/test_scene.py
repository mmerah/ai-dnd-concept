from dataclasses import replace

import pytest
from core_test_support import initialized

from aidm.engines.core import Engine
from aidm.state.entities import PLAYER_ID, CheckedEntityId, EntityId
from aidm.state.model import Game
from aidm.state.scene import Scene

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
        sections=(("PLAYER", "Kael stands here."),),
        director_sections=(("PLAYER", "Kael stands here."), ("HIDDEN", "A vault waits below.")),
        public_entity_ids=public,
        present_entity_ids=present,
        art_subject_ids=subjects,
    )


def _staged(engine: Engine, scene: Scene) -> Engine:
    def build(state: Game) -> Scene:
        del state
        return scene

    return replace(engine, scene=build)


def test_views_refuse_an_unknown_id_in_any_set() -> None:
    engine, state = initialized()
    assert not state.world.require(HIDDEN).known
    unmet = (
        _scene(public=frozenset({HIDDEN})),
        _scene(present=frozenset({HIDDEN})),
        _scene(subjects=(HIDDEN,)),
    )
    for scene in unmet:
        with pytest.raises(ValueError, match="has not met"):
            _ = _staged(engine, scene).views(state)
    with pytest.raises(ValueError, match="does not hold"):
        _ = _staged(engine, _scene(public=frozenset({EntityId("nobody")}))).views(state)


def test_the_narrator_view_drops_director_text() -> None:
    engine, state = initialized()
    narrator = _staged(engine, _scene(present=frozenset({PLAYER_ID}))).views(state).narrator
    assert narrator.sections == (("PLAYER", "Kael stands here."),)
