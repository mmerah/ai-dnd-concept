from types import MappingProxyType

import pytest

from aidm.domain.engine import EngineData
from aidm.utils.models import EMPTY_FROZEN_MAP, Frozen, FrozenMap, updated


class _Defaulted(Frozen):
    entries: FrozenMap[str, int] = EMPTY_FROZEN_MAP


def test_a_defaulted_frozen_map_is_immutable() -> None:
    with pytest.raises(TypeError):
        _Defaulted().entries["added"] = 1  # pyright: ignore[reportIndexIssue]


def test_updated_validates_so_a_copied_payload_stays_frozen() -> None:
    data = EngineData.model_validate(
        {"engine": "story", "schema_version": 1, "payload": {"a": [1]}}
    )

    copied = updated(data, payload={"b": [2]})

    assert isinstance(copied.payload, MappingProxyType)
    with pytest.raises(TypeError):
        copied.payload["c"] = 3  # pyright: ignore[reportIndexIssue]


def test_engine_payload_is_recursively_immutable_and_json_round_trips() -> None:
    data = EngineData.model_validate(
        {
            "engine": "story",
            "schema_version": 1,
            "payload": {"nested": [{"count": 2, "active": True}]},
        }
    )

    assert isinstance(data.payload, MappingProxyType)
    nested = data.payload["nested"]
    assert isinstance(nested, tuple)
    item = nested[0]
    assert isinstance(item, MappingProxyType)

    with pytest.raises(TypeError):
        item["count"] = 3  # pyright: ignore[reportIndexIssue]

    assert (
        data.model_dump_json() == '{"engine":"story","schema_version":1,'
        '"payload":{"nested":[{"count":2,"active":true}]}}'
    )


@pytest.mark.parametrize("payload", [{1: "bad"}, {1, 2}, float("inf")])
def test_engine_payload_rejects_non_json_values(payload: object) -> None:
    with pytest.raises(ValueError):
        EngineData.model_validate({"engine": "story", "schema_version": 1, "payload": payload})
