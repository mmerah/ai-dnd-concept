from collections.abc import Callable

import pytest
from pydantic import ValidationError
from support.game import MARA, initialized, with_entity
from support.table import ENGINE_IDS, game
from support.tunnelgoons import ENGINE as TUNNELGOONS_ENGINE
from support.tunnelgoons import MIRA as TUNNELGOONS_MIRA
from support.tunnelgoons import small_world as tunnelgoons_world

from aidm.core.entities import EngineId, Refusal, Slug
from aidm.core.play import Interjection, Line, SpokenLine
from aidm.core.views import NarratorView, Subject
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.world import Loner3eCast

SECRET = Loner3eCast(
    id="hidden-actor",
    name="The Secret",
    brief="Unrevealed canon.",
    concept="A Watcher",
)

OBJECT = Loner3eCast(
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
    _ = draft.payload.kill(MARA)
    return engine.narrator_view(draft), MARA


def _tunnelgoons_dead_view() -> tuple[NarratorView, Slug]:
    state = tunnelgoons_world()
    state.payload.npcs[TUNNELGOONS_MIRA].alive = False
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


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_the_player_is_never_listed_as_someone_else_here(engine_id: EngineId) -> None:
    engine, state = game(engine_id)

    here = next(panel for panel in engine.player_view(state).panels if panel.title == "Also here")
    assert all(row.icon_id != PLAYER_ID for row in here.rows)

    sections = dict(engine.master_sections(state))
    assert f"[{PLAYER_ID}]" not in sections["HERE WITH THE PLAYER"]


def test_everyone_known_and_present_may_speak() -> None:
    """SRD "Everything is a Character": a thing present and known is a speaker too."""
    engine, state = initialized()

    view = engine.narrator_view(with_entity(state, OBJECT))

    assert OBJECT.id in view.speakers


def test_a_narrator_view_naming_a_speaker_who_is_not_a_subject_is_refused() -> None:
    subject = Subject(id="mara", label="Mara", detail="A ferrywoman.")
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


def test_a_narrator_views_party_refuses_a_stranger_or_a_repeat_and_others_excludes_it() -> None:
    subject = Subject(id="mara", label="Mara", detail="A ferrywoman.")
    other = Subject(id="kael", label="Kael", detail="")

    with pytest.raises(ValidationError, match="not subjects"):
        _ = NarratorView(
            place="p",
            title="t",
            focus="f",
            situation="s",
            subjects=(subject,),
            speakers=(),
            party=("stranger",),
            sheet=(),
        )
    with pytest.raises(ValidationError, match="duplicate party members"):
        _ = NarratorView(
            place="p",
            title="t",
            focus="f",
            situation="s",
            subjects=(subject, other),
            speakers=(),
            party=(other.id, other.id),
            sheet=(),
        )

    view = NarratorView(
        place="p",
        title="t",
        focus="f",
        situation="s",
        subjects=(subject, other),
        speakers=(),
        party=(other.id,),
        sheet=(),
    )
    assert view.others() == (subject,)


def test_a_spoken_line_names_its_speaker_or_nobody() -> None:
    with pytest.raises(ValidationError, match="names its speaker"):
        _ = SpokenLine(speaker_id="kael", text="Hello.")
    with pytest.raises(ValidationError, match="names its speaker"):
        _ = SpokenLine(speaker="Kael", text="Hello.")


def test_spoken_refuses_a_subject_who_is_not_a_speaker() -> None:
    subject = Subject(id="mara", label="Mara", detail="A ferrywoman.")
    view = NarratorView(
        place="p",
        title="t",
        focus="f",
        situation="s",
        subjects=(subject,),
        speakers=(),
        party=(subject.id,),
        sheet=(),
    )

    with pytest.raises(Refusal, match="nobody here has id"):
        view.spoken((Line(speaker_id="mara", text="Hello."),))


def test_check_interjection_accepts_the_members_own_lines_and_refuses_the_rest() -> None:
    member_id = "mara"
    accepted = Interjection(
        lines=(Line(speaker_id=member_id, text="Careful."),), proposal="I check the door."
    )
    stranger = Interjection(lines=(Line(speaker_id="kael", text="Careful."),))
    bare_proposal = Interjection(lines=(), proposal="I check the door.")

    subject = Subject(id=member_id, label="Mara", detail="A ferrywoman.")
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


def test_a_proposal_is_stripped_so_accept_plays_what_the_composer_would() -> None:
    assert Interjection(lines=(), proposal="  ").proposal == ""


def test_the_player_view_panels_carry_icon_ids_for_who_else_is_here() -> None:
    engine, state = initialized()

    view = engine.player_view(with_entity(state, SECRET))

    here = next(panel for panel in view.panels if panel.title == "Also here")
    icon_ids = {row.icon_id for row in here.rows}
    assert "mara" in icon_ids
    assert all(row.label != "The Secret" for panel in view.panels for row in panel.rows)
