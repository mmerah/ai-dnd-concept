from collections.abc import Callable, Mapping
from pathlib import Path
from random import Random

from pydantic import Field

from aidm.content.model import CharacterProfile, CreatedCharacter
from aidm.engines.core import (
    CharacterCreation,
    Command,
    DirectorContext,
    NoArgs,
    ProposalBase,
    SheetAdvancement,
    SheetEngine,
    apply_action,
    apply_play,
    command,
)
from aidm.engines.loner3e.rules import (
    GROWTH,
    AdventureGrowth,
    Change,
    Mechanics,
    Pack,
    PackEntry,
    Question,
    Sheet,
    apply_complete_chapter,
    apply_restore_luck,
    describe_entity,
    resolve_question,
    twist_table,
)
from aidm.engines.packs import load_packs, pack_paths, pack_step
from aidm.state.creation import (
    AnyStep,
    CreationOption,
    CreationStep,
    Picks,
    TextStep,
    check_picks,
    picked,
)
from aidm.state.entities import (
    PLAYER_ID,
    CheckedEntityId,
    Counter,
    EngineId,
    Entity,
    EntityId,
    Frozen,
)
from aidm.state.facts import Fact, explained_fact
from aidm.state.model import Game
from aidm.state.play import PendingDecision

type Twists = Callable[[Game], tuple[tuple[str, str], ...]]


class RestoreLuck(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or an actor here.")


def _restore_luck(deps: DirectorContext, args: RestoreLuck) -> str:
    return apply_action(deps, lambda draft: apply_restore_luck(draft, args.actor_id))


def _complete_chapter(deps: DirectorContext, _args: NoArgs) -> str:
    return apply_action(deps, apply_complete_chapter)


def director_commands(twists: Twists) -> tuple[Command, ...]:
    """Only the question roll needs the twist table, so only it is built per engine."""

    def roll_question(deps: DirectorContext, question: Question) -> str:
        return apply_play(
            deps, lambda draft, rng: resolve_question(draft, question, rng, twists(draft))
        )

    return (
        command(
            "roll_question",
            "Roll Chance against Risk for one closed dramatic question.",
            Question,
            roll_question,
        ),
        command(
            "restore_luck",
            "Restore an actor's luck after a conflict ends.",
            RestoreLuck,
            _restore_luck,
        ),
        command(
            "complete_chapter",
            "Record that the current adventure has ended.",
            NoArgs,
            _complete_chapter,
        ),
    )


class Loner3eAdvancement(SheetAdvancement):
    proposal_type = AdventureGrowth
    ledger_key = "milestones"
    occasion = "finishes an adventure"
    offer_text = GROWTH
    spent_why = "a milestone spent"

    def ledger(self, state: Game, subject_id: EntityId) -> Counter:
        return Mechanics.of_game(state).sheets[subject_id].milestones

    def grant(
        self, draft: Game, subject_id: EntityId, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        del rng
        assert isinstance(proposal, AdventureGrowth)
        sheet = Mechanics.of_game(draft).sheets[subject_id]
        subject = draft.world.require(subject_id)
        # Sequential against the live sheet, so a rewrite may name what an earlier change wrote.
        return tuple(
            _rewrite(sheet, subject, change, proposal.why)
            if change.kind == "rewrite"
            else _gain(sheet, subject, change, proposal.why)
            for change in proposal.changes
        )


def _gain(sheet: Sheet, subject: Entity, change: Change, why: str) -> Fact:
    if change.kind == "skill":
        sheet.skills = (*sheet.skills, change.tag)
    elif change.kind == "gear":
        sheet.gear = (*sheet.gear, change.tag)
    else:
        sheet.frailties = (*sheet.frailties, change.tag)
    return explained_fact(
        subject,
        f"{change.kind}_gained",
        f"{subject.name} gained {change.kind} {change.tag}",
        why,
        narrate=False,
    )


def _rewrite(sheet: Sheet, subject: Entity, change: Change, why: str) -> Fact:
    old, new = change.tag, change.into
    if old in sheet.skills:
        sheet.skills = _swapped(sheet.skills, old, new)
    elif old in sheet.frailties:
        sheet.frailties = _swapped(sheet.frailties, old, new)
    elif old in sheet.gear:
        sheet.gear = _swapped(sheet.gear, old, new)
    else:
        raise ValueError(f"{subject.name} carries no tag {old!r} to rewrite")
    return explained_fact(
        subject,
        "tag_rewritten",
        f"{subject.name} rewrote {old} as {new}",
        why,
        narrate=False,
    )


def _swapped(tags: tuple[str, ...], old: str, new: str) -> tuple[str, ...]:
    return tuple(new if tag == old else tag for tag in tags)


class Loner3eCreation(CharacterCreation):
    def __init__(self, packs: Mapping[str, Pack]) -> None:
        self._packs = packs

    def steps(self, picks: Picks) -> tuple[AnyStep, ...]:
        first = pack_step(self._packs)
        chosen = picked(picks, "pack")
        pack = self._packs.get(chosen[0]) if chosen else None
        if pack is None:
            return (first,)
        return (
            first,
            TextStep(
                id="concept",
                prompt="Write a one-line concept",
                hint=", ".join(entry.label for entry in pack.concepts[:3]),
            ),
            CreationStep(
                id="skills", prompt="Choose two skills", options=_options(pack.skills), choose=2
            ),
            CreationStep(id="frailty", prompt="Choose a frailty", options=_options(pack.frailties)),
            CreationStep(
                id="gear", prompt="Choose two pieces of gear", options=_options(pack.gear), choose=2
            ),
        )

    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        check_picks(self.steps(picks), picks)
        pack = self._packs[picked(picks, "pack")[0]]
        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief),
            rules={
                "pack": picked(picks, "pack")[0],
                "concept": picked(picks, "concept")[0],
                "skills": [_label(pack.skills, skill) for skill in picked(picks, "skills")],
                "frailties": [_label(pack.frailties, picked(picks, "frailty")[0])],
                "gear": [_label(pack.gear, gear) for gear in picked(picks, "gear")],
            },
        )


def _options(entries: tuple[PackEntry, ...]) -> tuple[CreationOption, ...]:
    return tuple(
        CreationOption(id=entry.id, label=entry.label, detail=entry.detail) for entry in entries
    )


def _label(entries: tuple[PackEntry, ...], chosen: str) -> str:
    return next(entry.label for entry in entries if entry.id == chosen)


class Loner3eEngine(SheetEngine[Sheet]):
    id = EngineId("loner3e")
    badge = ("LONER 3E", "teal-7")
    engine_dir = Path(__file__).parent
    sheet_type = Sheet
    mechanics_type = Mechanics

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.advancement = Loner3eAdvancement(self.engine_dir)
        self.creation = Loner3eCreation(self.packs)
        self.director_commands = director_commands(self.twists)

    def validate(self, state: Game) -> None:
        super().validate(state)
        if (chosen := Mechanics.of_game(state).sheets[PLAYER_ID].pack) not in self.packs:
            raise ValueError(f"this game plays the {chosen!r} table set, which is not installed")

    def describe(self, state: Game, entity: Entity) -> str:
        return describe_entity(Mechanics.of_game(state), entity)

    def sheet_view(self, state: Game) -> tuple[tuple[str, str], ...]:
        sheet = Mechanics.of_game(state).sheets[PLAYER_ID]
        return (
            ("Concept", sheet.concept),
            ("Skills", ", ".join(sheet.skills)),
            ("Frailties", ", ".join(sheet.frailties)),
            ("Gear", ", ".join(sheet.gear)),
            ("Luck", f"{sheet.luck.current} / {sheet.luck.maximum}"),
        )

    def check_pending(self, pending: PendingDecision) -> None:
        """The hand-back is the whole decision: no options, nothing frozen, no `resume`."""
        if pending.kind != "conflict":
            super().check_pending(pending)
        elif pending.payload:
            raise ValueError("a conflict decision freezes nothing, so it carries no payload")

    def twists(self, state: Game) -> tuple[tuple[str, str], ...]:
        """The player's own table set: an NPC sheet is seeded with the default and never selects."""
        return twist_table(self.packs, Mechanics.of_game(state).sheets[PLAYER_ID].pack)
