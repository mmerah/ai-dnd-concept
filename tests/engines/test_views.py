from collections.abc import Callable

import pytest
from pydantic import ValidationError
from support.game import MARA, initialized, with_entity
from support.tunnelgoons import ENGINE as TUNNELGOONS_ENGINE
from support.tunnelgoons import MIRA as TUNNELGOONS_MIRA
from support.tunnelgoons import small_world as tunnelgoons_world

from aidm.core.entities import Refusal, Slug
from aidm.core.play import Interjection, Line
from aidm.core.views import NarratorView, Subject
from aidm.engines.loner3e.world import Loner3eEntity

SECRET = Loner3eEntity(
    id="hidden-actor",
    name="The Secret",
    brief="Unrevealed canon.",
    concept="A Watcher",
)

OBJECT = Loner3eEntity(
    id="a-locked-chest",
    name="A Locked Chest",
    brief="Iron-bound, and shut fast.",
    known=True,
)


def _loner3e_hidden_shown() -> str:
    engine, state = initialized()
    return str(engine.narrator_view(with_entity(state, SECRET)).model_dump())


def _tunnelgoons_hidden_shown() -> str:
    return str(TUNNELGOONS_ENGINE.narrator_view(tunnelgoons_world()).model_dump())


@pytest.mark.parametrize(
    ("shown_of", "hidden"),
    [
        (_loner3e_hidden_shown, ("The Secret", "vault map")),
        (_tunnelgoons_hidden_shown, ("Robo Mantis",)),
    ],
    ids=["loner3e", "tunnelgoons"],
)
def test_the_narrator_view_names_nobody_the_player_has_not_met(
    shown_of: Callable[[], str], hidden: tuple[str, ...]
) -> None:
    shown = shown_of()
    for label in hidden:
        assert label not in shown


def _loner3e_dead_view() -> tuple[NarratorView, Slug]:
    engine, state = initialized()
    draft = state.draft()
    _ = draft.world.kill(MARA)
    return engine.narrator_view(draft), MARA


def _tunnelgoons_dead_view() -> tuple[NarratorView, Slug]:
    state = tunnelgoons_world()
    state.world.npcs[TUNNELGOONS_MIRA].alive = False
    return TUNNELGOONS_ENGINE.narrator_view(state), TUNNELGOONS_MIRA


@pytest.mark.parametrize(
    "build", [_loner3e_dead_view, _tunnelgoons_dead_view], ids=["loner3e", "tunnelgoons"]
)
def test_the_dead_stay_in_the_scene_but_do_not_speak(
    build: Callable[[], tuple[NarratorView, Slug]],
) -> None:
    view, known = build()
    assert known in [subject.id for subject in view.subjects]
    assert known not in view.speakers


def test_a_narrator_view_naming_a_speaker_who_is_not_a_subject_is_refused() -> None:
    subject = Subject(id="mara", name="Mara", brief="A ferrywoman.")
    with pytest.raises(ValidationError, match="not subjects"):
        _ = NarratorView(
            place="p",
            title="t",
            focus="f",
            situation="s",
            subjects=(subject,),
            speakers=("stranger",),
            party=(subject.id,),
            sheet=(),
        )


def test_check_interjection_accepts_the_members_own_lines_and_refuses_the_rest() -> None:
    member_id = "mara"
    accepted = Interjection(
        lines=(Line(speaker_id=member_id, text="Careful."),), proposal="I check the door."
    )
    stranger = Interjection(lines=(Line(speaker_id="kael", text="Careful."),))
    bare_proposal = Interjection(lines=(), proposal="I check the door.")

    subject = Subject(id=member_id, name="Mara", brief="A ferrywoman.")
    view = NarratorView(
        place="p",
        title="t",
        focus="f",
        situation="s",
        subjects=(subject,),
        speakers=(member_id,),
        party=(member_id,),
        sheet=(),
    )

    view.check_interjection(member_id, accepted)
    with pytest.raises(Refusal, match=f"only {member_id} speaks here"):
        view.check_interjection(member_id, stranger)
    with pytest.raises(Refusal, match="a proposal comes with at least one line"):
        view.check_interjection(member_id, bare_proposal)


def test_the_player_view_panels_carry_icon_ids_for_who_else_is_here() -> None:
    engine, state = initialized()

    view = engine.player_view(with_entity(state, SECRET))

    here = next(panel for panel in view.panels if panel.title == "Also here")
    icon_ids = {row.icon_id for row in here.rows}
    assert "mara" in icon_ids
    assert all(row.name != "The Secret" for panel in view.panels for row in panel.rows)
