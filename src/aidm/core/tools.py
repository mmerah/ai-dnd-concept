from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from random import Random
from typing import Any

from pydantic import BaseModel, JsonValue

from aidm.core.entities import EntityId, Frozen
from aidm.core.facts import Fact
from aidm.core.model import Game

# The rng is a parameter so a trial run against a throwaway copy cannot consume the turn's dice.
type Play[G: Game[Any]] = Callable[[G, Random], tuple[Fact, ...]]
type Validate[G: Game[Any]] = Callable[[G], None]
type Known[G: Game[Any]] = Callable[[G, EntityId], bool | None]


class NoArgs(Frozen):
    pass


@dataclass(frozen=True, slots=True)
class MasterTool[G: Game[Any]]:
    name: str
    description: str
    args: type[BaseModel]
    call: Callable[[G, Mapping[str, JsonValue], Random], tuple[Fact, ...]]
    # World tools may still run in a turn that opened suspended; engine mechanics may not.
    during_suspension: bool = False


def master_tool[G: Game[Any], A: BaseModel](
    name: str,
    description: str,
    args: type[A],
    resolve: Callable[[G, A, Random], Sequence[Fact]],
    *,
    during_suspension: bool = False,
) -> MasterTool[G]:
    if bare := [key for key, one in args.model_fields.items() if not one.description]:
        raise ValueError(f"{name} parameters the model reads carry no description: {bare}")

    def call(draft: G, raw: Mapping[str, JsonValue], rng: Random) -> tuple[Fact, ...]:
        return tuple(resolve(draft, args.model_validate(raw), rng))

    return MasterTool(name, description, args, call, during_suspension)


def apply_to_draft[G: Game[Any]](
    validate: Validate[G],
    known: Known[G],
    draft: G,
    play: Play[G],
    rng: Random,
) -> tuple[Fact, ...]:
    """Every mutation runs this sequence, so no caller can skip the engine's own gate."""
    before = draft.pending
    landed = play(draft, rng)
    if before is not None and draft.pending is not before:
        raise ValueError("the rules already wait on a decision; they take one at a time")
    for fact in landed:
        if not fact.told or fact.entity_id is None:
            continue
        seen = known(draft, fact.entity_id)
        if seen is None:
            raise ValueError(f"a told fact names {fact.entity_id!r}, which the world does not hold")
        if not seen:
            raise ValueError(f"a told fact names {fact.entity_id!r}, whom the player has not met")
    validate(draft)
    return landed


def schema_of(args: type[BaseModel]) -> dict[str, JsonValue]:
    """One schema function, so what MCP publishes is what every prompt describes."""
    schema = args.model_json_schema()
    _drop_property_titles(schema)
    # The tool already names itself; the argument class name would be a second, wrong name.
    _ = schema.pop("title", None)
    return schema


def _drop_property_titles(node: JsonValue) -> None:
    """A field title only restates its name; a model title still names the arm `verb` selects."""
    if isinstance(node, dict):
        for name, value in node.items():
            if name == "properties" and isinstance(value, dict):
                for field in value.values():
                    if isinstance(field, dict):
                        _ = field.pop("title", None)
            _drop_property_titles(value)
    elif isinstance(node, list):
        for item in node:
            _drop_property_titles(item)
