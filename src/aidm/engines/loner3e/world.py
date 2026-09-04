from collections.abc import Sequence
from typing import Literal

from pydantic import Field

from aidm.core.entities import Refusal, require_unique
from aidm.core.facts import Fact
from aidm.core.model import Character, Game, Scenario
from aidm.core.views import Rows
from aidm.engines.base import Counter, Person
from aidm.engines.scenes.world import SceneCanon, SceneWorld

LUCK_MAX = 6
DIE_FACE = 6  # every roll in the game is one d6, and every table is six rows
TIES_PER_TWIST = 3

TagKind = Literal["skill", "frailty", "gear", "condition"]


class Loner3eSheet(Person):
    """SRD "Everything is a Character": a person, an object, a vehicle or a curse alike."""

    concept: str = ""
    tags: dict[TagKind, list[str]] = Field(default_factory=dict)
    # Living characters only; the SRD gives none to an object, a vehicle or a curse.
    goal: str = ""
    motive: str = ""
    nemesis: str = ""
    luck: Counter = Field(default_factory=lambda: Counter(current=LUCK_MAX, maximum=LUCK_MAX))

    def tagged(self, kind: TagKind) -> list[str]:
        return self.tags.get(kind, [])

    def rows(self) -> Rows:
        return tuple(
            (label, value)
            for label, value in (
                ("Concept", self.concept),
                ("Skills", ", ".join(self.tagged("skill"))),
                ("Frailties", ", ".join(self.tagged("frailty"))),
                ("Gear", ", ".join(self.tagged("gear"))),
                ("Conditions", ", ".join(self.tagged("condition"))),
                ("Goal", self.goal),
                ("Motive", self.motive),
                ("Nemesis", self.nemesis),
                ("Luck", str(self.luck)),
            )
            if value
        )

    def unwritten(self) -> str:
        missing = [
            why
            for why, satisfied in (
                ("alive", self.alive),
                ("full luck", self.luck.current == LUCK_MAX),
            )
            if not satisfied
        ]
        return ", ".join(missing)

    def change_tags(self, kind: TagKind, gained: Sequence[str], lost: Sequence[str]) -> list[Fact]:
        if not gained and not lost:
            raise Refusal("change_tags needs at least one gained or lost tag")
        require_unique(f"{kind} tags", (*gained, *lost))
        current = self.tagged(kind)
        if carried := [tag for tag in gained if tag in current]:
            raise Refusal(f"{self.name} already carries the {kind} {carried[0]!r}")
        if missing := [tag for tag in lost if tag not in current]:
            raise Refusal(f"{self.name} carries no {kind} {missing[0]!r}")
        self.tags[kind] = [tag for tag in (*current, *gained) if tag not in lost]
        deltas = (*(f"+{tag}" for tag in gained), *(f"-{tag}" for tag in lost))
        trace = f"{self.label} {kind} " + ", ".join(deltas)
        parts: list[str] = []
        if gained:
            took = ", ".join(gained)
            parts.append(f"Took {took}" if kind == "gear" else f"Now: {took}")
        if lost:
            lost_line = ", ".join(lost)
            parts.append(f"Lost {lost_line}" if kind == "gear" else f"No longer: {lost_line}")
        return [self.fact("tags_changed", trace, card="; ".join(parts))]

    def drive(self, *, goal: str, motive: str, nemesis: str) -> list[Fact]:
        if not goal and not motive and not nemesis:
            raise Refusal("drive needs a goal, a motive or a nemesis to set")
        parts: list[str] = []
        if goal:
            self.goal = goal
            parts.append(f"goal: {goal}")
        if motive:
            self.motive = motive
            parts.append(f"motive: {motive}")
        if nemesis:
            self.nemesis = nemesis
            parts.append(f"nemesis: {nemesis}")
        trace = f"{self.label} " + "; ".join(parts)
        card = f"{self.name}: {goal}" if goal else ""
        return [self.fact("drive_set", trace, card=card)]

    def refill(self, why: str) -> list[Fact]:
        return self.luck.change(self, self.luck.shortfall, "Luck", why)


class Loner3eWorld(SceneWorld[Loner3eSheet, Loner3eSheet]):
    # The played character's tally paces the whole game, so no sheet carries one.
    twist: Counter = Field(default_factory=lambda: Counter(current=0, maximum=TIES_PER_TWIST))

    def conflict_prompt(self, actor: Loner3eSheet, opponent: Loner3eSheet) -> str:
        foe = actor if opponent.id == self.player.id else opponent
        return (
            f"The conflict with {foe.name} runs on: neither side is out of luck yet. Press the "
            "attack, try something else, or break away — what do you do?"
        )


class Loner3eGame(Game[Loner3eWorld]):
    pass


class Loner3eScenario(Scenario[SceneCanon[Loner3eSheet]]):
    pass


class Loner3eCharacter(Character[Loner3eSheet]):
    pass
