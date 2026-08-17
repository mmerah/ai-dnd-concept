from typing import Literal

from pydantic import Field

from aidm.engines.counters import render_counters
from aidm.engines.sheets import SheetBase, SheetMechanics
from aidm.state.base import Counter, Entity, Slug

STARTING_CREDITS = 2
DEFAULT_FACE = 6  # an unlisted skill rolls the bare d6
HINDERED_FACE = 4

type SkillDie = Literal[8, 10, 12]
LADDER: tuple[SkillDie, ...] = (8, 10, 12)


class Sheet(SheetBase):
    """The one sheet shape, whether it belongs to the player or to an NPC."""

    specialty: str = ""
    origin: str = ""
    skills: dict[str, SkillDie] = Field(default_factory=dict)
    credits: Counter = Counter(current=STARTING_CREDITS)
    # The advancement ledger.
    jobs: Counter = Counter(current=0)

    def counters(self) -> dict[Slug, Counter]:
        return {"credits": self.credits}

    def face(self, skill: str) -> int:
        return self.skills.get(skill, DEFAULT_FACE)


class Mechanics(SheetMechanics[Sheet]): ...


def raised(current: SkillDie | None) -> SkillDie:
    """One step up the none -> d8 -> d10 -> d12 ladder; raises ValueError at the top."""
    if current is None:
        return LADDER[0]
    index = LADDER.index(current)
    if index + 1 == len(LADDER):
        raise ValueError("that skill is already d12, the top of the ladder")
    return LADDER[index + 1]


def describe_entity(mechanics: Mechanics, entity: Entity) -> str:
    sheet = mechanics.sheets.get(entity.id)
    if sheet is None:
        return ""
    skills = ", ".join(f"{name} d{face}" for name, face in sorted(sheet.skills.items()))
    lines = (
        f"specialty: {sheet.specialty}" if sheet.specialty else "",
        f"origin: {sheet.origin}" if sheet.origin else "",
        f"skills: {skills}" if skills else "",
        f"pools: {render_counters(sheet.counters())}",
    )
    return "\n".join(line for line in lines if line)
