from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from aidm.core.entities import Frozen, Refusal, Slug, check_unique
from aidm.core.facts import Fact
from aidm.core.model import Character, Game, Scenario
from aidm.core.play import DecisionOption
from aidm.core.views import Rows
from aidm.engines.base import PLAYER_ID, Gauge, Person
from aidm.engines.scenes.tools import SceneDraft
from aidm.engines.scenes.world import SceneWorld

LUCK_MAX = 6
DIE_FACE = 6  # every roll in the game is one d6, and every table is six rows
TIES_PER_TWIST = 3
AND_AT = 4  # both dice 4+ sharpens the answer to -and
BUT_AT = 3  # both dice 3 or under softens it to -but
TOLD: dict[str, str] = {
    "yes-and": "yes, and better than hoped",
    "yes": "yes",
    "yes-but": "yes, but at a cost",
    "no-but": "no, but not badly",
    "no": "no",
    "no-and": "no, and worse",
}

type TagKind = Literal["skill", "frailty", "gear", "condition"]


class Outcome(Frozen):
    id: Slug
    harm: int

    @property
    def wording(self) -> str:
        """The answer in story words: the narrator never reads the rules."""
        return TOLD[self.id]


class Loner3eCast(Person):
    """A character: a person, an object, a vehicle or a curse alike."""

    concept: str = ""
    tags: dict[TagKind, list[str]] = Field(default_factory=dict)
    # Living characters only; the SRD gives none to an object, a vehicle or a curse.
    goal: str = ""
    motive: str = ""
    nemesis: str = ""
    luck: Gauge = Field(default_factory=lambda: Gauge(current=LUCK_MAX, maximum=LUCK_MAX))
    defeated: bool = False

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
                ("Defeated", "yes" if self.defeated else ""),
            )
            if value
        )

    def forbidden(self) -> str:
        parts = (super().forbidden(), "full luck" if self.luck.shortfall != 0 else "")
        return ", ".join(part for part in parts if part)

    def change_tags(self, kind: TagKind, gained: Sequence[str], lost: Sequence[str]) -> list[Fact]:
        check_unique(f"{kind} tags", (*gained, *lost))
        current = self.tagged(kind)
        if carried := [tag for tag in gained if tag in current]:
            raise Refusal(f"{self.name} already carries the {kind} {carried[0]!r}")
        if missing := [tag for tag in lost if tag not in current]:
            raise Refusal(f"{self.name} carries no {kind} {missing[0]!r}")
        self.tags[kind] = [tag for tag in (*current, *gained) if tag not in lost]
        trace = f"{self.mention} {kind} " + ", ".join(
            (*(f"+{tag}" for tag in gained), *(f"-{tag}" for tag in lost))
        )
        parts: list[str] = []
        if gained:
            took = ", ".join(gained)
            parts.append(f"Took {took}" if kind == "gear" else f"Now: {took}")
        if lost:
            lost_line = ", ".join(lost)
            parts.append(f"Lost {lost_line}" if kind == "gear" else f"No longer: {lost_line}")
        return [self.fact(trace, card="; ".join(parts))]

    def drive(self, *, goal: str, motive: str, nemesis: str) -> list[Fact]:
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
        trace = f"{self.mention} " + "; ".join(parts)
        card = f"{self.name}: {goal}" if goal else ""
        return [self.fact(trace, card=card)]

    def refill(self, why: str) -> list[Fact]:
        return self.change(self.luck, self.luck.shortfall, "Luck", why)

    def lose(self) -> list[Fact]:
        """The mark the Luck reset cannot carry: this contest stays settled until it is cleared."""
        self.defeated = True
        lost = f"{self.name} is out of luck"
        return [self.fact(lost, card=lost)]

    def recover(self, why: str) -> list[Fact]:
        facts = self.refill(why)
        if self.defeated:
            self.defeated = False
            trace = f"{self.mention} is no longer defeated ({why})"
            card = (
                "No longer defeated"
                if self.id == PLAYER_ID
                else f"{self.name} is no longer defeated"
            )
            facts.append(self.fact(trace, card=card))
        return facts


@dataclass(frozen=True, slots=True)
class Struck:
    """One exchange of a conflict: what it cost, and who lost it, if anyone."""

    facts: list[Fact]
    loser: str = ""


class Loner3eWorld(SceneWorld[Loner3eCast]):
    # The played character's tally paces the whole game, so no sheet carries one.
    twist: Gauge = Field(default_factory=lambda: Gauge(current=0, maximum=TIES_PER_TWIST))

    def tick_twist(self) -> bool:
        self.twist.current += 1
        if self.twist.shortfall == 0:
            self.twist.current = 0
            return True
        return False

    def conflict_prompt(self, actor: Loner3eCast, opponent: Loner3eCast) -> str:
        foe = actor if opponent.id == self.player.id else opponent
        return (
            f"The conflict with {foe.name} runs on: neither side is out of luck yet. Press the "
            "attack, try something else, or break away — what do you do?"
        )

    def strike(self, actor: Loner3eCast, opponent: Loner3eCast, outcome: Outcome) -> Struck:
        harm = outcome.harm
        hit, striker = (opponent, actor) if harm > 0 else (actor, opponent)
        why = f"{striker.name} gets the better of the exchange"
        facts = hit.change(hit.luck, -abs(harm), "Luck", why)
        if hit.luck.current != 0:
            return Struck(facts=facts)
        facts.extend(hit.lose())
        # SRD: luck resets after conflicts, and a side at 0 is the only end the engine sees.
        facts.extend(hit.refill("the conflict is over"))
        facts.extend(striker.refill("the conflict is over"))
        return Struck(facts=facts, loser=hit.name)

    def check_conflict(self, actor: Loner3eCast, opponent: Loner3eCast | None) -> None:
        if opponent is None:
            return
        if opponent.id == actor.id:
            raise Refusal(f"{actor.name} cannot be their own opposition in a conflict.")
        for side in (actor, opponent):
            if side.defeated:
                raise Refusal(
                    f"{side.name} lost their last conflict, so it is settled, not reopened. "
                    "Settle what it cost them, or call `restore_luck` first if this is a "
                    "genuinely new contest."
                )


Loner3eGame = Game[Loner3eWorld]

Loner3eScenario = Scenario[SceneDraft[Loner3eCast]]

Loner3eCharacter = Character[Loner3eCast]


def outcome_for(chance: int, risk: int) -> Outcome:
    if chance == risk:
        return Outcome(id="yes-but", harm=1)
    side, sign = ("yes", 1) if chance > risk else ("no", -1)
    if min(chance, risk) >= AND_AT:
        return Outcome(id=f"{side}-and", harm=3 * sign)
    if max(chance, risk) <= BUT_AT:
        return Outcome(id=f"{side}-but", harm=sign)
    return Outcome(id=side, harm=2 * sign)


def twist_pairing(subject: int, action: int, twists: Rows) -> tuple[str, str]:
    return twists[subject - 1][0], twists[action - 1][1]


def pack_meanings(entries: Sequence[DecisionOption], tags: Sequence[str]) -> Rows:
    detail_of = {entry.label: entry.detail for entry in entries if entry.detail}
    return tuple((tag, detail_of[tag]) for tag in tags if tag in detail_of)
