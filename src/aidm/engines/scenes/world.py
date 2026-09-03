from collections.abc import Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import (
    CheckedEntityId,
    EntityId,
    Mutable,
    Refusal,
    Slug,
    require_unique,
)
from aidm.core.facts import Fact
from aidm.core.play import Exchange, SceneRecord
from aidm.core.views import Panel, PanelRow, Sections
from aidm.engines.base import Person, Thing, check_filing, sentence
from aidm.engines.hub import (
    HOME_ROW,
    HUB_ROW,
    JOB_DONE,
    Board,
    Job,
    Offer,
    check_board,
    check_jobs,
    closed_jobs_of,
    open_job_of,
    since_start,
)
from aidm.engines.scenes.drafts import JobDraft, NextDraft, ReturnDraft, SceneDraft

SCENE_SETTLED = Fact(
    kind="scene_settled",
    trace=(
        "this scene is settled. Bring it to a close, then ask the player what they want to "
        "pursue next — in the fiction, naming what the scene left open, never as a list of "
        "choices. They may also stay and keep playing here, so ask; do not push them out"
    ),
    told=True,
)

SCENE_LEFT = Fact(
    kind="scene_left",
    trace=(
        "the player has left this place; close the scene on their going and describe nothing "
        "of where they arrive: the page carries them on"
    ),
    told=True,
)


class SceneRun(Mutable):
    # Names the art cache entry, so returning to a place reuses its picture.
    place: Slug
    title: str
    # The player reads it; settling it ends the scene.
    question: str = Field(min_length=10)
    situation: str = Field(min_length=40)
    here: list[CheckedEntityId] = Field(default_factory=list)
    exchanges: list[Exchange] = Field(default_factory=list)
    # None while open; "" once settled here; the player's words when they left for elsewhere
    left: str | None = None
    recap: str = ""  # written when the player left


class SceneCanon[C: Person](Mutable):
    """A scenario as authored: its opening scene and cast, with no player in it yet."""

    cast: dict[EntityId, C] = Field(default_factory=dict)
    opening: SceneRun
    source: str = ""
    hub: Slug | None = None
    board: Board | tuple[()] = ()

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
        check_filing(self.cast)
        check_named(self.opening.here, self.cast)
        opening = self.opening
        if opening.exchanges or opening.left is not None or opening.recap:
            raise Refusal("an opening with play in it")
        check_hub(self.hub, self.board, (self.opening,), ())
        return self


class SceneWorld[C: Person, P: Person](Mutable):
    """The world as a sequence of scenes: the player is a sheet, never a cast entry."""

    runs: list[SceneRun] = Field(min_length=1)
    source: str = ""
    hub: Slug | None = None
    board: Board | tuple[()] = ()
    jobs: list[Job] = Field(default_factory=list)
    cast: dict[EntityId, C] = Field(default_factory=dict)
    player: P
    party: list[EntityId] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_hub(self.hub, self.board, self.runs, self.jobs)
        check_filing(self.cast)
        check_named(self.run.here, self.cast)
        if not self.player.known:
            raise Refusal("the player is unknown to themselves")
        if self.player.id in self.cast:
            raise Refusal("the player is in the cast")
        if self.player.id in self.run.here:
            raise Refusal("the player is in every scene and is never listed in it")
        if self.player.id in self.party:
            raise Refusal("the player cannot travel with themselves")
        require_unique("party", self.party)
        for one in self.party:
            if one not in self.cast:
                raise Refusal(f"{one!r} travels with the player but is not in the cast")
            if not self.cast[one].alive:
                raise Refusal(f"{one!r} is dead and cannot travel with the player")
        if left := sorted(set(self.party) - set(self.run.here)):
            raise Refusal(f"the party is in every scene; {left} are not in this one")
        return self

    @classmethod
    def begin(cls, canon: SceneCanon[C], player: P) -> Self:
        """The player is added by code and never authored, so no scenario can claim their id."""
        canon = deepcopy(canon)
        return cls(
            cast=canon.cast,
            player=player,
            runs=[canon.opening],
            source=canon.source,
            hub=canon.hub,
            board=canon.board,
        )

    @property
    def run(self) -> SceneRun:
        return self.runs[-1]

    @property
    def at_hub(self) -> bool:
        return self.hub is not None and self.run.place == self.hub

    def present(self) -> list[EntityId]:
        return [one for one in self.run.here if self.cast[one].known]

    def hidden(self) -> list[EntityId]:
        return [one for one in self.run.here if not self.cast[one].known]

    def open_job(self) -> Job | None:
        return open_job_of(self.jobs)

    def closed_jobs(self) -> tuple[Job, ...]:
        return closed_jobs_of(self.jobs)

    def job_terms(self) -> str:
        job = self.open_job()
        return job.terms if job is not None else ""

    @property
    def job_done(self) -> bool:
        job = self.open_job()
        return job is not None and job.finished

    def job_runs(self) -> list[SceneRun]:
        return since_start(self.runs, self.open_job(), campaign=self.hub is not None)

    def exchanges(self) -> tuple[Exchange, ...]:
        return tuple(one for run in self.runs for one in run.exchanges)

    def scenes(self) -> tuple[SceneRecord, ...]:
        return tuple(
            SceneRecord(
                title=run.title,
                question=run.question,
                recap=run.recap,
                exchanges=tuple(run.exchanges),
            )
            for run in self.job_runs()
        )

    def last_seen(self, entity_id: EntityId) -> str:
        """The prompt's own line; scanning back keeps what the story dropped from being lost."""
        for run in reversed(self.runs):
            if entity_id in run.here:
                return f"last seen in: {run.title}"
        return ""

    def members(self) -> list[C]:
        return [self.cast[one] for one in self.party]

    def require(self, entity_id: EntityId) -> C | P:
        if entity_id == self.player.id:
            return self.player
        one = self.cast.get(entity_id)
        if one is None:
            raise Refusal(f"unknown id {entity_id!r}. Use only ids you were shown.")
        return one

    def require_here(self, entity_id: EntityId) -> C | P:
        one = self.require(entity_id)
        if one.id == self.player.id:
            return one
        if one.id not in self.run.here or not one.known:
            raise Refusal(f"{one.name} is not here with the player, so nothing can happen to them")
        return one

    def require_alive_here(self, entity_id: EntityId) -> C | P:
        one = self.require(entity_id)
        if not one.alive:
            raise Refusal(f"{one.name} is dead; they take no further part.")
        if one.id == self.player.id:
            return one
        if one.id not in self.run.here or not one.known:
            raise Refusal(
                f"{entity_id!r} is not here with the player. "
                "Bring them here first, or act on who is here."
            )
        return one

    def here(self) -> Iterator[C | P]:
        yield self.player
        for entity_id in self.present():
            yield self.cast[entity_id]

    def reveal_hidden(self, entity_id: EntityId) -> list[Fact]:
        """The discovery itself, distinct from what `enter` tells about someone walking in."""
        one = self.require(entity_id)
        if entity_id not in self.run.here or one.known:
            raise Refusal(f"{entity_id!r} is not hidden here")
        facts = one.reveal()
        return [facts[0].model_copy(update={"card": sentence(f"{one.name} discovered")})]

    def enter(self, entity_id: EntityId) -> list[Fact]:
        if entity_id == self.player.id:
            raise Refusal("the player is in every scene; move the story on instead")
        one = self.require(entity_id)
        if one.id in self.run.here:
            raise Refusal(f"{one.name} is already here")
        self.run.here.append(one.id)
        trace = f"{one.label} arrives"
        return [*one.reveal(), one.fact("entity_entered", trace, card=f"{one.name} arrives")]

    def leave(self, entity_id: EntityId) -> list[Fact]:
        if entity_id == self.player.id:
            raise Refusal("the player is in every scene; move the story on instead")
        one = self.require_here(entity_id)
        if one.id in self.party:
            raise Refusal(f"{one.name} travels with the player and leaves through `leave_party`")
        self.run.here.remove(one.id)
        return [one.fact("entity_left", f"{one.label} leaves", card=f"{one.name} leaves")]

    def kill(self, entity_id: EntityId) -> list[Fact]:
        one = self.require_here(entity_id)
        if not one.alive:
            raise Refusal(f"{one.name} is already dead")
        facts = one.reveal()
        if one.id in self.party:
            self.party.remove(one.id)
        one.alive = False
        card = "You are dead" if one.id == self.player.id else f"{one.name} is dead"
        facts.append(one.fact("actor_killed", f"{one.label} is dead", card=card))
        return facts

    def join_party(self, entity_id: EntityId) -> list[Fact]:
        one = self.require_alive_here(entity_id)
        if one.id in self.party:
            raise Refusal(f"{one.name} already travels with the player")
        facts = one.reveal()
        self.party.append(one.id)
        trace = f"{one.name}[{one.id}] travels with the player"
        facts.append(one.fact("party_joined", trace, card=f"{one.name} joins your party"))
        return facts

    def leave_party(self, entity_id: EntityId) -> list[Fact]:
        one = self.require(entity_id)
        if one.id not in self.party:
            raise Refusal(f"{one.name} does not travel with the player")
        self.party.remove(one.id)
        trace = f"{one.name}[{one.id}] no longer travels with the player"
        return [one.fact("party_left", trace, card=f"{one.name} leaves your party")]

    def settle(self, job_done: bool, pursuit: str) -> list[Fact]:
        if self.run.left is not None:
            raise Refusal("this scene is already settled; the player has the way on")
        if job_done:
            job = self.open_job()
            if job is None or self.at_hub:
                raise Refusal("no job is open here")
            job.finished = True
        self.run.left = pursuit
        settled = SCENE_LEFT if pursuit else SCENE_SETTLED
        return [settled, JOB_DONE] if job_done else [settled]

    def merged_cast(self, draft: SceneDraft[C]) -> dict[EntityId, C]:
        """A re-filed member keeps the world's entry with the draft's brief."""
        return {
            **self.cast,
            **{
                one: held.model_copy(update={"brief": written.brief})
                if (held := self.cast.get(one)) is not None
                else written
                for one, written in draft.cast.items()
            },
        }

    def apply_scene(self, draft: SceneDraft[C]) -> None:
        self.cast = self.merged_cast(draft)
        everyone: Mapping[EntityId, Thing] = {self.player.id: self.player, **self.cast}
        present = resolve_ids(draft.present, everyone, "present")
        hidden = resolve_ids(draft.hidden, everyone, "hidden")
        for one in present:
            self.cast[one].known = True
        if isinstance(draft, NextDraft):
            self.run.recap = draft.recap
        if isinstance(draft, JobDraft):
            self.jobs.append(
                Job(title=draft.title, place=draft.place, terms=draft.job, started=len(self.runs))
            )
        elif isinstance(draft, ReturnDraft):
            job = self.open_job()
            if job is None:
                raise Refusal("no job is open to close")
            job.debrief = draft.debrief
            self.board = draft.offers
        self.runs.append(run_of(draft, [*self.party, *present, *hidden]))

    def party_rows(self) -> Sections:
        members = self.members()
        if not members:
            return ()
        listed = "\n".join(f"- {m.name}[{m.id}]" for m in members)
        return (("THE PARTY (led by the player)", listed),)

    def party_panel(self) -> tuple[Panel, ...]:
        members = self.members()
        if not members:
            return ()
        rows = tuple(PanelRow(label=m.name, detail=m.brief, icon_id=m.id) for m in members)
        return (Panel(title="Party", rows=rows),)

    def scene_rows(self) -> tuple[PanelRow, ...]:
        rows = [PanelRow(label=self.run.question, detail="")]
        if terms := self.job_terms():
            rows.append(PanelRow(label="The job", detail=terms))
        if self.at_hub:
            rows.append(HUB_ROW)
        elif (left := self.run.left) is not None:
            if left:
                rows.append(PanelRow(label="Go on", detail=left, intent=left))
            else:
                rows.append(
                    PanelRow(
                        label="Way on", detail="Keep playing, or name where you go and move on."
                    )
                )
            if self.hub is not None:
                rows.append(HOME_ROW)
        return tuple(rows)


def check_named(here: Sequence[EntityId], cast: Mapping[EntityId, Thing]) -> None:
    require_unique("ids in the scene", here)
    for who in here:
        if who not in cast:
            raise Refusal(f"scene names {who!r}, who is not in the cast")


def check_hub(
    hub: Slug | None, board: Sequence[Offer], runs: Sequence[SceneRun], jobs: Sequence[Job]
) -> None:
    check_board(hub, board)
    check_jobs(hub, jobs, len(runs))
    if hub is None:
        return
    if runs[0].place != hub:
        raise Refusal(f"run 0 does not open at hub {hub!r}")
    # Every hub run after the first is a return, and a return closes exactly one job.
    if sum(run.place == hub for run in runs[1:]) != len(closed_jobs_of(jobs)):
        raise Refusal("hub runs after the first and closed jobs disagree")


def resolved_id(wanted: str, cast: Mapping[EntityId, Thing]) -> EntityId | None:
    """Ids are the worldsmith's failure mode: an unknown one matches a cast name before refusal."""
    if wanted in cast:
        return EntityId(wanted)
    matches = [one.id for one in cast.values() if one.name.casefold() == wanted.casefold()]
    return EntityId(matches[0]) if len(matches) == 1 else None


def resolve_ids(
    wanted: Iterable[str], cast: Mapping[EntityId, Thing], where: str
) -> list[EntityId]:
    found: list[EntityId] = []
    for one in wanted:
        matched = resolved_id(one, cast)
        if matched is None:
            raise Refusal(f"the scene lists {one!r} as {where}, and no such id or name exists")
        if matched not in found:
            found.append(matched)
    return found


def run_of[C: Person](draft: SceneDraft[C], here: list[EntityId]) -> SceneRun:
    return SceneRun(
        place=draft.place,
        title=draft.title,
        question=draft.question,
        situation=draft.situation,
        here=here,
    )
