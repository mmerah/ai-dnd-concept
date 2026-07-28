"""The tests' composition root: the shipped pack, the ruleset compiled from it, and a real game.

The same wiring as `aidm/bootstrap.py` minus the saves directory, so a test that wants a real world
does not need one — and cached, so the whole suite compiles the pack once. Every value it returns is
frozen, which is what makes sharing them safe."""

import json
from collections.abc import Callable, Mapping
from contextlib import ExitStack
from functools import cache
from pathlib import Path

from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.agents import creator as creator_module
from aidm.agents import director as director_module
from aidm.agents import maintainer as maintainer_module
from aidm.agents import narrator as narrator_module
from aidm.config import settings
from aidm.content import Content, Pack, loaded, read_pack
from aidm.content.records import Collection, Record, Slug
from aidm.domain.models import CharacterSheet, GameState, ScenarioDef
from aidm.engine import campaign
from aidm.engine.pack_ruleset import compile_ruleset
from aidm.engine.ruleset import Ruleset
from aidm.pipeline import TurnOptions
from aidm.store import read_scenario, read_sheet

PACK_DIR = settings().packs[0]
SCENARIO = "whispering_vault"
CHARACTER = "kael"
OPTIONS = TurnOptions(history_window=6, max_growth=3)

Stub = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


@cache
def pack(directory: Path = PACK_DIR) -> Pack:
    """The shipped pack as authored, for the tests that assert the corpus rather than play it.
    Cached per directory so the whole suite parses ~1,900 records once."""
    return read_pack(directory)


@cache
def content() -> Content:
    return loaded([pack(d) for d in settings().packs])


def all_of[R: Record](pack: Pack, name: Collection, kind: type[R]) -> Mapping[Slug, R]:
    """One collection of a pack, narrowed to the class the caller names. Here rather than on `Pack`
    because only the corpus tests read a pack by collection; the application reads `Content`."""
    found = pack.records.get(name, {})
    if wrong := sorted(i for i, r in found.items() if not isinstance(r, kind)):
        raise ValueError(f"{name} holds records that are no {kind.__name__}: {wrong}")
    return {i: r for i, r in found.items() if isinstance(r, kind)}


@cache
def ruleset() -> Ruleset:
    return compile_ruleset(content())


@cache
def sheet(character: str = CHARACTER) -> CharacterSheet:
    return read_sheet(settings().characters_dir / f"{character}.json")


@cache
def scenario(name: str = SCENARIO) -> ScenarioDef:
    return read_scenario(settings().scenarios_dir / f"{name}.json")


@cache
def new_game(name: str = SCENARIO, character: str = CHARACTER) -> GameState:
    """A composed level-1 game: the scenario's canon, statted, with the sheet placed in it."""
    return campaign.begin(scenario(name), sheet(character), ruleset(), content().stamps)


def structured(**output: object) -> Stub:
    """Structured roles use NativeOutput, so the model replies with schema-shaped JSON text."""

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(output))])

    return stub


def text(body: str) -> Stub:
    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(body)])

    return stub


def stubs(
    stack: ExitStack,
    *,
    director: Stub | None = None,
    narrator: Stub | None = None,
    maintainer: Stub | None = None,
    creator: Stub | None = None,
) -> None:
    """Pydantic AI's own seam, one role at a time. Explicit per-role params, so a renamed role
    module is a type error rather than a KeyError."""
    for module, stub in (
        (director_module, director),
        (narrator_module, narrator),
        (maintainer_module, maintainer),
        (creator_module, creator),
    ):
        if stub is not None:
            stack.enter_context(module.agent().override(model=FunctionModel(stub)))
