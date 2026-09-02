import json
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Mutable, Slug, require_unique
from aidm.core.facts import Fact
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
    Debrief,
    Job,
    Offer,
    Stop,
    check_board,
    check_kind,
    closed_jobs,
    hub_sections,
    job_start,
    place_unmet,
)
from aidm.engines.scenes.drafts import JobDraft, NextDraft, ReturnDraft, SceneDraft

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


class Scene(Frozen):
    # Names the art cache entry, so returning to a place reuses its picture.
    place: Slug
    title: str
    # Public: the player reads it; settling it ends the scene.
    question: str = Field(min_length=10)
    situation: str = Field(min_length=40)
    # What `question` does not say: never narrated, never in a view.
    secret: str = ""
    debrief: Debrief | None = None  # the hub's word on the job just left; hub runs after the first
    job: str = ""  # the job as taken; on the scene that leaves the hub only


class SceneRun(Mutable):
    scene: Scene
    present: list[CheckedEntityId] = Field(default_factory=list)
    hidden: list[CheckedEntityId] = Field(default_factory=list)
    exchanges: list[Exchange] = Field(default_factory=list)
    # None while open; "" once settled here; the player's words when they left for elsewhere
    left: str | None = None
    # The master's word: settling this scene finished the job the player walked out on.
    job_done: bool = False
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
    opening: Scene
    present: list[CheckedEntityId] = Field(default_factory=list)
    hidden: list[CheckedEntityId] = Field(default_factory=list)
    source: str = ""
    hub: Slug | None = None
    board: tuple[Offer, ...] = ()

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
        check_filing(self.cast)
        check_named(self.present, self.hidden, self.cast)
        check_hub(self.hub, self.board, (SceneRun(scene=self.opening),))
        return self


class SceneScenario[C: Person](Mutable):
    world: SceneCanon[C]


class SceneWorld[C: Person, P: Person](Mutable):
    """The world as a sequence of scenes: the player is a sheet, never a cast entry."""

    runs: list[SceneRun] = Field(min_length=1)
    source: str = ""
    hub: Slug | None = None
    board: tuple[Offer, ...] = ()
    cast: dict[EntityId, C] = Field(default_factory=dict)
    player: P
    party: list[EntityId] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_hub(self.hub, self.board, self.runs)
        check_filing(self.cast)
        check_named(self.run.present, self.run.hidden, self.cast)
        if not self.player.known:
            raise ValueError("the player is unknown to themselves")
        if self.player.id in self.cast:
            raise ValueError("the player is in the cast")
        if self.player.id in (*self.run.present, *self.run.hidden):
            raise ValueError("the player is in every scene and is never listed in it")
        if self.player.id in self.party:
            raise ValueError("the player cannot travel with themselves")
        check_party(self.party, self.cast)
        if left := sorted(set(self.party) - set(self.run.present)):
            raise ValueError(f"the party is in every scene; {left} are not in this one")
        return self

    @property
    def run(self) -> SceneRun:
        return self.runs[-1]

    @property
    def current(self) -> Scene:
        return self.run.scene

    @property
    def at_hub(self) -> bool:
        return self.hub is not None and self.current.place == self.hub

    @property
    def job_done(self) -> bool:
        """The master's verdict on the open job: read before a return is appended."""
        return any(run.job_done for run in self.job_runs())

    @property
    def job(self) -> str:
        """What the player walked out on, as the scene that left the hub wrote it."""
        return next((run.scene.job for run in self.job_runs() if run.scene.job), "")

    def stops(self) -> tuple[Stop, ...]:
        return tuple(
            Stop(
                place=run.scene.place,
                title=run.scene.title,
                debrief=run.scene.debrief,
                job=run.scene.job,
            )
            for run in self.runs
        )

    def job_runs(self) -> list[SceneRun]:
        return self.runs[job_start(self.stops()) :]

    def jobs(self) -> tuple[Job, ...]:
        return closed_jobs(self.hub, self.stops())

    def exchanges(self) -> tuple[Exchange, ...]:
        return tuple(one for run in self.runs for one in run.exchanges)

    def scenes(self) -> tuple[SceneRecord, ...]:
        return tuple(
            SceneRecord(
                title=run.scene.title,
                question=run.scene.question,
                recap=run.recap,
                exchanges=tuple(run.exchanges),
            )
            for run in self.job_runs()
        )

    def last_seen(self, entity_id: EntityId) -> str:
        """The prompt's own line; scanning back keeps what the story dropped from being lost."""
        for run in reversed(self.runs):
            if entity_id in (*run.present, *run.hidden):
                return f"last seen in: {run.scene.title}"
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
        if one.id not in self.run.present:
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
        if one.id not in self.run.present:
            raise ValueError(
                f"{entity_id!r} is not here with the player. "
                "Bring them here first, or act on who is here."
            )
        return one

    def here(self) -> Iterator[C | P]:
        yield self.player
        for entity_id in self.run.present:
            yield self.cast[entity_id]

    def label(self, entity: Person) -> str:
        return labeled(entity, self.player.id)

    def reveal(self, entity: Person) -> list[Fact]:
        return reveal(entity, self.player.id)

    def reveal_hidden(self, entity_id: EntityId) -> list[Fact]:
        """The discovery itself, distinct from what `enter` tells about someone walking in."""
        one = self.require(entity_id)
        if entity_id not in self.run.hidden:
            raise ValueError(f"{entity_id!r} is not hidden here")
        self.run.hidden.remove(one.id)
        self.run.present.append(one.id)
        facts = self.reveal(one)
        if not facts:
            raise ValueError(f"the player has already met {one.name}")
        return [facts[0].model_copy(update={"card": sentence(f"{one.name} discovered")})]

    def enter(self, entity_id: EntityId) -> list[Fact]:
        if entity_id == self.player.id:
            raise ValueError("the player is in every scene; move the story on instead")
        one = self.require(entity_id)
        if one.id in self.run.present:
            raise ValueError(f"{one.name} is already here")
        if one.id in self.run.hidden:
            raise ValueError(f"{one.name} is hidden here; reveal them instead")
        self.run.present.append(one.id)
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
        self.run.present.remove(one.id)
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
        if job_done and (self.hub is None or self.at_hub):
            raise ValueError("no job is open here")
        self.run.left = pursuit
        self.run.job_done = job_done
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
        finished = self.job_done  # the master's verdict on the job the return is closing
        self.cast = self.merged_cast(draft)
        everyone: Mapping[EntityId, Entity] = {self.player.id: self.player, **self.cast}
        present = resolve_ids(draft.present, everyone, "present")
        hidden = resolve_ids(draft.hidden, everyone, "hidden")
        for one in present:
            self.cast[one].known = True
        if isinstance(draft, NextDraft):
            self.run.recap = draft.recap
        self.runs.append(
            SceneRun(
                scene=scene_of(draft, finished),
                present=[*self.party, *present],
                hidden=hidden,
            )
        )

    def hub_rows(self, *, returning: bool) -> Rows:
        if self.hub is None:
            return ()
        return hub_sections(
            self.runs[0].scene.title,
            self.hub,
            self.board,
            self.jobs(),
            at_hub=self.at_hub,
            returning=returning,
            finished=self.job_done,
        )

    def scene_rows(self) -> tuple[PanelRow, ...]:
        rows = [PanelRow(label=self.current.question, detail="")]
        if self.job:
            rows.append(PanelRow(label="The job", detail=self.job))
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
        return "\n".join(entity_line(self.require(one)) for one in self.run.hidden) or "- (none)"

    def render_worldsmith(
        self, intent: str, guidance: str, answer: type[SceneDraft[C]], *, role: str
    ) -> str:
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
            role,
            source=self.source,
            history=render_history(self.scenes()),
            cast=cast,
            guidance=guidance,
            intent=intent,
            answer=answer,
            hub=(
                *((("THE JOB", self.job),) if self.job else ()),
                *self.hub_rows(returning=issubclass(answer, ReturnDraft)),
            ),
        )


class SceneState[C: Person, P: Person](Mutable):
    world: SceneWorld[C, P]


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


def new_world[C: Person, P: Person](canon: SceneCanon[C], player: P) -> SceneWorld[C, P]:
    """The player is added by code and never authored, so no scenario can claim their id."""
    canon = deepcopy(canon)
    return SceneWorld(
        cast=canon.cast,
        player=player,
        runs=[
            SceneRun(scene=canon.opening, present=list(canon.present), hidden=list(canon.hidden))
        ],
        source=canon.source,
        hub=canon.hub,
        board=canon.board,
    )


def check_game[S: SceneState[Any, Any]](packs: Collection[str], state: Game[S]) -> None:
    if not state.packs:
        raise ValueError(f"a {state.engine!r} game needs at least one table set")
    if missing := sorted(set(state.packs) - set(packs)):
        raise ValueError(f"the game names packs not installed: {missing}")
    check_kind(state.scenario.kind, state.payload.world.hub)


def way_open[S: SceneState[Any, Any]](state: Game[S]) -> bool:
    world = state.payload.world
    return world.run.left is not None or world.at_hub


def player_over[S: SceneState[Any, Any]](state: Game[S]) -> str | None:
    return "You died." if not state.payload.world.player.alive else None


def check_named(
    present: Sequence[EntityId], hidden: Sequence[EntityId], cast: Mapping[EntityId, Entity]
) -> None:
    require_unique("ids in the scene", (*present, *hidden))
    for who in (*present, *hidden):
        if who not in cast:
            raise ValueError(f"scene names {who!r}, who is not in the cast")
    for who in hidden:
        if cast[who].known:
            raise ValueError(f"{who!r} is hidden here but the player has already met them")
    for who in present:
        if not cast[who].known:
            raise ValueError(f"{who!r} is here but the player has not met them")


def check_hub(hub: Slug | None, board: Sequence[Offer], runs: Sequence[SceneRun]) -> None:
    check_board(hub, board)
    for index, run in enumerate(runs):
        if run.job_done and (hub is None or run.scene.place == hub):
            raise ValueError(f"run {index} has a job done with no job open")
    if hub is None:
        for index, run in enumerate(runs):
            if run.scene.debrief is not None:
                raise ValueError(f"run {index} has a debrief with no hub")
        return
    first = runs[0].scene
    if first.place != hub or first.debrief is not None:
        raise ValueError(f"run 0 does not open at hub {hub!r} with no debrief")
    for index in range(1, len(runs)):
        scene = runs[index].scene
        at_hub = scene.place == hub
        if at_hub and scene.debrief is None:
            raise ValueError(f"run {index} is at the hub with no debrief")
        if not at_hub and scene.debrief is not None:
            raise ValueError(f"run {index} is away from the hub with a debrief")
        if at_hub and runs[index - 1].scene.place == hub:
            raise ValueError(f"run {index} is a hub run right after a hub run")


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
    role: str,
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
            ("YOUR ROLE", role),
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


def scene_of[C: Person](draft: SceneDraft[C], finished: bool) -> Scene:
    return Scene(
        place=draft.place,
        title=draft.title,
        question=draft.question,
        situation=draft.situation,
        secret=draft.secret,
        job=draft.job if isinstance(draft, JobDraft) else "",
        debrief=Debrief(text=draft.debrief, finished=finished)
        if isinstance(draft, ReturnDraft)
        else None,
    )
