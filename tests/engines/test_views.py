import pytest
from pydantic import ValidationError
from support.game import initialized, with_entity

from aidm.core.entities import EntityId, Refusal
from aidm.core.play import Interjection, Line, SpokenLine
from aidm.core.views import NarratorView, Subject
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.world import Loner3eSheet

SECRET = Loner3eSheet(
    id=EntityId("hidden-actor"),
    name="The Secret",
    brief="Unrevealed canon.",
    concept="A Watcher",
)

OBJECT = Loner3eSheet(
    id=EntityId("a-locked-chest"),
    name="A Locked Chest",
    brief="Iron-bound, and shut fast.",
    known=True,
)


def test_the_narrator_view_names_nobody_in_the_scene_the_player_has_not_met() -> None:
    engine, state = initialized()

    shown = str(engine.narrator_view(with_entity(state, SECRET)).model_dump())

    assert "The Secret" not in shown
    # The vault map is hidden here, and Mara is standing in the room.
    assert "vault map" not in shown
    assert "Mara" in shown


def test_everyone_known_and_present_may_speak() -> None:
    """SRD "Everything is a Character": a thing present and known is a speaker too."""
    engine, state = initialized()

    view = engine.narrator_view(with_entity(state, OBJECT))

    assert OBJECT.id in view.speakers


def test_a_narrator_view_naming_a_speaker_who_is_not_a_subject_is_refused() -> None:
    subject = Subject(id=EntityId("mara"), label="Mara", detail="A ferrywoman.")
    with pytest.raises(ValidationError, match="not subjects"):
        _ = NarratorView(
            place="p",
            title="t",
            focus="f",
            situation="s",
            subjects=(subject,),
            speakers=(EntityId("stranger"),),
            party=(subject.id,),
            sheet=(),
        )


def test_a_narrator_views_party_refuses_a_stranger_or_a_repeat_and_others_excludes_it() -> None:
    subject = Subject(id=EntityId("mara"), label="Mara", detail="A ferrywoman.")
    other = Subject(id=EntityId("kael"), label="Kael", detail="")

    with pytest.raises(ValidationError, match="not subjects"):
        _ = NarratorView(
            place="p",
            title="t",
            focus="f",
            situation="s",
            subjects=(subject,),
            speakers=(),
            party=(EntityId("stranger"),),
            sheet=(),
        )
    with pytest.raises(ValidationError, match="repeats"):
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
        _ = SpokenLine(speaker_id=EntityId("kael"), text="Hello.")
    with pytest.raises(ValidationError, match="names its speaker"):
        _ = SpokenLine(speaker="Kael", text="Hello.")


def test_spoken_refuses_a_subject_who_is_not_a_speaker() -> None:
    subject = Subject(id=EntityId("mara"), label="Mara", detail="A ferrywoman.")
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
        view.spoken((Line(speaker_id=EntityId("mara"), text="Hello."),))


def test_interjection_refusal_accepts_the_members_own_lines_and_refuses_the_rest() -> None:
    member_id = EntityId("mara")
    accepted = Interjection(
        lines=(Line(speaker_id=member_id, text="Careful."),), proposal="I check the door."
    )
    stranger = Interjection(lines=(Line(speaker_id=EntityId("kael"), text="Careful."),))
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

    assert view.interjection_refusal(member_id, accepted) is None
    assert view.interjection_refusal(member_id, stranger) == (
        f"only {member_id} speaks here: every `speaker_id` is {member_id!r}"
    )
    assert view.interjection_refusal(member_id, bare_proposal) == (
        "a proposal comes with at least one line of dialogue; keep quiet with no lines and no "
        "proposal"
    )


def test_a_proposal_is_stripped_so_accept_plays_what_the_composer_would() -> None:
    assert Interjection(lines=(), proposal="  ").proposal == ""


def test_the_player_view_panels_carry_icon_ids_for_who_else_is_here() -> None:
    engine, state = initialized()

    view = engine.player_view(with_entity(state, SECRET))

    assert tuple(panel.title for panel in view.panels) == (
        "Character",
        "This scene",
        "Also here",
        "Trail",
    )
    here = next(panel for panel in view.panels if panel.title == "Also here")
    icon_ids = {row.icon_id for row in here.rows}
    assert PLAYER_ID not in icon_ids
    assert EntityId("mara") in icon_ids
    assert all(row.label != "The Secret" for panel in view.panels for row in panel.rows)
