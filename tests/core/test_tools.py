from random import Random
from typing import Literal

import pytest
from pydantic import Field

from aidm.core.entities import EngineId, Frozen
from aidm.core.facts import Fact
from aidm.core.model import AnyGame, Game, ScenarioMeta
from aidm.core.tools import schema_of, tool, tools_of

type Kind = Literal["gear", "condition"]


class Word(Frozen):
    word: str = Field(description="One word the master fills in.")


class Undescribed(Frozen):
    entity_id: str


class Marking:
    @tool
    def first(self, _draft: AnyGame, args: Word, _rng: Random) -> list[Fact]:
        """The first tool the base publishes."""
        return [Fact(trace=f"base first {args.word}")]

    @tool
    def second(self, _draft: AnyGame, args: Word, _rng: Random) -> list[Fact]:
        """The second tool the base publishes."""
        return [Fact(trace=f"base second {args.word}")]


class Adding(Marking):
    def second(self, _draft: AnyGame, args: Word, _rng: Random) -> list[Fact]:
        return [Fact(trace=f"override second {args.word}")]

    @tool
    def third(self, _draft: AnyGame, args: Word, _rng: Random) -> list[Fact]:
        """The tool the subclass adds."""
        return [Fact(trace=f"subclass third {args.word}")]


def test_the_published_order_is_the_bases_tools_then_the_subclasss() -> None:
    published = tools_of(Adding())

    assert list(published) == ["first", "second", "third"]

    draft: AnyGame = Game[Word](
        scenario_id="trial",
        character_id="player",
        scenario=ScenarioMeta(title="Trial", premise="A trial runs", scope="One trial"),
        engine=EngineId("trial"),
        pack_id="srd",
        world=Word(word="nothing"),
    )
    facts = published["second"].call(draft, {"word": "vest"}, Random(0))

    assert [fact.trace for fact in facts] == ["override second vest"]


def test_an_unmarked_override_reads_the_description_the_base_marked() -> None:
    assert tools_of(Adding())["second"].description == "The second tool the base publishes."


class Quiet:
    def touch(self, _draft: AnyGame, args: Word, _rng: Random) -> list[Fact]:
        return [Fact(trace=args.word)]


class Untyped:
    def touch(self, _draft: AnyGame, word: str, _rng: Random) -> list[Fact]:
        """Touch a thing."""
        return [Fact(trace=word)]


class Undescribing:
    def touch(self, _draft: AnyGame, args: Undescribed, _rng: Random) -> list[Fact]:
        """Touch a thing."""
        return [Fact(trace=args.entity_id)]


def test_a_method_with_no_description_is_refused_where_it_is_marked() -> None:
    with pytest.raises(ValueError, match="carries no description"):
        _ = tool(Quiet.touch)


def test_a_third_parameter_that_is_no_argument_model_is_refused_where_it_is_marked() -> None:
    with pytest.raises(ValueError, match="takes no argument model"):
        _ = tool(Untyped.touch)


def test_a_parameter_the_model_cannot_read_is_refused_where_it_is_marked() -> None:
    with pytest.raises(ValueError, match="carry no description"):
        _ = tool(Undescribing.touch)


def test_a_schema_is_one_tree_with_no_class_name_in_it() -> None:
    class Marked(Frozen):
        kind: Kind | None = None

    assert schema_of(Marked) == {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "kind": {"enum": ["gear", "condition"], "type": ["string", "null"], "default": None}
        },
    }
