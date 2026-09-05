from aidm.core.entities import EntityId
from aidm.core.play import PendingDecision, PendingOption
from aidm.core.views import PlayerView, Subject
from aidm.ui.game import can_type

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
