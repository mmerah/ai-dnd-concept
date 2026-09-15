"""The authored demo: what the player types, what the master plays, what the narrator writes.

The recorder reads the same beats it feeds the roles, so the camera knows what each turn shows.
The dice are seeded in `server.py`, so the narration below matches the oracle every run.
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import JsonValue

type Focus = Literal["page", "scene", "card", "sheet", "composer"]
type Lines = tuple[tuple[str | None, str], ...]

SCENARIO = "whispering-vault"
CHARACTER = "kael"


@dataclass(frozen=True, slots=True)
class Beat:
    """One turn: the player's words, the master's tool calls, the narrator's answer."""

    player: str
    calls: tuple[tuple[str, dict[str, JsonValue]], ...]
    lines: Lines
    focus: Focus = "page"
    hold: float = 3.0
    after: Lines = field(default=())


OPENING: Lines = (
    (
        None,
        "The abbey of Saint Corvin emptied in a single night, and nobody who left has said why. "
        "The abbot's study is the only room in it with a candle still burning.",
    ),
    (
        None,
        "Mara is at the desk where she has been for a year, cataloguing books nobody will read. "
        "She does not look up when you come in.",
    ),
    (None, "Under the desk, one flagstone sits a finger proud of its neighbours."),
)

BEATS: tuple[Beat, ...] = (
    Beat(
        player="I set my boot on the raised flagstone and lean my weight onto it.",
        calls=(
            (
                "roll",
                {
                    "what": "Lean on the raised flagstone",
                    "actor_id": "player",
                    "question": "Does it give?",
                    "position": "neutral",
                },
            ),
        ),
        lines=(
            (
                None,
                "The stone gives — a finger's drop, then a grind of stone on stone that the "
                "whole room hears.",
            ),
            ("mara", "Leave that."),
            (None, "Her pen has stopped. She is looking at the desk, not at you."),
        ),
        focus="card",
    ),
    Beat(
        player="Mara. What did the abbot seal down there?",
        calls=(("reveal", {"entity_id": "vault-map"}),),
        lines=(
            ("mara", "Not what. Who is the better question, and I will not answer that one."),
            (
                None,
                "She takes a folded chart from the back of the ledger and lays it on the desk "
                "between you, and keeps one finger on it.",
            ),
            ("mara", "The undercroft on this is larger than the abbey standing over it."),
        ),
        focus="card",
    ),
    Beat(
        player="I take the map.",
        calls=(
            (
                "change_tags",
                {"entity_id": "player", "kind": "gear", "gained": ["The Vault Map"]},
            ),
        ),
        lines=(
            (
                None,
                "She lets it go easily, the way people do when they have waited a year for "
                "somebody else to carry the thing.",
            ),
            ("mara", "Whatever you bring up, do not bring it through this room."),
        ),
        focus="sheet",
    ),
    Beat(
        player="I lift the flagstone and go down.",
        calls=(("next_scene", {"pursuit": "Down the stair the abbey's own plans deny."}),),
        lines=(
            (
                None,
                "The flagstone comes up on a lantern's worth of cold air and the smell of water "
                "that has never seen a summer.",
            ),
        ),
        after=(
            (
                None,
                "Eight dressed steps down, the stonework changes to something older, cut rather "
                "than laid. Your lantern reaches four steps past that and stops.",
            ),
            (None, "Somewhere below it, water is moving."),
        ),
        focus="page",
        hold=3.6,
    ),
)
