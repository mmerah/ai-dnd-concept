from abc import abstractmethod
from collections.abc import Callable, Sequence
from pathlib import Path
from random import Random
from typing import Any

from pydantic import BaseModel

from aidm.core.creation import CreationStep
from aidm.core.entities import Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.io import read_prompt
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    Game,
    Generation,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import DecisionOption
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import NarratorView, Pairs, Panel, PlayerView
from aidm.engines.base import (
    JOIN_PARTY,
    LEAVE_PARTY,
    JoinParty,
    LeaveParty,
    Person,
    character_panel,
    here_panel,
    party_panel,
    party_section,
    render_worldsmith,
    trail_panel,
)
from aidm.engines.scenes.packs import SRD_PACK, ScenePack, read_packs
from aidm.engines.scenes.tools import (
    ENTER,
    KILL,
    LEAVE,
    NEXT_SCENE,
    REVEAL,
    Enter,
    Kill,
    Leave,
    NextDraft,
    NextScene,
    Reveal,
    SceneDraft,
)
from aidm.engines.scenes.world import SCENE_LEFT, SceneWorld
from aidm.engines.scenes.worldsmith import (
    COMPLICATING,
    CROSSING,
    TURNING,
    scene_refusal,
    scene_sections,
)
from aidm.engines.seam import Engine

WORLDSMITH_PROMPT = Path(__file__).parent / "worldsmith.md"
RULES_PROMPT = Path(__file__).parent / "rules.md"
DEPARTURE: Slug = "departure"
COMPLICATION: Slug = "complication"
MOVE_ON = DecisionOption(
    id="move-on", label="Move on", detail="Keep playing, or say where you go and move on."
)
WAY_UNWRITTEN = Fact(
    told=True,
    trace="the way on could not be written",
    card="The way on could not be written. You are still where you were.",
)
COMPLICATION_UNWRITTEN = Fact(
    told=True,
    trace="the complication could not be written",
    card="Nothing new came down on this place after all. You are still where you were.",
)
OPENING = (
    "Write the opening scene of this adventure. Name the one place the player starts in and "
    "who is there. A scene ends when the player leaves it, so a `focus` on somewhere farther "
    "on belongs to a later scene. `cast` is the adventure's people and things, not the "
    "scene's. Write who is met here and who the player will meet farther in. List under "
    "`present` and `hidden` only who is here now. The opening also writes `arc`, in a few "
    "lines or in none."
)
MOVING_ON = (
    "The player takes the way on this scene offered. PLAYER ACTION is where they mean to go. "
    "Play their leaving if nothing stops them. Then call `next_scene` with `pursuit` in their "
    "own words. The crossing is written after this turn."
)


class SceneEngine[C: Person, G: Game[Any], K: ScenePack](Engine[C, G]):
    cast: type[C]
    pack: type[K]
    world_type: type[SceneWorld[C]]
    packs: dict[str, K]
    unwritten = {DEPARTURE: WAY_UNWRITTEN, COMPLICATION: COMPLICATION_UNWRITTEN}
    family_prompt = RULES_PROMPT

    def __init__(self) -> None:
        self.packs = read_packs(self.directory / "packs", self.pack)
        super().__init__()

    def world(self, state: G) -> SceneWorld[C]:
        return state.payload

    def pack_options(self) -> tuple[DecisionOption, ...]:
        return tuple(DecisionOption(id=key, label=pack.name) for key, pack in self.packs.items())

    def validate(self, state: G) -> None:
        super().validate(state)
        if not state.packs:
            raise Refusal(f"a {state.engine!r} game needs at least one table set")
        if missing := sorted(set(state.packs) - set(self.packs)):
            raise Refusal(f"the game names packs not installed: {missing}")

    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> SceneWorld[C]:
        # A restart opens the same scenario again, so the present is marked met on a copy.
        draft: SceneDraft[C] = scenario.payload.model_copy(deep=True)
        if (refused := scene_refusal(draft)) is not None:
            raise Refusal(refused)
        return self.world_type.opening(draft, self.player_of(character), scenario.source)

    def master_sections(self, state: G) -> Pairs:
        world = self.world(state)
        scene = world.run
        return (
            ("SCENE", f"{scene.title}\n{scene.situation}"),
            *((("WHAT THIS SCENE IS ABOUT", scene.focus),) if scene.focus else ()),
            ("YOU PLAY FOR", world.player.line()),
            *self.sheet_sections(state),
            ("HERE WITH THE PLAYER", world.here_lines()),
            *party_section(world.members()),
            ("HIDDEN HERE (the player has not found these)", world.hidden_lines()),
            *((("THE ARC (the player has not found this)", world.arc),) if world.arc else ()),
            *self.glossary(state),
        )

    def sheet_sections(self, _state: G) -> Pairs:
        return ()

    def glossary(self, _state: G) -> Pairs:
        return ()

    def narrator_view(self, state: G) -> NarratorView:
        world = self.world(state)
        scene = world.run
        here = list(world.here())
        return NarratorView(
            place=scene.place,
            title=scene.title,
            focus=scene.focus,
            situation=scene.situation,
            subjects=tuple(member.subject() for member in here),
            speakers=tuple(member.id for member in here if member.alive),
            party=(world.player.id, *world.party),
            sheet=world.player.rows(),
        )

    def player_view(self, state: G) -> PlayerView:
        world = self.world(state)
        player = world.player
        me = player.subject()
        return PlayerView(
            player=me,
            scene_title=world.run.title,
            situation=world.run.situation,
            panels=(
                character_panel(player.rows()),
                *self.panels(state),
                *world.scene_panel(),
                *party_panel(world.members()),
                here_panel(other.subject() for other in world.others()),
                trail_panel(run.title for run in world.runs),
            ),
            prompt=state.pending,
            action=MOVE_ON if world.run.offered else None,
            over=self.over(state),
        )

    def master_tools(self) -> tuple[MasterTool[G], ...]:
        return (
            *super().master_tools(),
            master_tool("reveal", REVEAL, Reveal, self.reveal),
            master_tool("enter", ENTER, Enter, self.enter),
            master_tool("leave", LEAVE, Leave, self.leave),
            master_tool("kill", KILL, Kill, self.kill),
            master_tool("join_party", JOIN_PARTY, JoinParty, self.join_party),
            master_tool("leave_party", LEAVE_PARTY, LeaveParty, self.leave_party),
            master_tool("next_scene", NEXT_SCENE, NextScene, self.next_scene),
        )

    def reveal(self, draft: G, args: Reveal, _rng: Random) -> list[Fact]:
        return self.world(draft).reveal_hidden(args.entity_id)

    def enter(self, draft: G, args: Enter, _rng: Random) -> list[Fact]:
        return self.world(draft).enter(args.entity_id)

    def leave(self, draft: G, args: Leave, _rng: Random) -> list[Fact]:
        return self.world(draft).leave(args.entity_id)

    def kill(self, draft: G, args: Kill, _rng: Random) -> list[Fact]:
        return self.world(draft).kill(args.entity_id)

    def join_party(self, draft: G, args: JoinParty, _rng: Random) -> list[Fact]:
        return self.world(draft).join_party(args.entity_id)

    def leave_party(self, draft: G, args: LeaveParty, _rng: Random) -> list[Fact]:
        return self.world(draft).leave_party(args.entity_id)

    def next_scene(self, draft: G, args: NextScene, _rng: Random) -> list[Fact]:
        if args.pursuit and args.complication:
            raise Refusal("a pursuit or a complication, not both")
        if args.pursuit:
            draft.generation = Generation(operation=DEPARTURE, brief=args.pursuit)
            return [SCENE_LEFT]
        if not args.complication:
            return self.world(draft).offer()
        draft.generation = Generation(operation=COMPLICATION, brief=args.complication)
        return [
            Fact(
                trace=f"the worldsmith writes the complication once this turn ends: "
                f"{args.complication}. Nothing more lands this turn; stop and exit",
            )
        ]

    def act(self, draft: G, action: Slug, _words: str) -> None:
        if action != MOVE_ON.id or not self.world(draft).run.offered:
            raise Refusal("the way on has changed since the page was drawn")
        draft.note(MOVING_ON)

    def pack_step(self) -> CreationStep:
        return CreationStep(id="pack", prompt="Choose a table set", options=self.pack_options())

    def srd_pack(self) -> K:
        pack = self.packs.get(SRD_PACK)
        if pack is None:
            raise Refusal("the SRD table set is not installed")
        return pack

    def render_request(
        self, draft: G, *, guidance: str, intent: str, answer: type[BaseModel]
    ) -> str:
        world = self.world(draft)
        return render_worldsmith(
            role=read_prompt(WORLDSMITH_PROMPT),
            source=world.source,
            scope=draft.scenario.scope,
            family=scene_sections(world),
            intent=intent,
            guidance=guidance,
            answer=answer,
        )

    def render_next(self, draft: G, intent: str) -> str:
        world = self.world(draft)
        if world.arc:
            intent += (
                f"\n\nThe arc as last written:\n{world.arc}\n"
                "Revise `arc` only where what happened warrants it. Leave it empty to keep it."
            )
        return self.render_request(
            draft, guidance=self.guidance(draft.packs), intent=intent, answer=NextDraft[self.cast]
        )

    def render_opening(self, source: str, guidance: str, scope: str) -> str:
        return render_worldsmith(
            role=read_prompt(WORLDSMITH_PROMPT),
            source=source,
            scope=scope,
            family=scene_sections(None),
            intent=OPENING,
            guidance=guidance,
            answer=SceneDraft[self.cast],
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
            source=source,
            payload=draft,
        )

    async def write_next(self, draft: G, intent: str, worldsmith: WorldsmithAnswer) -> NextDraft[C]:
        world = self.world(draft)
        prompt = self.render_next(draft, intent)
        return await worldsmith(
            prompt, NextDraft[self.cast], lambda answer: scene_refusal(answer, world)
        )

    def install(self, draft: G, scene: SceneDraft[C]) -> list[Fact]:
        world = self.world(draft)
        world.apply_scene(scene.model_copy(deep=True))
        trace = f"the scene opens: {scene.title}"
        if travelling := [member.name for member in world.members()]:
            trace += f", the player travelling with {', '.join(travelling)}"
        card = f"New scene: {scene.title}" + (f"\n{scene.focus}" if scene.focus else "")
        return [Fact(trace=trace, told=True, card=card)]

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

        guidance = self.guidance(packs)
        prompt = self.render_opening(source, guidance, meta.scope)
        return await self.compose(worldsmith, prompt, SceneDraft[self.cast], built, playable)

    async def advance(
        self, draft: G, request: Generation, worldsmith: WorldsmithAnswer
    ) -> tuple[tuple[Fact, ...], str | None]:
        left = self.world(draft).run.title
        if request.operation == DEPARTURE:
            scene = await self.write_next(draft, request.brief, worldsmith)
            # The engine's own closing reads the scene being left, so it runs before the install.
            leaving = self.leaving(draft)
            facts = (*leaving, *self.install(draft, scene))
            return facts, CROSSING.format(left=left, pursuit=request.brief)
        asked = COMPLICATING.format(brief=request.brief)
        scene = await self.write_next(draft, asked, worldsmith)
        return tuple(self.install(draft, scene)), TURNING

    def panels(self, _state: G) -> tuple[Panel, ...]:
        return ()

    def leaving(self, _state: G) -> tuple[Fact, ...]:
        return ()

    @abstractmethod
    def guidance(self, picks: Sequence[Slug], /) -> str: ...
