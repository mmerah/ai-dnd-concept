import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import UnionType
from typing import Annotated, Literal, TypeAliasType, Union, get_args, get_origin

from annotated_types import MaxLen
from pydantic import Field, TypeAdapter
from pydantic.fields import FieldInfo

from aidm.state.base import Frozen, Slug
from aidm.state.effects import WorldEffect
from aidm.state.plan import DirectorBeat, RuleCall

ROLLS_CARD = (
    "What a `roll` may name, and the `args` each one takes. One roll at most per beat, and only "
    "what the list below spells."
)
EFFECTS_CARD = (
    "What an `effects` entry may name, and the `args` each one takes. A beat writes as many as "
    "the fiction causes, or none."
)


@dataclass(frozen=True, slots=True)
class TypedBeat:
    roll: Frozen | None
    effects: tuple[Frozen, ...]


def translate(
    beat: DirectorBeat, actions: Mapping[Slug, type[Frozen]], effects: TypeAdapter[Frozen]
) -> TypedBeat:
    """Authored examples come through here too, so prose and the wire share one gate."""
    return TypedBeat(
        roll=None if beat.roll is None else _roll(beat.roll, actions),
        effects=tuple(translate_effect(call, effects) for call in beat.effects),
    )


def translate_effect(call: RuleCall, effects: TypeAdapter[Frozen]) -> Frozen:
    # Spread last: an `op` smuggled into `args` must not rename the call.
    return effects.validate_python({**call.args, "op": call.name})


def _roll(call: RuleCall, actions: Mapping[Slug, type[Frozen]]) -> Frozen:
    model = actions.get(call.name)
    if model is None:
        raise ValueError(
            f"this engine has no roll named {call.name!r}. Its rolls are: {', '.join(actions)}"
        )
    return model.model_validate(call.args)


def card(title: str, intro: str, calls: Mapping[Slug, type[Frozen]]) -> str:
    """Rendered from the models that validate it, so prose cannot drift from what a retry says."""
    entries = [f"`{name}` — {_summary(model)}\n{_args(model)}" for name, model in calls.items()]
    return "\n\n".join([f"## {title}", intro, *entries])


def _summary(model: type[Frozen]) -> str:
    return " ".join((model.__doc__ or "").split())


def _args(model: type[Frozen]) -> str:
    lines = [
        f"  - `{name}` ({_marks(field)}) — {field.description or ''}".rstrip()
        for name, field in model.model_fields.items()
        if name != "op"
    ]
    return "\n".join(lines) or "  - (no arguments)"


def _marks(field: FieldInfo) -> str:
    known = (_shape(field), "required" if field.is_required() else _default(field))
    return "; ".join(mark for mark in known if mark)


def _default(field: FieldInfo) -> str:
    return f"default {json.dumps(field.get_default(call_default_factory=True))}"


def _shape(field: FieldInfo) -> str:
    if choices := _literals(field.annotation):
        return "one of " + ", ".join(f"`{choice}`" for choice in choices)
    if not _is_list(field.annotation):
        return ""
    capped = next((mark.max_length for mark in field.metadata if isinstance(mark, MaxLen)), None)
    return "list" if capped is None else f"list of at most {capped}"


def _literals(annotation: object) -> tuple[str, ...]:
    inner = _unwrapped(annotation)
    origin = get_origin(inner)
    if origin is Literal:
        return tuple(str(choice) for choice in get_args(inner))
    if origin in (Union, UnionType):
        return tuple(choice for member in get_args(inner) for choice in _literals(member))
    return ()


def _is_list(annotation: object) -> bool:
    return get_origin(_unwrapped(annotation)) is tuple


def _unwrapped(annotation: object) -> object:
    if isinstance(annotation, TypeAliasType):
        return _unwrapped(annotation.__value__)
    if get_origin(annotation) is Annotated:
        return _unwrapped(get_args(annotation)[0])
    return annotation


def _members(annotation: object) -> tuple[type[Frozen], ...]:
    inner = _unwrapped(annotation)
    if members := get_args(inner):
        return tuple(model for member in members for model in _members(member))
    if isinstance(inner, type) and issubclass(inner, Frozen):
        return (inner,)
    raise TypeError(f"{annotation} is no union of call models")


# Derived from the union, so an op the adapter takes cannot be missing from the card.
WORLD_CALLS: Mapping[Slug, type[Frozen]] = {
    str(model.model_fields["op"].default): model for model in _members(WorldEffect)
}


def effect_adapter(own: Mapping[Slug, type[Frozen]]) -> TypeAdapter[Frozen]:
    members = (WorldEffect, *own.values())
    # A dynamic Union: the engine's declaration is the single source, so card and adapter cannot
    # drift. Nesting the already-discriminated WorldEffect keeps retry errors naming the exact
    # field (see PROGRESS.md, Phase 1 step 1).
    union = Union[members]  # pyright: ignore[reportInvalidTypeArguments] # noqa: UP007
    return TypeAdapter(Annotated[union, Field(discriminator="op")])
