from support.game import with_entity
from support.table import LONER3E, game, narrowed

from aidm.app.spawn import PROMPT_MAX_BYTES
from aidm.core.model import PackSelection
from aidm.core.play import Chapter, Exchange, SpokenLine
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import Loner3eCast, Loner3eGame

SOURCE_BYTES = 48_000
CAST_SIZE = 30
CHAPTER_COUNT = 40
WRITTEN_CHAPTERS = 2
EXCHANGES_PER_CHAPTER = 20
TRANSCRIPT_CHARS = 400


def test_a_heavy_game_still_fits_the_command_line() -> None:
    engine, raw_state = game(LONER3E)
    engine = narrowed(engine, Loner3eEngine)
    state = narrowed(raw_state, Loner3eGame)

    draft = state.draft()
    draft.packs = PackSelection(ids=("srd", "ap01-fantasy"))
    draft.payload.source = "x" * SOURCE_BYTES
    draft.log = _chapters()
    state = draft.commit()

    for index in range(CAST_SIZE):
        member = Loner3eCast(id=f"cast-{index}", name=f"Member {index}", brief="", known=True)
        state = with_entity(state, member)

    engine.validate(state)
    prompt = engine.render_next(state, "…")
    assert len(prompt.encode()) < PROMPT_MAX_BYTES


def _chapters() -> list[Chapter]:
    recapped = [
        Chapter(title=f"Scene {index}", focus="", recap=f"A short recap of scene {index}.")
        for index in range(CHAPTER_COUNT - WRITTEN_CHAPTERS)
    ]
    written = [
        Chapter(title=f"Scene {index}", focus="", exchanges=_exchanges())
        for index in range(CHAPTER_COUNT - WRITTEN_CHAPTERS, CHAPTER_COUNT)
    ]
    return [*recapped, *written]


def _exchanges() -> list[Exchange]:
    line = SpokenLine(text="x" * TRANSCRIPT_CHARS)
    return [Exchange(words="", lines=(line,)) for _ in range(EXCHANGES_PER_CHAPTER)]
