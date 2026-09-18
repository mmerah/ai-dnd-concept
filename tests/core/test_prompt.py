from aidm.core.play import Chapter, Exchange, SpokenLine
from aidm.core.prompt import TAIL_EXCHANGES, render_history


def _told(words: str) -> Exchange:
    return Exchange(words=words, lines=(SpokenLine(text=f"{words} happens."),))


def test_render_history_prints_an_older_scenes_recap_and_not_its_exchanges() -> None:
    older = Chapter(
        title="The Drowned Hall",
        focus="What lies beneath the water?",
        recap="You found the drowned hall and left it behind.",
        exchanges=[_told("dropped")],
    )
    scenes = [older, Chapter(title="A1", focus="q1"), Chapter(title="A2", focus="q2")]

    history = render_history(scenes)

    assert "what happened: You found the drowned hall and left it behind." in history
    assert "dropped" not in history


def test_render_history_shows_an_older_scenes_last_tail_exchanges_only() -> None:
    words_list = [f"p{number}" for number in range(TAIL_EXCHANGES + 2)]
    older = Chapter(title="Hub", focus="q0", exchanges=[_told(w) for w in words_list])
    scenes = [older, Chapter(title="A1", focus="q1"), Chapter(title="A2", focus="q2")]

    history = render_history(scenes)

    for kept in words_list[-TAIL_EXCHANGES:]:
        assert f"> {kept}" in history
    for dropped in words_list[:-TAIL_EXCHANGES]:
        assert f"> {dropped}\n" not in history
