from aidm.core.play import Exchange, SceneRecord, SpokenLine
from aidm.core.prompt import INTERJECTED, TAIL_EXCHANGES, render_history, told_history


def _told(prompt: str) -> Exchange:
    return Exchange(prompt=prompt, lines=(SpokenLine(text=f"{prompt} happens."),))


def test_render_history_prints_an_older_scenes_recap_and_not_its_exchanges() -> None:
    older = SceneRecord(
        title="The Drowned Hall",
        focus="What lies beneath the water?",
        recap="You found the drowned hall and left it behind.",
        exchanges=(_told("dropped"),),
    )
    scenes = [older, SceneRecord(title="A1", focus="q1"), SceneRecord(title="A2", focus="q2")]

    history = render_history(scenes)

    assert "what happened: You found the drowned hall and left it behind." in history
    assert "dropped" not in history


def test_render_history_prints_the_last_two_scenes_whole() -> None:
    recent_a = SceneRecord(title="A1", focus="q1", exchanges=(_told("p1"), _told("p2")))
    recent_b = SceneRecord(title="A2", focus="q2", exchanges=(_told("p3"),))
    scenes = [SceneRecord(title="Hub", focus="q0"), recent_a, recent_b]

    history = render_history(scenes)

    assert "> p1\np1 happens." in history
    assert "> p2\np2 happens." in history
    assert "> p3\np3 happens." in history


def test_render_history_shows_an_older_scenes_last_tail_exchanges_only() -> None:
    prompts = [f"p{number}" for number in range(TAIL_EXCHANGES + 2)]
    older = SceneRecord(title="Hub", focus="q0", exchanges=tuple(_told(p) for p in prompts))
    scenes = [older, SceneRecord(title="A1", focus="q1"), SceneRecord(title="A2", focus="q2")]

    history = render_history(scenes)

    for kept in prompts[-TAIL_EXCHANGES:]:
        assert f"> {kept}" in history
    for dropped in prompts[:-TAIL_EXCHANGES]:
        assert f"> {dropped}\n" not in history


def test_told_history_reads_as_the_master_does_without_the_recap() -> None:
    older = SceneRecord(
        title="Hub", focus="q0", recap="What happened before.", exchanges=(_told("dropped"),)
    )
    recent_a = SceneRecord(title="A1", focus="q1", exchanges=(_told("p1"),))
    recent_b = SceneRecord(title="A2", focus="q2", exchanges=(_told("p2"),))
    scenes = [older, recent_a, recent_b]

    read = told_history(scenes)

    assert read == "SCENE: A1\nq1\n\n> p1\np1 happens.\n\nSCENE: A2\nq2\n\n> p2\np2 happens."
    assert told_history([SceneRecord(title="A1", focus="q1")]) == "(nothing yet)"


def test_history_keeps_who_said_what() -> None:
    exchange = Exchange(
        prompt="I ask Mara.",
        lines=(
            SpokenLine(speaker_id="mara", speaker="Mara", text="Not for sale."),
            SpokenLine(text="She goes back to her ledger."),
        ),
    )
    scenes = [SceneRecord(title="A1", focus="", exchanges=(exchange,))]

    read = told_history(scenes)

    assert "> I ask Mara.\nMara: Not for sale.\nShe goes back to her ledger." in read
    assert "Mara: Not for sale." in render_history(scenes)


def test_a_marked_exchange_carries_no_prompt_line() -> None:
    story = Exchange(prompt="", mark="story", lines=(SpokenLine(text="Quiet falls."),))
    party = Exchange(
        prompt="",
        mark="interjection",
        lines=(SpokenLine(speaker_id="vessa", speaker="Vessa", text="Wait."),),
    )
    scenes = [SceneRecord(title="A1", focus="q1", exchanges=(story, party))]

    read = told_history(scenes)

    assert "> " not in read
    assert INTERJECTED in read
