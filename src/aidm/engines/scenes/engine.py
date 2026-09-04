from abc import abstractmethod
from collections.abc import Callable, Sequence
from pathlib import Path
from random import Random
from typing import Any

from pydantic import BaseModel

from aidm.core.creation import CreationStep
from aidm.core.entities import Refusal, Slug, parse
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
from aidm.core.play import Commission, DecisionOption
from aidm.core.tools import MasterTool, Play, master_tool
from aidm.core.views import (
    NarratorView,
    Panel,
    PlayerView,
    Sections,
    lines_of,
    render_history,
)
from aidm.engines.base import (
    SRD_PACK,
    Pack,
    Person,
    character_panel,
    here_panel,
    read_packs,
    trail_panel,
)
from aidm.engines.hub import (
    AWAY_BRIEF,
    CAMPAIGN_OPENING,
    GO_HOME,
    ONE_SHOT_OPENING,
    RETURN_BRIEF,
    TAKE_BRIEF,
    WRITE_HUB_SCENE,
    Campaign,
    Job,
    check_kind,
    question_heading,
)
from aidm.engines.scenes.drafts import (
    CastDraft,
    HubDraft,
    JobDraft,
    NextDraft,
    ReturnDraft,
    SceneDraft,
)
from aidm.engines.scenes.tools import (
    Enter,
    JoinParty,
    Kill,
    Leave,
    LeaveParty,
    NextScene,
    Reveal,
    SceneCommission,
    SharedChange,
)
from aidm.engines.scenes.world import SceneCanon, SceneWorld, resolve_ids, run_of
from aidm.engines.scenes.worldsmith import (
    COMMISSION_ASK,
    CROSSING,
    cast_refusal,
    scene_refusal,
    worldsmith_prompt,
)
from aidm.engines.seam import COMMISSION, COMMISSION_BRIEF, Engine

WORLDSMITH = (Path(__file__).parent / "worldsmith.md").read_text(encoding=ENCODING)


class SceneEngine[C: Person, P: Person, G: Game[Any], K: Pack](Engine[P, G]):
    cast: type[C]
    pack: type[K]
    world_type: type[SceneWorld[C, P]]
    hub_phrase: str  # what CAMPAIGN_OPENING asks this engine's hub to be
    finished_note: str = ""  # the note a finished job leaves for the next turn
    packs: dict[str, K]

    def __init__(self) -> None:
        self.packs = read_packs(self.directory / "packs", self.pack)
        super().__init__()  # last: `master_tools` reads the packs

    def world(self, state: G) -> SceneWorld[C, P]:
        return state.payload

    def crossing(self, state: G, pursuit: str) -> str | None:
        return CROSSING.format(left=self.world(state).run.title, pursuit=pursuit)

    def pack_options(self) -> tuple[DecisionOption, ...]:
        """The create page's table sets, and the first step of every scene engine's creation."""
        return tuple(DecisionOption(id=key, label=pack.name) for key, pack in self.packs.items())

    def validate(self, state: G) -> None:
        if not state.packs:
            raise Refusal(f"a {state.engine!r} game needs at least one table set")
        if missing := sorted(set(state.packs) - set(self.packs)):
            raise Refusal(f"the game names packs not installed: {missing}")
        check_kind(state.scenario.kind, self.world(state).campaign)

    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> SceneWorld[C, P]:
        self.check_scenario(scenario)
        canon: SceneCanon[C] = scenario.payload
        return self.world_type.begin(canon, self.player_of(character))

    def master_sections(self, state: G) -> Sections:
        """Every section stated, hidden canon included: the game master reads all of it."""
        world = self.world(state)
        scene = world.run
        return (
            ("SCENE", f"{scene.title}\n{scene.situation}"),
            (question_heading(world.at_hub), scene.question),
            ("YOU PLAY FOR", world.player.line()),
            *self.sheet_sections(state),
            ("HERE WITH THE PLAYER", world.here_lines()),
            *world.party_rows(),
            ("HIDDEN HERE (the player has not found these)", world.hidden_lines()),
            *((("THE ARC (the player has not found this)", world.arc),) if world.arc else ()),
            *self.glossary(state),
            *(() if world.campaign is None else world.campaign.tail(at_hub=world.at_hub)),
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
            subjects=tuple(member.subject() for member in here),
            speakers=tuple(member.id for member in here),
        )

    def player_view(self, state: G) -> PlayerView:
        world = self.world(state)
        player = world.player
        campaign = world.campaign
        me = player.subject()
        return PlayerView(
            player=me,
            panels=(
                character_panel(player.rows()),
                *self.panels(state),
                Panel(title="This scene", rows=world.scene_rows()),
                *(() if campaign is None else campaign.board_panel(at_hub=world.at_hub)),
                *world.party_panel(),
                here_panel(
                    me, (member.subject() for member in world.here() if member.id != player.id)
                ),
                trail_panel(run.title for run in world.job_runs()),
                *(() if campaign is None else campaign.jobs_panel()),
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
            case JoinParty():
                return world.join_party(change.entity_id)
            case LeaveParty():
                return world.leave_party(change.entity_id)

    def next_scene(self, draft: G, args: NextScene, _rng: Random) -> list[Fact]:
        return self.world(draft).settle(args.job_done, args.pursuit)

    def commission_tool(self) -> MasterTool[G]:
        return master_tool(
            COMMISSION,
            COMMISSION_BRIEF
            + " A person, a thing or a rumour, each a cast entry. Read THE ARC first and ask "
            "with it in view; the worldsmith may bend it to hold what you ask for.",
            SceneCommission,
            self.ask_worldsmith,
        )

    def pack_step(self) -> CreationStep:
        return CreationStep(id="pack", prompt="Choose a table set", options=self.pack_options())

    def srd_pack(self) -> K:
        pack = self.packs.get(SRD_PACK)
        if pack is None:
            raise Refusal("the SRD table set is not installed")
        return pack

    def hub_sections(
        self, world: SceneWorld[C, P], *, returning: bool, reopening: Job | None
    ) -> Sections:
        campaign = world.campaign
        if campaign is None:
            return ()
        brief = (
            WRITE_HUB_SCENE + RETURN_BRIEF
            if returning
            else TAKE_BRIEF
            if world.at_hub
            else AWAY_BRIEF
        )
        return campaign.hub_block(
            world.runs[0].title, brief, world.records(), returning=returning, reopening=reopening
        )

    def render_next(
        self,
        draft: G,
        intent: str,
        answer: type[BaseModel],
        *,
        reopening: Job | None = None,
        asked: str = "",
    ) -> str:
        """A scene write, or a commission: `answer` says which sections the intent needs."""
        world = self.world(draft)
        returning, follows_arc = issubclass(answer, ReturnDraft), issubclass(answer, NextDraft)
        if world.arc and follows_arc:
            intent += (
                f"\n\nThe arc as last written: {world.arc}. Rewrite `arc` so it follows what "
                "happened."
            )
        return worldsmith_prompt(
            WORLDSMITH,
            source=world.source,
            history=render_history(world.scenes()),
            cast=world.cast_lines(),
            guidance=self.guidance(draft.packs, campaign=world.campaign is not None),
            intent=intent,
            answer=answer,
            hub=self.hub_sections(world, returning=returning, reopening=reopening),
            asked=asked,
        )

    def opening_draft(self, kind: ScenarioKind) -> type[SceneDraft[C]]:
        """Pydantic parametrizes the subscript at runtime, so the cast type reaches the schema."""
        return HubDraft[self.cast] if kind == "campaign" else SceneDraft[self.cast]

    def render_opening(self, source: str, guidance: str, kind: ScenarioKind) -> str:
        return worldsmith_prompt(
            WORLDSMITH,
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
        self, meta: ScenarioMeta, packs: tuple[Slug, ...], draft: SceneDraft[C], source: str
    ) -> AnyScenario:
        if (refused := scene_refusal(draft)) is not None:
            raise Refusal(refused)
        return self.scenario(
            meta=meta.with_premise(draft.situation),
            engine=self.id,
            packs=packs,
            payload=self.opening_canon(draft, source),
        )

    def opening_canon(self, draft: SceneDraft[C], source: str) -> SceneCanon[C]:
        """Parametrized on the engine's cast, so the canon revalidates as its own people."""
        cast = draft.cast
        present = resolve_ids(draft.present, cast, "present")
        hidden = resolve_ids(draft.hidden, cast, "hidden")
        for entity_id in present:
            cast[entity_id].known = True
        campaign = (
            Campaign(place=draft.place, board=draft.offers) if isinstance(draft, HubDraft) else None
        )
        return parse(
            SceneCanon[self.cast],
            {
                "cast": cast,
                "opening": run_of(draft, [*present, *hidden]),
                "source": source,
                "campaign": campaign,
                "arc": draft.arc,
            },
        )

    async def write_next(
        self, draft: G, intent: str, worldsmith: WorldsmithAnswer, *, reopening: Job | None = None
    ) -> SceneDraft[C]:
        world = self.world(draft)
        returning = world.campaign is not None and not world.at_hub and intent == GO_HOME
        model: type[SceneDraft[C]] = (
            ReturnDraft[self.cast]
            if returning
            else JobDraft[self.cast]
            if world.at_hub
            else NextDraft[self.cast]
        )
        later = draft.on_order()
        asked = lines_of(f"- a {c.kind}: {c.brief}" for c in later) if later else ""
        prompt = self.render_next(draft, intent, model, reopening=reopening, asked=asked)
        return await worldsmith(
            prompt, model, lambda answer: scene_refusal(answer, world, later, reopening)
        )

    def install(
        self, draft: G, scene: SceneDraft[C], *, reopening: Job | None = None
    ) -> list[Fact]:
        world = self.world(draft)
        world.apply_scene(scene.model_copy(deep=True), reopening=reopening)
        draft.commissions.clear()  # every scene draft carries `cast`, and the bar counted it
        trace = f"the story moves to {scene.title}"
        if travelling := [member.name for member in world.members()]:
            trace += f", the player travelling with {', '.join(travelling)}"
        label = "Home" if isinstance(scene, ReturnDraft) else "New scene"
        card = "\n".join(
            (
                f"{label}: {scene.title}",
                f"At stake: {scene.question}",
                *([f"The job: {scene.job}"] if isinstance(scene, JobDraft) else []),
            )
        )
        opened = Fact(kind="scene_opened", trace=trace, told=True, card=card)
        # `apply_scene` has refused a return with no campaign, so the narrowing is for the types.
        if isinstance(scene, ReturnDraft) and world.campaign is not None:
            job = world.campaign.jobs[-1]
            if job.finished and self.finished_note:
                draft.note(self.finished_note.format(title=job.title))
            return [job.closed(), opened]
        return [opened]

    def render_commission(self, draft: G, asked: Commission) -> str:
        world = self.world(draft)
        intent = COMMISSION_ASK.format(kind=asked.kind, brief=asked.brief)
        if world.arc:
            intent += (
                f"\n\nThe arc as last written: {world.arc}. Rewrite `arc` only where it must "
                "bend to hold the new entry; leave it empty to keep it."
            )
        return self.render_next(draft, intent, CastDraft[self.cast])

    async def fulfil(self, draft: G, asked: Commission, worldsmith: WorldsmithAnswer) -> Play[G]:
        world = self.world(draft)
        written = await worldsmith(
            self.render_commission(draft, asked),
            CastDraft[self.cast],
            lambda answer: cast_refusal(answer, world),
        )
        return lambda candidate, _rng: tuple(self.install_cast(candidate, asked, written))

    def install_cast(self, draft: G, asked: Commission, written: CastDraft[C]) -> list[Fact]:
        world = self.world(draft)
        entity_id = next(iter(written.cast))
        new = entity_id not in world.cast
        world.cast = world.merged_cast(written.cast)
        world.arc = written.arc or world.arc
        draft.withdraw(asked)
        entry = world.cast[entity_id]  # a known id keeps the world's name
        trace = (
            f"the worldsmith wrote {entry.label}: {entry.brief}; bring them in with `enter`"
            if new
            else f"the worldsmith rewrote {entry.label}: {entry.brief}"
        )
        return [Fact(kind="commissioned", trace=trace)]

    async def author(
        self,
        meta: ScenarioMeta,
        source: str,
        packs: Sequence[Slug],
        worldsmith: WorldsmithAnswer,
        playable: Callable[[AnyScenario], str | None],
    ) -> AnyScenario:
        def built(draft: SceneDraft[C]) -> AnyScenario:
            return self.build_scenario(meta, tuple(packs), draft, source)

        kind = meta.kind
        guidance = self.guidance(packs, campaign=kind == "campaign")
        prompt = self.render_opening(source, guidance, kind)
        return await self.compose(worldsmith, prompt, self.opening_draft(kind), built, playable)

    def ready(self, state: G) -> bool:
        world = self.world(state)
        return world.run.left is not None or world.at_hub

    async def advance(
        self, draft: G, intent: str, worldsmith: WorldsmithAnswer
    ) -> tuple[Fact, ...]:
        reopening = self.reopening(draft, intent)
        scene = await self.write_next(draft, intent, worldsmith, reopening=reopening)
        # The engine's own closing reads the scene being left, so it runs before the install.
        return (*self.leaving(draft), *self.install(draft, scene, reopening=reopening))

    def panels(self, state: G) -> tuple[Panel, ...]:
        return ()

    def leaving(self, state: G) -> tuple[Fact, ...]:
        return ()

    @abstractmethod
    def guidance(self, picks: Sequence[Slug], *, campaign: bool) -> str: ...
