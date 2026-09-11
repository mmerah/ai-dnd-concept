from aidm.core.play import Chapter, Exchange, SpokenLine
from aidm.core.prompt import INTERJECTED, TAIL_EXCHANGES, render_history, told_history


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


def test_render_history_prints_the_last_two_scenes_whole() -> None:
    recent_a = Chapter(title="A1", focus="q1", exchanges=[_told("p1"), _told("p2")])
    recent_b = Chapter(title="A2", focus="q2", exchanges=[_told("p3")])
    scenes = [Chapter(title="Hub", focus="q0"), recent_a, recent_b]

    history = render_history(scenes)

    assert "> p1\np1 happens." in history
    assert "> p2\np2 happens." in history
    assert "> p3\np3 happens." in history


def test_render_history_shows_an_older_scenes_last_tail_exchanges_only() -> None:
    words_list = [f"p{number}" for number in range(TAIL_EXCHANGES + 2)]
    older = Chapter(title="Hub", focus="q0", exchanges=[_told(w) for w in words_list])
    scenes = [older, Chapter(title="A1", focus="q1"), Chapter(title="A2", focus="q2")]

    history = render_history(scenes)

    for kept in words_list[-TAIL_EXCHANGES:]:
        assert f"> {kept}" in history
    for dropped in words_list[:-TAIL_EXCHANGES]:
        assert f"> {dropped}\n" not in history


def test_told_history_reads_as_the_master_does_without_the_recap() -> None:
    older = Chapter(
        title="Hub", focus="q0", recap="What happened before.", exchanges=[_told("dropped")]
    )
    recent_a = Chapter(title="A1", focus="q1", exchanges=[_told("p1")])
    recent_b = Chapter(title="A2", focus="q2", exchanges=[_told("p2")])
    scenes = [older, recent_a, recent_b]

    read = told_history(scenes)

    assert read == "SCENE: A1\nq1\n\n> p1\np1 happens.\n\nSCENE: A2\nq2\n\n> p2\np2 happens."
    assert told_history([Chapter(title="A1", focus="q1")]) == "(nothing yet)"


def test_history_keeps_who_said_what() -> None:
    exchange = Exchange(
        words="I ask Mara.",
        lines=(
            SpokenLine(speaker_id="mara", speaker="Mara", text="Not for sale."),
            SpokenLine(text="She goes back to her ledger."),
        ),
    )
    scenes = [Chapter(title="A1", focus="", exchanges=[exchange])]

    read = told_history(scenes)

    assert "> I ask Mara.\nMara: Not for sale.\nShe goes back to her ledger." in read
    assert "Mara: Not for sale." in render_history(scenes)


def test_a_marked_exchange_carries_no_prompt_line() -> None:
    story = Exchange(words="", mark="story", lines=(SpokenLine(text="Quiet falls."),))
    party = Exchange(
        words="",
        mark="interjection",
        lines=(SpokenLine(speaker_id="vessa", speaker="Vessa", text="Wait."),),
    )
    scenes = [Chapter(title="A1", focus="q1", exchanges=[story, party])]

    read = told_history(scenes)

    assert "> " not in read
    assert INTERJECTED in read
