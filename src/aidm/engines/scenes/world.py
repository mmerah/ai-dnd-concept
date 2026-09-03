import json
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Mutable, Slug, require_unique
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import Game
from aidm.core.play import Exchange, SceneRecord
from aidm.core.tools import schema_of
from aidm.core.views import PanelRow, Rows, render_history, sections
from aidm.engines.core import (
    Entity,
    Person,
    check_filing,
    check_party,
    entity_fact,
    labeled,
    reveal,
    sentence,
)
from aidm.engines.hub import (
    HOME_ROW,
    HUB_ROW,
    JOB_DONE,
    Board,
    Job,
    Offer,
    check_board,
    check_jobs,
    check_kind,
    closed_jobs_of,
    hub_sections,
    open_job_of,
    place_unmet,
    since_start,
)
from aidm.engines.scenes.drafts import JobDraft, NextDraft, ReturnDraft, SceneDraft

WORLDSMITH = (Path(__file__).parent / "worldsmith.md").read_text(encoding=ENCODING)

NEXT_SCENE = (
    "Say this scene's question is settled. The player is then asked what they want to pursue, "
    "and their own words build the next scene. Do not answer for them."
)

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

SURPRISE = (
    "Surprise the player. Turn an established fact against them, or bring back something they "
    "have stopped thinking about. Surprise by recombining what exists, never by inventing what "
    "the source would not hold."
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


class NextScene(Frozen):
    job_done: bool = Field(
        default=False,
        description="A campaign only: settling this scene also finishes the job the player "
        "walked out on.",
    )
    pursuit: str = Field(
        default="",
        description="Set when the player has left this place for good with its question open: "
        "where they are going, in their own words. Empty when the question settled here.",
    )


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
            raise ValueError("an opening with play in it")
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
            raise ValueError("the player is unknown to themselves")
        if self.player.id in self.cast:
            raise ValueError("the player is in the cast")
        if self.player.id in self.run.here:
            raise ValueError("the player is in every scene and is never listed in it")
        if self.player.id in self.party:
            raise ValueError("the player cannot travel with themselves")
        check_party(self.party, self.cast)
        if left := sorted(set(self.party) - set(self.run.here)):
            raise ValueError(f"the party is in every scene; {left} are not in this one")
        return self

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
            raise ValueError(f"unknown id {entity_id!r}. Use only ids you were shown.")
        return one

    def require_here(self, entity_id: EntityId) -> C | P:
        one = self.require(entity_id)
        if one.id == self.player.id:
            return one
        if one.id not in self.run.here or not one.known:
            raise ValueError(
                f"{one.name} is not here with the player, so nothing can happen to them"
            )
        return one

    def require_alive_here(self, entity_id: EntityId) -> C | P:
        one = self.require(entity_id)
        if not one.alive:
            raise ValueError(f"{one.name} is dead; they take no further part.")
        if one.id == self.player.id:
            return one
        if one.id not in self.run.here or not one.known:
            raise ValueError(
                f"{entity_id!r} is not here with the player. "
                "Bring them here first, or act on who is here."
            )
        return one

    def here(self) -> Iterator[C | P]:
        yield self.player
        for entity_id in self.present():
            yield self.cast[entity_id]

    def label(self, entity: Person) -> str:
        return labeled(entity, self.player.id)

    def reveal(self, entity: Person) -> list[Fact]:
        return reveal(entity, self.player.id)

    def reveal_hidden(self, entity_id: EntityId) -> list[Fact]:
        """The discovery itself, distinct from what `enter` tells about someone walking in."""
        one = self.require(entity_id)
        if entity_id not in self.run.here or one.known:
            raise ValueError(f"{entity_id!r} is not hidden here")
        facts = self.reveal(one)
        return [facts[0].model_copy(update={"card": sentence(f"{one.name} discovered")})]

    def enter(self, entity_id: EntityId) -> list[Fact]:
        if entity_id == self.player.id:
            raise ValueError("the player is in every scene; move the story on instead")
        one = self.require(entity_id)
        if one.id in self.run.here:
            raise ValueError(f"{one.name} is already here")
        self.run.here.append(one.id)
        trace = f"{self.label(one)} arrives"
        return [
            *self.reveal(one),
            entity_fact(one, "entity_entered", trace, card=f"{one.name} arrives"),
        ]

    def leave(self, entity_id: EntityId) -> list[Fact]:
        if entity_id == self.player.id:
            raise ValueError("the player is in every scene; move the story on instead")
        one = self.require_here(entity_id)
        if one.id in self.party:
            raise ValueError(f"{one.name} travels with the player and leaves through `leave_party`")
        self.run.here.remove(one.id)
        trace = f"{self.label(one)} leaves"
        return [entity_fact(one, "entity_left", trace, card=f"{one.name} leaves")]

    def kill(self, entity_id: EntityId) -> list[Fact]:
        one = self.require_here(entity_id)
        if not one.alive:
            raise ValueError(f"{one.name} is already dead")
        facts = self.reveal(one)
        if one.id in self.party:
            self.party.remove(one.id)
        one.alive = False
        card = "You are dead" if one.id == self.player.id else f"{one.name} is dead"
        facts.append(entity_fact(one, "actor_killed", f"{self.label(one)} is dead", card=card))
        return facts

    def settle(self, job_done: bool, pursuit: str) -> tuple[Fact, ...]:
        if self.run.left is not None:
            raise ValueError("this scene is already settled; the player has the way on")
        if job_done:
            job = self.open_job()
            if job is None or self.at_hub:
                raise ValueError("no job is open here")
            job.finished = True
        self.run.left = pursuit
        settled = SCENE_LEFT if pursuit else SCENE_SETTLED
        return (settled, JOB_DONE) if job_done else (settled,)

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
        everyone: Mapping[EntityId, Entity] = {self.player.id: self.player, **self.cast}
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
                raise ValueError("no job is open to close")
            job.debrief = draft.debrief
        self.runs.append(run_of(draft, [*self.party, *present, *hidden]))

    def hub_rows(self, *, returning: bool) -> Rows:
        if self.hub is None:
            return ()
        return hub_sections(
            self.runs[0].title,
            self.hub,
            self.board,
            self.closed_jobs(),
            at_hub=self.at_hub,
            returning=returning,
            finished=self.job_done,
        )

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

    def here_lines(self) -> str:
        lines = "\n".join(entity_line(one) for one in self.here() if one.id != self.player.id)
        return lines or "- (none)"

    def hidden_lines(self) -> str:
        return "\n".join(entity_line(self.require(one)) for one in self.hidden()) or "- (none)"

    def render_worldsmith(self, intent: str, guidance: str, answer: type[SceneDraft[C]]) -> str:
        # The worldsmith must know who follows the player out of the scene.
        cast = "\n".join(
            (
                entity_line(self.player, detail=self.last_seen(self.player.id)),
                *(
                    entity_line(
                        one,
                        detail="travels with the player"
                        if one.id in self.party
                        else self.last_seen(one.id),
                    )
                    for one in self.cast.values()
                ),
            )
        )
        return worldsmith_prompt(
            source=self.source,
            history=render_history(self.scenes()),
            cast=cast,
            guidance=guidance,
            intent=intent,
            answer=answer,
            hub=(
                *((("THE JOB", terms),) if (terms := self.job_terms()) else ()),
                *self.hub_rows(returning=issubclass(answer, ReturnDraft)),
            ),
        )


class Reveal(Frozen):
    """Make a hidden entity known when the player notices, finds, or reaches it."""

    verb: Literal["reveal"]
    entity_id: CheckedEntityId = Field(description="Exact id of an entity listed as hidden here.")


class Enter(Frozen):
    """Bring a cast member into the current scene."""

    verb: Literal["enter"]
    entity_id: CheckedEntityId = Field(description="Exact id of a cast member not already here.")


class Leave(Frozen):
    """Take a cast member out of the current scene."""

    verb: Literal["leave"]
    entity_id: CheckedEntityId = Field(description="Exact id of someone here.")


class Kill(Frozen):
    """Record that someone here has died."""

    verb: Literal["kill"]
    entity_id: CheckedEntityId = Field(description="Exact id of who here died.")


def new_world[W: SceneWorld[Any, Any]](
    world_type: type[W], canon: SceneCanon[Any], player: Person
) -> W:
    """The player is added by code and never authored, so no scenario can claim their id."""
    canon = deepcopy(canon)
    return world_type(
        cast=canon.cast,
        player=player,
        runs=[canon.opening],
        source=canon.source,
        hub=canon.hub,
        board=canon.board,
    )


def check_game[W: SceneWorld[Any, Any]](packs: Collection[str], state: Game[W]) -> None:
    if not state.packs:
        raise ValueError(f"a {state.engine!r} game needs at least one table set")
    if missing := sorted(set(state.packs) - set(packs)):
        raise ValueError(f"the game names packs not installed: {missing}")
    check_kind(state.scenario.kind, state.payload.hub)


def way_open[W: SceneWorld[Any, Any]](state: Game[W]) -> bool:
    world = state.payload
    return world.run.left is not None or world.at_hub


def player_over[W: SceneWorld[Any, Any]](state: Game[W]) -> str | None:
    return "You died." if not state.payload.player.alive else None


def check_named(here: Sequence[EntityId], cast: Mapping[EntityId, Entity]) -> None:
    require_unique("ids in the scene", here)
    for who in here:
        if who not in cast:
            raise ValueError(f"scene names {who!r}, who is not in the cast")


def check_hub(
    hub: Slug | None, board: Sequence[Offer], runs: Sequence[SceneRun], jobs: Sequence[Job]
) -> None:
    check_board(hub, board)
    check_jobs(hub, jobs, len(runs))
    if hub is None:
        return
    if runs[0].place != hub:
        raise ValueError(f"run 0 does not open at hub {hub!r}")
    # Every hub run after the first is a return, and a return closes exactly one job.
    if sum(run.place == hub for run in runs[1:]) != len(closed_jobs_of(jobs)):
        raise ValueError("hub runs after the first and closed jobs disagree")


def resolved_id(wanted: str, cast: Mapping[EntityId, Entity]) -> EntityId | None:
    """Ids are the worldsmith's failure mode: an unknown one matches a cast name before refusal."""
    if wanted in cast:
        return EntityId(wanted)
    matches = [one.id for one in cast.values() if one.name.casefold() == wanted.casefold()]
    return EntityId(matches[0]) if len(matches) == 1 else None


def resolve_ids(
    wanted: Iterable[str], cast: Mapping[EntityId, Entity], where: str
) -> list[EntityId]:
    found: list[EntityId] = []
    for one in wanted:
        matched = resolved_id(one, cast)
        if matched is None:
            raise ValueError(f"the scene lists {one!r} as {where}, and no such id or name exists")
        if matched not in found:
            found.append(matched)
    return found


def named_in(situation: str, hidden: Iterable[str], cast: Mapping[EntityId, Entity]) -> list[str]:
    """Multi-word names only: a prop called `Bell` shares its word with any bell tower."""
    said = situation.casefold()
    found = (cast[one] for wanted in hidden if (one := resolved_id(wanted, cast)) is not None)
    return [one.name for one in found if " " in one.name.strip() and one.name.casefold() in said]


def cast_unmet(
    others: Sequence[str],
    hidden: Sequence[str],
    situation: str,
    known: Mapping[EntityId, Entity],
    held: Mapping[EntityId, Entity],
    *,
    needs_return: bool,
) -> list[str]:
    """The cast a scene owes, whatever the engine's own people are made of."""
    unmet: list[str] = []
    if not others:
        unmet.append("at least one cast member besides the player")
    if needs_return and not any(resolved_id(one, held) is not None for one in others):
        unmet.append("at least one existing cast member brought back")
    if stray := sorted(one for one in others if resolved_id(one, known) is None):
        unmet.append(f"ids that exist; these name nobody: {stray}")
    # `situation` is read to the player, so naming a hidden entity there hands them the find.
    if told := sorted(named_in(situation, hidden, known)):
        unmet.append(f"a situation that does not name what is hidden: {told}")
    return unmet


def hub_unmet(
    place: Slug,
    hub: Slug | None,
    *,
    debrief: str | None,
    held: Mapping[EntityId, Entity],
    known: Mapping[EntityId, Entity],
) -> list[str]:
    """A debrief means a return: it is home, and it is read to the player."""
    unmet: list[str] = []
    if (misplaced := place_unmet(place, hub, returning=debrief is not None)) is not None:
        unmet.append(misplaced)
    if debrief is not None:
        strangers = [eid for eid, one in held.items() if not one.known]
        if named := sorted(named_in(debrief, strangers, known)):
            unmet.append(f"a debrief that does not name what the player has not met: {named}")
    return unmet


def scene_unmet[C: Person, P: Person](
    draft: SceneDraft[C], world: SceneWorld[C, P] | None
) -> list[str]:
    """The one bar: every refusal the install makes, so the worldsmith's one retry sees them all."""
    held: Mapping[EntityId, C] = {} if world is None else world.cast
    everyone: Mapping[EntityId, Entity] = (
        dict(draft.cast)
        if world is None
        else {world.player.id: world.player, **world.merged_cast(draft)}
    )
    followers = () if world is None else (world.player.id, *world.party)
    others = (*draft.present, *draft.hidden)
    unmet: list[str] = []
    if named := sorted(one for one in others if resolved_id(one, everyone) in followers):
        unmet.append(
            "a scene that does not list the player or the party; "
            f"they are put there by code: {named}"
        )
    if world is not None and world.player.id in draft.cast:
        unmet.append("a cast that never rewrites the player")
    if misfiled := [
        f"{one.id!r} is filed under {key!r}" for key, one in draft.cast.items() if key != one.id
    ]:
        unmet.append("cast entries under their own id: " + "; ".join(misfiled))
    # Nothing can be brought back once everyone left behind travels with the player.
    needs_return = world is not None and bool(set(world.cast) - set(world.party))
    unmet.extend(
        cast_unmet(others, draft.hidden, draft.situation, everyone, held, needs_return=needs_return)
    )
    present = [one for name in draft.present if (one := resolved_id(name, everyone)) is not None]
    hidden = [one for name in draft.hidden if (one := resolved_id(name, everyone)) is not None]
    if overlap := sorted(set(present) & set(hidden)):
        unmet.append(f"nobody listed as both present and hidden: {overlap}")
    if met := sorted(one for one in set(hidden) - set(followers) if everyone[one].known):
        unmet.append(f"a hidden list without {met}, whom the player has already met")
    if broken := [
        f"{eid}: {why}"
        for eid, one in draft.cast.items()
        if eid not in held and (why := one.unwritten())
    ]:
        unmet.append(f"cast members as the worldsmith may write them: {broken}")
    unmet.extend(
        hub_unmet(
            draft.place,
            None if world is None else world.hub,
            debrief=draft.debrief if isinstance(draft, ReturnDraft) else None,
            held=held,
            known=everyone,
        )
    )
    return unmet


def scene_refusal[C: Person, P: Person](
    draft: SceneDraft[C], world: SceneWorld[C, P] | None = None
) -> str | None:
    unmet = scene_unmet(draft, world)
    return None if not unmet else "the scene needs " + "; ".join(unmet)


def worldsmith_prompt(
    *,
    source: str,
    history: str,
    cast: str,
    guidance: str,
    intent: str,
    answer: type[BaseModel],
    hub: Rows = (),
) -> str:
    return sections(
        (
            ("YOUR ROLE", WORLDSMITH),
            ("SOURCE MATERIAL", source or "(none — write from the cast)"),
            ("SCENES SO FAR", history),
            *hub,
            ("THE WHOLE CAST", cast),
            ("ENGINE GUIDANCE", guidance),
            ("WHAT COMES NEXT", intent),
            ("STANDING INSTRUCTION", SURPRISE),
            ("ANSWER WITH", json.dumps(schema_of(answer), indent=2, ensure_ascii=False)),
        )
    )


def entity_line(one: Person, *, detail: str = "") -> str:
    line = f"- {one.name}[{one.id}] — {one.brief}"
    if not one.alive:
        line += " (dead)"
    parts = [line]
    if sheet := "; ".join(f"{label.lower()}: {value}" for label, value in one.rows()):
        parts.append(f"  {sheet}")
    if detail:
        parts.append(f"  {detail}")
    return "\n".join(parts)


def run_of[C: Person](draft: SceneDraft[C], here: list[EntityId]) -> SceneRun:
    return SceneRun(
        place=draft.place,
        title=draft.title,
        question=draft.question,
        situation=draft.situation,
        here=here,
    )
