from collections.abc import Callable, Mapping
from dataclasses import dataclass

from pydantic import BaseModel, JsonValue

from aidm.state.model import Scenario, WorldState


@dataclass(frozen=True, slots=True)
class AuthoringTool:
    name: str
    description: str
    args: type[BaseModel]
    apply: Callable[[WorldState, Mapping[str, JsonValue]], str]


@dataclass(frozen=True, slots=True)
class AuthoringBrief:
    bar_prompt: str
    guidance: str
    unmet: Callable[[Scenario], list[str]]
    settled: frozenset[str] = frozenset()
    tools: tuple[AuthoringTool, ...] = ()
