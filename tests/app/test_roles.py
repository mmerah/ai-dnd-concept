import logging
from dataclasses import dataclass
from random import Random

import pytest
from support.game import initialized

from aidm.app.roles import ask, run_master
from aidm.app.spawn import RunResult
from aidm.config import Role
from aidm.core.entities import Refusal
from aidm.core.play import Answer, Narration
from aidm.turn import Turn


@dataclass(slots=True)
class _AlwaysRefuses:
    calls: int = 0

    async def run(
        self, role: Role, prompt: str, conversation: str | None, tools: Turn | None = None
    ) -> RunResult:
        del role, prompt, conversation, tools
        self.calls += 1
        raise Refusal("boom")


def _turn_of() -> Turn:
    engine, state = initialized()
    return Turn.begin(engine, state, Answer(text="I wait."), Random(0))


async def test_a_master_that_lands_nothing_is_asked_once_not_retried() -> None:
    turn = _turn_of()
    spawner = _AlwaysRefuses()

    with pytest.raises(Refusal, match="boom"):
        await run_master(spawner, turn)

    assert spawner.calls == 1


async def test_a_master_that_already_landed_facts_is_not_retried_and_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    turn = _turn_of()
    _ = turn.call(
        "change_tags", {"actor_id": "player", "kind": "condition", "gained": ["Listening"]}
    )
    spawner = _AlwaysRefuses()

    with caplog.at_level(logging.WARNING, logger="aidm.app.roles"):
        await run_master(spawner, turn)

    assert spawner.calls == 1
    assert "applying 1 facts" in caplog.text


async def test_a_retry_carries_on_the_refused_attempt_and_sends_only_the_error() -> None:
    asked: list[tuple[str, str | None]] = []

    class _Spawner:
        async def run(
            self, role: Role, prompt: str, conversation: str | None, tools: Turn | None = None
        ) -> RunResult:
            del role, tools
            asked.append((prompt, conversation))
            return RunResult('{"lines": []}' if conversation else "not json", "abc-123")

    _ = await ask(_Spawner(), "narrator", "THE WHOLE BRIEF", Narration, lambda _: None)

    assert asked[0] == ("THE WHOLE BRIEF", None)
    assert asked[1][1] == "abc-123"
    assert "THE WHOLE BRIEF" not in asked[1][0]


async def test_a_spawn_that_refuses_once_still_gets_its_one_retry() -> None:
    attempts: list[str | None] = []

    class _Spawner:
        async def run(
            self, role: Role, prompt: str, conversation: str | None, tools: Turn | None = None
        ) -> RunResult:
            del role, prompt, tools
            attempts.append(conversation)
            if len(attempts) == 1:
                raise Refusal("the narrator exited 1")
            return RunResult('{"lines": []}', "abc-123")

    answer = await ask(_Spawner(), "narrator", "PROMPT", Narration, lambda _: None)

    assert answer == Narration(lines=())
    assert attempts == [None, None]


async def test_answered_nothing_usable_does_not_quote_the_checks_message() -> None:
    class _Spawner:
        async def run(
            self, role: Role, prompt: str, conversation: str | None, tools: Turn | None = None
        ) -> RunResult:
            del role, prompt, tools
            return RunResult('{"lines": []}', conversation or "abc-123")

    def _check(_: Narration) -> None:
        raise Refusal("a scene that does not name what is hidden: ['Bell']")

    with pytest.raises(Refusal, match="the narrator answered nothing usable") as failed:
        _ = await ask(_Spawner(), "narrator", "PROMPT", Narration, _check)

    assert "Bell" not in str(failed.value)
