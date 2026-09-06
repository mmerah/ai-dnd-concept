import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from random import Random
from typing import Any

from pydantic import BaseModel, Field, JsonValue

from aidm.core.entities import Frozen, parse
from aidm.core.facts import Fact
from aidm.core.model import Game

# The rng is a parameter so a trial run against a throwaway copy cannot consume the turn's dice.
type Play[G: Game[Any]] = Callable[[G, Random], tuple[Fact, ...]]
NOISE_KEYS = ("title", "pattern", "maxLength", "minLength", "discriminator")


class Attempt(Frozen):
    """`what` is read by the player; what they must not learn goes in a master-only field."""

    what: str = Field(
        min_length=1,
        description="The attempt, in a few words the player may read; it heads the card.",
    )


@dataclass(frozen=True, slots=True)
class MasterTool[G: Game[Any]]:
    name: str
    description: str
    args: type[BaseModel]
    call: Callable[[G, Mapping[str, JsonValue], Random], tuple[Fact, ...]]


def master_tool[G: Game[Any], A: BaseModel](
    name: str,
    description: str,
    args: type[A],
    resolve: Callable[[G, A, Random], Sequence[Fact]],
) -> MasterTool[G]:
    if bare := [key for key, info in args.model_fields.items() if not info.description]:
        raise ValueError(f"{name} parameters the model reads carry no description: {bare}")

    def call(draft: G, raw: Mapping[str, JsonValue], rng: Random) -> tuple[Fact, ...]:
        return tuple(resolve(draft, parse(args, raw), rng))

    return MasterTool(name, description, args, call)


def schema_of(args: type[BaseModel]) -> dict[str, JsonValue]:
    """One schema function, so what MCP publishes is what every prompt describes."""
    schema = args.model_json_schema()
    _normalize(schema)
    return schema


def schema_text(model: type[BaseModel]) -> str:
    return json.dumps(schema_of(model), indent=2, ensure_ascii=False)


def _normalize(node: JsonValue) -> None:
    """Drop what the model reads for free from parsing, and fold `T | None` to one node."""
    if isinstance(node, list):
        for item in node:
            _normalize(item)
        return
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        # A `properties` or `$defs` map is keyed by names, which may spell a noise key.
        if key in ("properties", "$defs") and isinstance(value, dict):
            for child in value.values():
                _normalize(child)
        else:
            _normalize(value)
    for key in NOISE_KEYS:
        node.pop(key, None)
    _collapse_nullable(node)


def _collapse_nullable(node: dict[str, JsonValue]) -> None:
    members = node.get("anyOf")
    if not isinstance(members, list) or len(members) != 2:
        return
    branches = [member for member in members if member != {"type": "null"}]
    if len(branches) != 1:
        return
    branch = branches[0]
    if not isinstance(branch, dict) or not isinstance(branch.get("type"), str):
        return
    rest = {key: value for key, value in node.items() if key != "anyOf"}
    node.clear()
    node.update(branch)
    node["type"] = [branch["type"], "null"]
    node.update(rest)
