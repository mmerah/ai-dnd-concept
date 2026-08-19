import json

import pytest

from aidm.llm import repaired

HURT = "A painful sprain from straining against the vault's lock."
TRUNCATED = f'{{\n  "entity_id": "player",\n  "trait_id": "injured-hand",\n  "text": "{HURT}"\n'


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (TRUNCATED, {"entity_id": "player", "trait_id": "injured-hand", "text": HURT}),
        ('{"queries": ["chart", "vault"', {"queries": ["chart", "vault"]}),
        ('{"need": "a way down', {"need": "a way down"}),
        ('{"amount": 3}', {"amount": 3}),
    ],
)
def test_unterminated_arguments_are_closed(args: str, expected: dict[str, object]) -> None:
    assert json.loads(repaired(args)) == expected


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ('```json\n{"amount": 3}\n```', {"amount": 3}),
        ('"{\\"amount\\": 3}"', {"amount": 3}),
        ('{"queries": ["chart",', {"queries": ["chart"]}),
    ],
)
def test_wrapped_arguments_are_unwrapped(args: str, expected: dict[str, object]) -> None:
    assert json.loads(repaired(args)) == expected


@pytest.mark.parametrize("args", ["", '{"amount":', "not json at all", '["chart"]', '"hello"'])
def test_arguments_no_small_repair_saves_are_left_alone(args: str) -> None:
    assert repaired(args) == args
