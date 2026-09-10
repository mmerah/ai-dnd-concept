from aidm.app.roles import render_interjection
from aidm.core.entities import EntityId
from aidm.core.views import NarratorView, Subject


def _view(subject: Subject) -> NarratorView:
    return NarratorView(
        place="p",
        title="t",
        focus="",
        situation="s",
        subjects=(subject,),
        speakers=(subject.id,),
        party=(subject.id,),
        sheet=(),
    )


def test_render_interjection_prints_the_members_own_sheet_or_none() -> None:
    mara = Subject(id=EntityId("mara"), label="Mara", detail="A ferrywoman.")

    with_sheet = render_interjection(_view(mara), mara, (("Skill", "Stealth d8"),), (), "")
    without_sheet = render_interjection(_view(mara), mara, (), (), "")

    assert "YOUR SHEET:\n- Skill: Stealth d8" in with_sheet
    assert "YOUR SHEET:\n(none)" in without_sheet
