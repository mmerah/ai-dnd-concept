import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from random import Random

import pytest
from httpx import HTTPStatusError, Request, Response
from pydantic import JsonValue
from support.game import initialized
from support.table import ENGINES_BUILT, LONER3E, offline_settings, updated

from aidm.app.spawn import RoleRunner
from aidm.config import RoleConfig, RoleSettings, Settings
from aidm.core.entities import Refusal
from aidm.core.model import AnyGame
from aidm.core.tools import MasterTool, schema_of

CHANGE_TAGS = ENGINES_BUILT[LONER3E].tools["change_tags"]
TRACE = "- the player Kael[player] gained the tag Listening"
FENCED = '```json\n{"lines": []}\n```'
_, STATE = initialized()


@dataclass(slots=True)
class _Tools:
    state: AnyGame
    calls: list[tuple[str, JsonValue]] = field(default_factory=list)

    def published_tools(self) -> Sequence[MasterTool]:
        return (CHANGE_TAGS,)

    def call(self, name: str, raw: JsonValue) -> str:
        if name != CHANGE_TAGS.name:
            raise Refusal(f"{name!r} is not a tool of the 'loner3e' engine.")
        _ = CHANGE_TAGS.call(self.state.draft(), raw, Random(0))
        self.calls.append((name, raw))
        return TRACE


def _settings(**roles: RoleConfig) -> Settings:
    return updated(offline_settings(), roles=RoleSettings(**roles).model_dump())


def _post(
    monkeypatch: pytest.MonkeyPatch, *replies: JsonValue | Exception
) -> list[dict[str, JsonValue]]:
    queued, sent = list(replies), list[dict[str, JsonValue]]()

    async def scripted(
        _provider: object, path: str, body: Mapping[str, JsonValue], _timeout: float
    ) -> bytes:
        assert path == "/chat/completions"
        # Snapshotted as the wire would see it: the loop appends to the same list afterwards.
        sent.append(deepcopy(dict(body)))
        reply = queued.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return json.dumps(reply).encode()

    monkeypatch.setattr("aidm.app.builtin.post_bearer", scripted)
    return sent


def _said(content: str | None, *tool_calls: JsonValue, **extra: JsonValue) -> JsonValue:
    message: dict[str, JsonValue] = {"role": "assistant", "content": content, **extra}
    if tool_calls:
        message["tool_calls"] = list(tool_calls)
    return {"choices": [{"message": message}]}


def _call(call_id: str, name: str, arguments: str) -> JsonValue:
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def _messages(body: dict[str, JsonValue]) -> list[JsonValue]:
    messages = body["messages"]
    assert isinstance(messages, list)
    return messages


async def test_the_master_plays_its_tools_in_process_and_echoes_each_reply_whole(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    change = {
        "actor_id": "player",
        "kind": "condition",
        "gained": ["Listening"],
    }
    arguments = json.dumps(change)
    first = _said(
        None,
        _call("a", "change_tags", arguments),
        _call("b", "change_tags", "[1]"),
        _call("c", "next_scene", "{}"),
        reasoning_details=[{"type": "reasoning.text", "text": "thinking"}],
    )
    sent = _post(monkeypatch, first, _said("Done."))
    tools = _Tools(STATE)

    spoken = await RoleRunner(_settings(master=RoleConfig(provider="local", model="m"))).run(
        "master", "PLAY", None, tools
    )

    assert spoken.text == "Done."
    assert tools.calls == [("change_tags", change)]
    assert sent[0]["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "change_tags",
                "description": CHANGE_TAGS.description,
                "parameters": schema_of(CHANGE_TAGS.args),
            },
        }
    ]
    user, echoed, *answers = _messages(sent[1])
    assert user == {"role": "user", "content": "PLAY"}
    assert echoed == {
        "role": "assistant",
        "reasoning_details": [{"type": "reasoning.text", "text": "thinking"}],
        "tool_calls": [
            _call("a", "change_tags", arguments),
            _call("b", "change_tags", "[1]"),
            _call("c", "next_scene", "{}"),
        ],
    }
    assert answers[0] == {"role": "tool", "tool_call_id": "a", "content": TRACE}
    refused = answers[1]
    assert isinstance(refused, dict)
    assert refused["tool_call_id"] == "b"
    assert "Input should be an object" in str(refused["content"])
    assert answers[2] == {
        "role": "tool",
        "tool_call_id": "c",
        "content": "'next_scene' is not a tool of the 'loner3e' engine.",
    }


async def test_a_master_still_calling_tools_past_the_cap_is_cut_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endless = _said(None, _call("a", "change_tags", "{}"))
    sent = _post(monkeypatch, endless, endless, endless, endless)
    master = RoleConfig(provider="local", model="m", max_rounds=3)

    with pytest.raises(Refusal, match="3 rounds"):
        _ = await RoleRunner(_settings(master=master)).run("master", "PLAY", None, _Tools(STATE))
    assert len(sent) == 3


@pytest.mark.parametrize(
    ("reply", "expected"),
    (
        (
            HTTPStatusError(
                "404",
                request=Request("POST", "https://example.invalid/v1/chat/completions"),
                response=Response(404, text="No endpoints found for m"),
            ),
            "404: No endpoints found for m",
        ),
        ({"error": {"message": "insufficient credits"}}, "insufficient credits"),
        ({"choices": []}, "no choices"),
        ({"id": "x"}, "no choices"),
    ),
    ids=("http status", "error body", "no choices", "unreadable"),
)
async def test_a_failed_provider_refuses_in_words_the_player_reads(
    monkeypatch: pytest.MonkeyPatch, reply: JsonValue | Exception, expected: str
) -> None:
    _ = _post(monkeypatch, reply)

    with pytest.raises(Refusal, match=expected):
        _ = await RoleRunner(_settings(narrator=RoleConfig(provider="local", model="m"))).run(
            "narrator", "BRIEF", None, _Tools(STATE)
        )


async def test_a_writer_that_calls_a_tool_is_refused_before_anything_lands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = _post(monkeypatch, _said(None, _call("a", "change_tags", "{}")))

    with pytest.raises(Refusal, match="no tools, yet called 'change_tags'"):
        _ = await RoleRunner(_settings(narrator=RoleConfig(provider="local", model="m"))).run(
            "narrator", "BRIEF", None
        )
