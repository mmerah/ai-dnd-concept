from abc import abstractmethod
from collections.abc import Callable, Sequence
from pathlib import Path
from random import Random
from typing import Any

from pydantic import BaseModel

from aidm.core.entities import Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    Game,
    ScenarioKind,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import DecisionOption, Exchange, SceneRecord
from aidm.core.views import NarratorView, Panel, PlayerView, Sections, render_history
from aidm.engines.base import (
    Pack,
    Person,
    character_panel,
    here_panel,
    read_packs,
    trail_panel,
)
from aidm.engines.hub import (
    CAMPAIGN_OPENING,
    GO_HOME,
    ONE_SHOT_OPENING,
    board_panel,
    check_kind,
    hub_sections,
    job_closed,
    jobs_panel,
    master_tail,
    question_heading,
)
from aidm.engines.scenes.drafts import HubDraft, JobDraft, NextDraft, ReturnDraft, SceneDraft
from aidm.engines.scenes.tools import Enter, Kill, Leave, NextScene, Reveal, SharedChange
from aidm.engines.scenes.world import SceneCanon, SceneWorld
from aidm.engines.scenes.worldsmith import (
    CROSSING,
    opening_canon,
    scene_refusal,
    worldsmith_prompt,
)
from aidm.engines.seam import Engine


class SceneEngine[C: Person, P: Person, G: Game[Any], K: Pack](Engine[G]):
    """The scene lifecycle, once; a subclass says what its rules add."""

    cast: type[C]
    pack: type[K]
    world_type: type[SceneWorld[C, P]]
    hub_phrase: str  # what CAMPAIGN_OPENING asks this engine's hub to be
    finished_note: str = ""  # the note a finished job leaves for the next turn
    packs: dict[str, K]
    worldsmith: str

    def __init__(self) -> None:
        self.packs = read_packs(self.directory / "packs", self.pack)
        self.worldsmith = (Path(__file__).parent / "worldsmith.md").read_text(encoding=ENCODING)
        super().__init__()  # last: `master_tools` reads the packs

    def world(self, state: G) -> SceneWorld[C, P]:
        return (
            state.payload
        )  # narrowed to the shared scene world; an engine's own subclass reads `draft.payload`

    def crossing(self, pursuit: str) -> str | None:
        return CROSSING.format(pursuit=pursuit)

    def pack_options(self) -> tuple[DecisionOption, ...]:
        """The create page's table sets, and the first step of every scene engine's creation."""
        return tuple(DecisionOption(id=key, label=one.name) for key, one in self.packs.items())

    def validate(self, state: G) -> None:
        if not state.packs:
            raise Refusal(f"a {state.engine!r} game needs at least one table set")
        if missing := sorted(set(state.packs) - set(self.packs)):
            raise Refusal(f"the game names packs not installed: {missing}")
        check_kind(state.scenario.kind, self.world(state).hub)

    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> BaseModel:
        if not isinstance(scenario, self.scenario):
            raise Refusal(f"{self.title} received an incompatible scenario")
        canon: SceneCanon[C] = scenario.payload
        return self.world_type.begin(canon, self.player_of(character))

    def over(self, state: G) -> str | None:
        return "You died." if not self.world(state).player.alive else None

    def record(self, state: G, exchange: Exchange) -> None:
        self.world(state).run.exchanges.append(exchange)

    def history(self, state: G) -> tuple[Exchange, ...]:
        return self.world(state).exchanges()

    def scenes(self, state: G) -> tuple[SceneRecord, ...]:
        return self.world(state).scenes()

    def master_sections(self, state: G) -> Sections:
        """Every section stated, hidden canon included: the game master reads all of it."""
        world = self.world(state)
        scene = world.run
        return (
            ("SCENE", f"{scene.title}\n{scene.situation}"),
            (question_heading(world.at_hub), scene.question),
            ("YOU PLAY FOR", world.player.line()),
            *self.sheet_sections(state),
            ("HERE WITH THE PLAYER", self.here_lines(world)),
            *world.party_rows(),
            ("HIDDEN HERE (the player has not found these)", self.hidden_lines(world)),
            *self.glossary(state),
            *master_tail(
                world.hub, world.at_hub, world.board, world.closed_jobs(), world.open_job()
            ),
        )

    def sheet_sections(self, state: G) -> Sections:
        """What the player's sheet adds below YOU PLAY FOR."""
        return ()

    def glossary(self, state: G) -> Sections:
        """What the rules spell out for the master below HIDDEN HERE."""
        return ()

    def narrator_view(self, state: G) -> NarratorView:
        world = self.world(state)
        scene = world.run
        here = list(world.here())
        return NarratorView(
            place=scene.place,
            title=scene.title,
            focus=scene.question,
            situation=scene.situation,
            subjects=tuple(one.subject() for one in here),
            speakers=tuple(one.subject().speaker() for one in here),
        )

    def player_view(self, state: G) -> PlayerView:
        world = self.world(state)
        player = world.player
        me = player.subject()
        return PlayerView(
            player=me,
            panels=(
                character_panel(player.rows()),
                *self.panels(state),
                Panel(title="This scene", rows=world.scene_rows()),
                *board_panel(world.at_hub, world.board),
                *world.party_panel(),
                here_panel(me, (one.subject() for one in world.here() if one.id != player.id)),
                trail_panel(run.title for run in world.job_runs()),
                *jobs_panel(world.closed_jobs()),
            ),
            prompt=state.pending,
            over=self.over(state),
        )

    def shared_change(self, world: SceneWorld[C, P], change: SharedChange) -> list[Fact]:
        """Each arm settles its own consequences, so a call leaves nothing half-done."""
        match change:
            case Reveal():
                return world.reveal_hidden(change.entity_id)
            case Enter():
                return world.enter(change.entity_id)
            case Leave():
                return world.leave(change.entity_id)
            case Kill():
                return world.kill(change.entity_id)

    def next_scene(self, draft: G, args: NextScene, _rng: Random) -> list[Fact]:
        return self.world(draft).settle(args.job_done, args.pursuit)

    def here_lines(self, world: SceneWorld[C, P]) -> str:
        lines = "\n".join(one.line() for one in world.here() if one.id != world.player.id)
        return lines or "- (none)"

    def hidden_lines(self, world: SceneWorld[C, P]) -> str:
        return "\n".join(world.require(one).line() for one in world.hidden()) or "- (none)"

    def hub_rows(self, world: SceneWorld[C, P], *, returning: bool) -> Sections:
        if world.hub is None:
            return ()
        return hub_sections(
            world.runs[0].title,
            world.hub,
            world.board,
            world.closed_jobs(),
            at_hub=world.at_hub,
            returning=returning,
            finished=world.job_done,
        )

    def render_next(self, draft: G, intent: str, answer: type[SceneDraft[C]]) -> str:
        world = self.world(draft)
        # The worldsmith must know who follows the player out of the scene.
        cast = "\n".join(
            (
                world.player.line(detail=world.last_seen(world.player.id)),
                *(
                    one.line(
                        detail="travels with the player"
                        if one.id in world.party
                        else world.last_seen(one.id)
                    )
                    for one in world.cast.values()
                ),
            )
        )
        return worldsmith_prompt(
            self.worldsmith,
            source=world.source,
            history=render_history(world.scenes()),
            cast=cast,
            guidance=self.guidance(draft.packs, campaign=world.hub is not None),
            intent=intent,
            answer=answer,
            hub=(
                *((("THE JOB", terms),) if (terms := world.job_terms()) else ()),
                *self.hub_rows(world, returning=issubclass(answer, ReturnDraft)),
            ),
        )

    def opening_draft(self, kind: ScenarioKind) -> type[SceneDraft[C]]:
        """Pydantic parametrizes the subscript at runtime, so the cast type reaches the schema."""
        return HubDraft[self.cast] if kind == "campaign" else SceneDraft[self.cast]

    def render_opening(self, source: str, guidance: str, kind: ScenarioKind) -> str:
        return worldsmith_prompt(
            self.worldsmith,
            source=source,
            history="(no scenes yet — write the opening)",
            cast="(no cast yet — write the people and things this scene needs)",
            guidance=guidance,
            intent=CAMPAIGN_OPENING.format(hub=self.hub_phrase)
            if kind == "campaign"
            else ONE_SHOT_OPENING,
            answer=self.opening_draft(kind),
        )

    def build_scenario(
        self,
        title: str,
        premise: str,
        packs: tuple[Slug, ...],
        written: SceneDraft[C],
        source: str,
        kind: ScenarioKind,
    ) -> AnyScenario:
        if (refused := scene_refusal(written)) is not None:
            raise Refusal(refused)
        return self.scenario(
            meta=ScenarioMeta(title=title, premise=premise or written.situation, kind=kind),
            engine=self.id,
            packs=packs,
            payload=opening_canon(written, source, self.cast),
        )

    async def write_next(
        self, draft: G, intent: str, worldsmith: WorldsmithAnswer
    ) -> SceneDraft[C]:
        world = self.world(draft)
        returning = world.hub is not None and not world.at_hub and intent == GO_HOME
        model: type[SceneDraft[C]] = (
            ReturnDraft[self.cast]
            if returning
            else JobDraft[self.cast]
            if world.at_hub
            else NextDraft[self.cast]
        )
        prompt = self.render_next(draft, intent, model)
        return await worldsmith(prompt, model, lambda written: scene_refusal(written, world))

    def install(self, draft: G, written: SceneDraft[C]) -> list[Fact]:
        world = self.world(draft)
        world.apply_scene(written.model_copy(deep=True))
        trace = f"the story moves to {written.title}"
        if came := [one.name for one in world.members()]:
            trace += f", the player travelling with {', '.join(came)}"
        label = "Home" if isinstance(written, ReturnDraft) else "New scene"
        card = "\n".join(
            (
                f"{label}: {written.title}",
                f"At stake: {written.question}",
                *([f"The job: {written.job}"] if isinstance(written, JobDraft) else []),
            )
        )
        opened = Fact(kind="scene_opened", trace=trace, told=True, card=card)
        if isinstance(written, ReturnDraft):
            job = world.jobs[-1]
            if job.finished and self.finished_note:
                draft.note(self.finished_note.format(title=job.title))
            return [job_closed(job), opened]
        return [opened]

    async def author(
        self,
        title: str,
        premise: str,
        source: str,
        packs: Sequence[Slug],
        kind: ScenarioKind,
        worldsmith: WorldsmithAnswer,
        playable: Callable[[AnyScenario], str | None],
    ) -> AnyScenario:
        def built(written: SceneDraft[C]) -> AnyScenario:
            return self.build_scenario(title, premise, tuple(packs), written, source, kind)

        guidance = self.guidance(packs, campaign=kind == "campaign")
        prompt = self.render_opening(source, guidance, kind)
        return await self.compose(worldsmith, prompt, self.opening_draft(kind), built, playable)

    def ready(self, state: G) -> bool:
        world = self.world(state)
        return world.run.left is not None or world.at_hub

    async def advance(
        self, draft: G, intent: str, worldsmith: WorldsmithAnswer
    ) -> tuple[Fact, ...]:
        written = await self.write_next(draft, intent, worldsmith)
        # The engine's own closing reads the scene being left, so it runs before the install.
        return (*self.leaving(draft), *self.install(draft, written))

    def panels(self, state: G) -> tuple[Panel, ...]:
        return ()

    def leaving(self, state: G) -> tuple[Fact, ...]:
        return ()

    @abstractmethod
    def guidance(self, picks: Sequence[Slug], *, campaign: bool) -> str: ...
    @abstractmethod
    def player_of(self, character: AnyCharacter) -> P: ...
