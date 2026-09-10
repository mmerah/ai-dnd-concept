"""The MCP path: the master's tools over HTTP, as the CLI calls them. Run the server with
--transport mcp."""

import json
import sys
import urllib.request
from pathlib import Path
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).parent))
from drive import BASE, Session, cards, log, run, submit, wait_idle

GAMES = (
    "/game/whispering-vault/kael",
    "/game/buried-keep/kael",
    "/game/drowned-road/kael",
    "/game/silent-relay/kael",
)


class Tool(TypedDict):
    name: str


class Result(TypedDict, total=False):
    tools: list[Tool]
    isError: bool


class Reply(TypedDict, total=False):
    result: Result


def rpc(method: str, params: dict[str, object]) -> Reply:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    request = urllib.request.Request(
        BASE + "/mcp/",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    with urllib.request.urlopen(request) as reply:
        return json.load(reply)


def body(s: Session) -> None:
    # Between turns: no tools are published, and a call is refused with the wait line.
    listed = rpc("tools/list", {})
    s.note(f"tools between turns: {listed}")
    s.check(listed.get("result", {}).get("tools") == [], f"tools listed outside a turn: {listed}")
    called = rpc("tools/call", {"name": "roll", "arguments": {}})
    s.note(f"call between turns: {called}")
    result = called.get("result", {})
    s.check(
        result.get("isError") is True and "no turn is open" in json.dumps(result),
        f"call outside a turn: {called}",
    )
    page = s.page()
    for path in GAMES:
        page.goto(BASE + path)
        wait_idle(page, timeout=40)
        submit(page, "I try something.")
        # Mid-turn: the engine's tools are published.
        page.wait_for_timeout(300)
        listed = rpc("tools/list", {})
        names = [tool["name"] for tool in listed.get("result", {}).get("tools", [])]
        s.note(f"{path}: tools {names}")
        s.check(
            "change_world" in names and "roll" in names, f"tools not published mid-turn: {listed}"
        )
        wait_idle(page)
        spoken = [e for e in log() if e["role"] == "master"][-1]
        s.check(
            bool(spoken["calls"]) and not any("MCP ERROR" in c[2] for c in spoken["calls"]),
            f"mcp call failed: {spoken['calls']}",
        )
        s.check(
            any("→" in c or "oracle" in c for c in cards(page)),
            f"no roll card over mcp: {cards(page)[-2:]}",
        )
        submit(page, "I misuse a tool.\n!change verb=reveal entity_id=nobody\n!nonesuch a=1")
        wait_idle(page)
        spoken = [e for e in log() if e["role"] == "master"][-1]
        s.note(f"{path}: refusals {[c[2][:80] for c in spoken['calls']]}")
        s.check(
            all(c[2].startswith("REFUSED") for c in spoken["calls"]),
            f"bad calls not refused over mcp: {spoken['calls']}",
        )
        s.shot(page, path.split("/")[2])


run("mcp", body)
