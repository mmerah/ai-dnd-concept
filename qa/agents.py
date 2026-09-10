"""Scripted stand-ins for the three AI roles, driven from the player's own words.

The master reads PLAYER ACTION from its prompt like the real one. A line that starts with `!` is
a script: `!roll what="Try the door" actor_id=player question="Does it give?"` calls that tool,
`!change verb=reveal entity_id=vault-map` wraps a `change_world` call, `!crash` and `!refuse`
fail the spawn, `!fail narrator` and `!bad worldsmith` arm a one-shot failure of another role.
Plain words with no script get one engine-appropriate roll, so dice show up in the page.

The narrator echoes what it was given, so every screenshot shows what the page was told. The
worldsmith answers each request shape with a small valid draft.
"""

import json
import logging
import re
import shlex
from asyncio import sleep
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import count
from typing import Literal

import httpx
from pydantic import JsonValue

from aidm.app.runtime import Runtime
from aidm.app.spawn import RunResult, Tools
from aidm.config import Role
from aidm.core.entities import Refusal

LOGGER = logging.getLogger("qa.agents")

type Transport = Literal["direct", "mcp"]
type Fault = Literal["fail", "bad", "slow"]

DEFAULT_ROLLS: dict[str, tuple[str, dict[str, JsonValue]]] = {
    "loner3e": (
        "roll",
        {
            "what": "Try it",
            "actor_id": "player",
            "question": "Does the player get what they want?",
        },
    ),
    "tunnelgoons": ("roll", {"what": "Try it", "ability": "skulker", "difficulty": 8}),
    "breathless": ("roll", {"what": "Try it", "skill": "think"}),
    "twentyfourxx": ("roll", {"what": "Try it", "skill": "Stealth"}),
}


@dataclass(slots=True)
class Spoken:
    role: Role
    prompt: str
    answer: str
    calls: list[tuple[str, dict[str, JsonValue], str]] = field(default_factory=list)
    error: str = ""


@dataclass(slots=True)
class ScriptedAgents:
    port: int
    transport: Transport = "direct"
    delay: float = 0.3
    runtime: Runtime | None = None
    faults: dict[Role, list[Fault]] = field(default_factory=dict)
    log: list[Spoken] = field(default_factory=list)
    scenes: "count[int]" = field(default_factory=lambda: count(1))

    async def run(
        self, role: Role, prompt: str, session: str | None, tools: Tools | None = None
    ) -> RunResult:
        del session, tools
        spoken = Spoken(role=role, prompt=prompt, answer="")
        self.log.append(spoken)
        await sleep(self.delay)
        try:
            spoken.answer = await self._answer(role, prompt, spoken)
        except (OSError, Refusal) as failed:
            spoken.error = f"{type(failed).__name__}: {failed}"
            raise
        return RunResult(spoken.answer, f"{role}-{len(self.log)}")

    async def _answer(self, role: Role, prompt: str, spoken: Spoken) -> str:
        armed = self.faults.get(role, [])
        if armed:
            fault = armed.pop(0)
            if fault == "fail":
                raise Refusal(f"scripted: the {role} failed")
            if fault == "slow":
                await sleep(6)
            if fault == "bad":
                return "not json at all"
        if role == "master":
            await self._master(prompt, spoken)
            return "done"
        if role == "narrator":
            return self._narrator(prompt)
        return self._worldsmith(prompt)

    async def _master(self, prompt: str, spoken: Spoken) -> None:
        action = _section(prompt, "PLAYER ACTION")
        scripts = [line[1:].strip() for line in action.splitlines() if line.startswith("!")]
        if not scripts:
            if "The player chose the option above" in action:
                return
            name, args = DEFAULT_ROLLS[self._engine_id()]
            await self._call(name, args, spoken)
            return
        for script in scripts:
            words = shlex.split(script)
            head, rest = words[0], words[1:]
            match head:
                case "crash":
                    raise OSError("scripted: the game master crashed")
                case "refuse":
                    raise Refusal("scripted: the game master refused")
                case "none":
                    continue
                case "fail" | "bad" | "slow":
                    role = _role(rest[0])
                    self.faults.setdefault(role, []).append(head)
                case "change":
                    await self._call("change_world", {"change": _args(rest)}, spoken)
                case _:
                    await self._call(head, _args(rest), spoken)

    async def _call(self, name: str, args: dict[str, JsonValue], spoken: Spoken) -> None:
        if self.transport == "mcp":
            answered = await self._mcp_call(name, args)
        else:
            try:
                answered = self._runtime().call(name, args)
            except Refusal as refused:
                answered = f"REFUSED: {refused}"
        spoken.calls.append((name, args, answered))
        LOGGER.info("master %s(%s) -> %s", name, json.dumps(args), answered.replace("\n", " | "))

    async def _mcp_call(self, name: str, args: dict[str, JsonValue]) -> str:
        body: dict[str, JsonValue] = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        }
        headers = {"Accept": "application/json, text/event-stream"}
        async with httpx.AsyncClient() as client:
            reply = await client.post(
                f"http://localhost:{self.port}/mcp/", json=body, headers=headers, timeout=30
            )
        result = reply.json()
        if "error" in result:
            return f"MCP ERROR: {result['error']}"
        content = result["result"]
        text = "\n".join(part["text"] for part in content.get("content", ()))
        return f"REFUSED: {text}" if content.get("isError") else text

    def _narrator(self, prompt: str) -> str:
        role = _section(prompt, "YOUR ROLE")
        if role.startswith("You are ") and "NARRATOR" not in role:
            member_id = re.search(r"Every `speaker_id` is `([^`]+)`", role)
            assert member_id is not None
            return json.dumps(
                {
                    "lines": [
                        {
                            "speaker_id": member_id.group(1),
                            "text": "[party] I have a thought about what we saw.",
                        }
                    ],
                    "proposal": "We follow the party member's suggestion.",
                }
            )
        happened = _section(prompt, "WHAT HAPPENED")
        action = _section(prompt, "PLAYER ACTION")
        speak = re.search(r'\[say (\S+) "([^"]*)"\]', action)
        lines: list[dict[str, JsonValue]] = [
            {"speaker_id": None, "text": f"[narration] {action[:80]}"},
            {"speaker_id": None, "text": f"[happened] {happened.replace(chr(10), ' ')[:400]}"},
        ]
        if speak is not None:
            lines.append({"speaker_id": speak.group(1), "text": speak.group(2)})
        return json.dumps({"lines": lines})

    def _worldsmith(self, prompt: str) -> str:
        schema = _section(prompt, "ANSWER WITH")
        number = next(self.scenes)
        if '"places"' in schema:
            opening = "(no map yet)" in prompt
            room = f"qa-room-{number}"
            return json.dumps(
                {
                    "start": room,
                    "places": {
                        room: {
                            "id": room,
                            "name": f"QA Room {number}",
                            "brief": "A test room.",
                            "known": opening,
                            "description": f"Room {number}, written by the scripted worldsmith.",
                        }
                    },
                    "ways": {},
                    "npcs": {
                        f"qa-npc-{number}": {
                            "id": f"qa-npc-{number}",
                            "name": f"QA Npc {number}",
                            "brief": "A test dweller.",
                            "known": opening,
                            "place": room,
                            "hp": {"current": 8, "maximum": 8},
                        }
                    },
                    "items": {},
                }
            )
        if '"abilities"' in schema:
            return json.dumps({"abilities": {"brute": 1, "skulker": 1, "erudite": 1}})
        if '"pronouns"' in schema:
            return json.dumps(
                {
                    "pronouns": "they/them",
                    "job": "Nurse",
                    "skills": {
                        "bash": 4,
                        "dash": 4,
                        "sneak": 4,
                        "shoot": 6,
                        "think": 8,
                        "sway": 10,
                    },
                    "item": "Baseball Bat",
                }
            )
        if '"specialty"' in schema:
            return json.dumps(
                {
                    "specialty": "Medic",
                    "skills": {"Medicine": 8},
                    "items": ["Med kit"],
                    "hindrances": [],
                }
            )
        scene: dict[str, JsonValue] = {
            "place": f"qa-place-{number}",
            "title": f"QA Scene {number}",
            "focus": f"Focus of scene {number}.",
            "situation": f"Scene {number}, written by the scripted worldsmith. Nothing is hidden.",
            "present": [f"qa-npc-{number}"],
            "hidden": [],
            "cast": {
                f"qa-npc-{number}": {
                    "id": f"qa-npc-{number}",
                    "name": f"QA Npc {number}",
                    "brief": "A test person.",
                }
            },
            "arc": "",
        }
        if '"recap"' in schema:
            scene["recap"] = f"Recap of the scene before {number}."
        return json.dumps(scene)

    def _runtime(self) -> Runtime:
        assert self.runtime is not None
        return self.runtime

    def _engine_id(self) -> str:
        playing = self._runtime().playing()
        assert playing is not None
        return playing.engine.id


def _section(prompt: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}[^\n]*:\n(.*?)(?=^\S[^\n]*:\n|\Z)", prompt, re.S | re.M)
    return match.group(1).strip() if match else ""


def _role(word: str) -> Role:
    match word:
        case "master" | "narrator" | "worldsmith":
            return word
        case _:
            raise Refusal(f"scripted: no role {word!r}")


def _args(words: Sequence[str]) -> dict[str, JsonValue]:
    args: dict[str, JsonValue] = {}
    for word in words:
        key, _, raw = word.partition("=")
        try:
            args[key] = json.loads(raw)
        except ValueError:
            args[key] = raw
    return args
