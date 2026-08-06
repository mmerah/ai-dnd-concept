import pytest
from pydantic import ValidationError

from aidm.state.sheet import (
    Counter,
    CounterTemplate,
    Sheet,
    SheetDefinition,
    SheetTag,
    SheetTemplate,
)


def test_counter_rejects_current_outside_its_bounds_and_clamps_in_both_directions() -> None:
    with pytest.raises(ValidationError, match="below minimum"):
        Counter(current=-1, minimum=0, maximum=10)
    with pytest.raises(ValidationError, match="above maximum"):
        Counter(current=11, minimum=0, maximum=10)

    held = Counter(current=5, minimum=0, maximum=10)
    assert held.clamped(-5) == 0
    assert held.clamped(50) == 10


def test_sheet_refuses_ambiguous_keys_and_duplicate_tag_ids() -> None:
    with pytest.raises(ValidationError, match="both a number and a counter"):
        Sheet(kind="actor", numbers={"hp": 5}, counters={"hp": Counter(current=5, maximum=5)})
    with pytest.raises(ValidationError, match="duplicate tag ids"):
        Sheet(
            kind="actor",
            tags=[SheetTag(id="poisoned", name="Poisoned"), SheetTag(id="poisoned", name="Again")],
        )


def test_runtime_merges_template_record_and_author_by_specificity() -> None:
    template = SheetTemplate(
        numbers={"armor-class": 10},
        counters={"hp": CounterTemplate(current=1, maximum=1, recharge="long-rest")},
    )
    definition = SheetDefinition(numbers={"armor-class": 15})

    sheet = definition.runtime("actor", template, record_numbers={"hp": 7, "armor-class": 12})

    assert sheet.counters["hp"] == Counter(current=7, maximum=7, recharge="long-rest")
    assert sheet.numbers["armor-class"] == 15
