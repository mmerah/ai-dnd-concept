from aidm.core.entities import EntityId
from aidm.core.play import Exchange, PendingDecision, PendingOption, SpokenLine
from aidm.core.views import PlayerView, Subject
from aidm.ui.game import can_type, standing_proposal

WREN = Subject(id=EntityId("player"), name="Wren", brief="A quiet scout")


def _view(prompt: PendingDecision | None = None, over: str | None = None) -> PlayerView:
    return PlayerView(player=WREN, panels=(), prompt=prompt, action=None, over=over)


def _pick(*, allows_text: bool) -> PendingDecision:
    return PendingDecision(
        kind="pick",
        prompt="Which door?",
        options=(PendingOption(id="left", label="Left", name="pick"),),
        allows_text=allows_text,
    )


def test_the_composer_opens_only_between_turns_on_a_game_still_going() -> None:
    assert can_type(_view(), None)
    assert not can_type(_view(), "master")
    assert not can_type(_view(prompt=_pick(allows_text=False)), None)
    assert can_type(_view(prompt=_pick(allows_text=True)), None)
    assert not can_type(_view(over="Wren is dead"), None)


def _spoken(*, proposal: str = "") -> Exchange:
    return Exchange(
        prompt="(the party speaks)",
        lines=(SpokenLine(speaker_id=EntityId("vessa-rune"), speaker="Vessa", text="Wait."),),
        proposal=proposal,
    )


def test_standing_proposal_holds_the_newest_proposal_between_turns_only() -> None:
    proposed = (_spoken(proposal="I check the door."),)

    assert standing_proposal(proposed, _view(), None) == proposed[-1]
    assert standing_proposal(proposed, _view(), "master") is None
    assert standing_proposal(proposed, _view(prompt=_pick(allows_text=True)), None) is None
    assert standing_proposal((_spoken(),), _view(), None) is None
