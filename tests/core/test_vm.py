import pytest
from pydantic import ValidationError

from aidm.engines.vm import ActionDef

RISK = {
    "name": "risk",
    "doc": "An uncertain attempt.",
    "labels": ["strong", "setback"],
    "params": {"actor_id": {"type": "entity-id", "description": "Who acts."}},
    "program": [
        {"op": "roll", "dice": "2d6", "reason": "trying", "vs": 7, "into": "total"},
        {"op": "outcome", "of": "$total", "at": {"strong": 7}, "default": "setback"},
    ],
}


def _refused(**program: object) -> str:
    with pytest.raises(ValidationError) as refusal:
        _ = ActionDef.model_validate(RISK | program)
    return str(refusal.value)


def test_a_broken_program_is_refused_at_load_not_on_the_turn_that_runs_it() -> None:
    """An authored program is content: every reference, label, and effect it names is checked
    once at load, so a typo cannot surface mid-turn as a dead action."""
    assert ActionDef.model_validate(RISK).model().model_fields.keys() == {"act", "actor_id"}

    undefined = [{"op": "outcome", "of": "$missing", "at": {"strong": 7}, "default": "setback"}]
    assert "reads undefined ['missing']" in _refused(program=undefined)

    stray = [*RISK["program"], {"op": "apply", "when_outcome": "mixed", "effect": {"op": "reveal"}}]
    assert "['mixed'] is no outcome" in _refused(program=stray)

    malformed = [{"op": "apply", "effect": {"op": "reveal", "entity": "vault"}}]
    assert "reveal.entity_id" in _refused(program=malformed)

    refusal = [
        {
            "op": "require",
            "that": {"pred": "is-player", "actor": "$actor_id"},
            "message": "{actor_id_nme} may not",
        }
    ]
    assert "refusal names undefined ['actor_id_nme']" in _refused(program=refusal)
