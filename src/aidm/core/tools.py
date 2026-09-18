import json
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from inspect import cleandoc, signature
from random import Random
from types import FunctionType

from pydantic import BaseModel, JsonValue

from aidm.core.entities import Frozen, parse_json
from aidm.core.facts import Fact
from aidm.core.model import AnyGame

NOISE_KEYS = ("title", "pattern", "maxLength", "minLength")
_MARKED: dict[Callable[..., object], type[BaseModel]] = {}


# No docstring: pydantic would publish it as the schema's `description`.
class NoArgs(Frozen):
    pass


@dataclass(frozen=True, slots=True)
class MasterTool:
    name: str
    description: str
    args: type[BaseModel]
    call: Callable[[AnyGame, JsonValue, Random], tuple[Fact, ...]]


def tool[F: Callable[..., Sequence[Fact]]](method: F) -> F:
    """The method docstring is the text the master reads."""
    if not (method.__doc__ or "").strip():
        raise ValueError(f"{method.__qualname__} carries no description")
    args = _args_of(method)
    if bare := [key for key, info in args.model_fields.items() if not info.description]:
        raise ValueError(
            f"{method.__qualname__} parameters the model reads carry no description: {bare}"
        )
    _MARKED[method] = args
    return method


def tools_of(engine: object) -> dict[str, MasterTool]:
    """Definition order, base class first; a name defined again keeps the slot it first took."""
    marked: dict[str, FunctionType] = {}
    for cls in reversed(type(engine).__mro__):
        members: Mapping[str, object] = vars(cls)
        for name, value in members.items():
            if not isinstance(value, FunctionType):
                continue
            if value in _MARKED:
                marked[name] = value
            elif name in marked:
                raise ValueError(f"{value.__qualname__} overrides a tool but carries no @tool mark")
    return {name: _published(engine, name, function) for name, function in marked.items()}


def schema_of(args: type[BaseModel]) -> dict[str, JsonValue]:
    """One schema function, so what MCP publishes is what every prompt describes."""
    schema = args.model_json_schema()
    defs = schema.pop("$defs", {})
    _inline_refs(schema, defs)
    _normalize(schema)
    return schema


def schema_text(model: type[BaseModel]) -> str:
    return json.dumps(schema_of(model), indent=2, ensure_ascii=False)


def _published(engine: object, name: str, function: FunctionType) -> MasterTool:
    """The bound method resolves an override; the marked function carries the text and the model."""
    args = _MARKED[function]
    bound: Callable[[AnyGame, BaseModel, Random], Sequence[Fact]] = getattr(engine, name)

    def call(draft: AnyGame, raw: JsonValue, rng: Random) -> tuple[Fact, ...]:
        return tuple(bound(draft, parse_json(args, json.dumps(raw)), rng))

    # One line: the master reads a description, not the source's wrapping.
    return MasterTool(name, " ".join(cleandoc(function.__doc__ or "").split()), args, call)


def _args_of(function: Callable[..., object]) -> type[BaseModel]:
    parameters = list(signature(function).parameters.values())
    args = parameters[2] if len(parameters) > 2 else None
    if args is not None and args.name.removeprefix("_") == "args":
        annotation: object = args.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return annotation
    raise ValueError(f"{function.__qualname__} does not take (self, draft, args, rng)")


def _inline_refs(node: JsonValue, defs: Mapping[str, JsonValue]) -> None:
    """A `$ref` becomes its definition: the model reads one tree and no class name leaks in."""
    if isinstance(node, list):
        for item in node:
            _inline_refs(item, defs)
        return
    if not isinstance(node, dict):
        return
    ref = node.pop("$ref", None)
    if isinstance(ref, str):
        target = defs[ref.removeprefix("#/$defs/")]
        if isinstance(target, dict):
            for key, value in target.items():
                node.setdefault(key, deepcopy(value))
    for value in node.values():
        _inline_refs(value, defs)


def _normalize(node: JsonValue) -> None:
    if isinstance(node, list):
        for item in node:
            _normalize(item)
        return
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        # A `properties` map is keyed by names, which may spell a noise key.
        if key == "properties" and isinstance(value, dict):
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
