import json
from abc import abstractmethod
from collections.abc import Callable, Sequence
from pathlib import Path
from random import Random
from typing import Any

from aidm.core.creation import CreationStep
from aidm.core.entities import Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    Game,
    Generation,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import DecisionOption
from aidm.core.prompt import Pairs
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import NarratorView, Panel, PlayerView
from aidm.engines.base import (
    Person,
    character_panel,
    here_panel,
    party_panel,
    party_section,
    trail_panel,
)
from aidm.engines.scenes.packs import SRD_PACK, ScenePack, read_packs
from aidm.engines.scenes.tools import (
    ENTER,
    LEAVE,
    NEXT_SCENE,
    Enter,
    Leave,
    NextDraft,
    NextScene,
    SceneDraft,
)
from aidm.engines.scenes.world import SCENE_LEFT, SceneWorld
from aidm.engines.scenes.worldsmith import (
    COMPLICATING,
    CROSSING,
    TURNING,
    check_scene,
    scene_sections,
)
from aidm.engines.seam import Engine, Request, Written, compose

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


class SceneEngine[C: Person, G: Game[Any], K: ScenePack](Engine[C, C, G]):
    pack: type[K]
    world: type[SceneWorld[C]]
    packs: dict[Slug, K]
    family_dir = Path(__file__).parent

    def __init__(self) -> None:
        self.packs = read_packs(self.directory / "packs", self.pack)
        if SRD_PACK not in self.packs:
            raise ValueError(f"the {self.id!r} engine ships no {SRD_PACK!r} pack")
        super().__init__()

    def world_of(self, state: G) -> SceneWorld[C]:
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
        # a restart reopens the same scenario file
        draft: SceneDraft[C] = scenario.payload.model_copy(deep=True)
        check_scene(draft)
        return self.world.opening(draft, self.player_of(character), scenario.source)

    def master_sections(self, state: G) -> Pairs:
        world = self.world_of(state)
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

    def family_sections(self, draft: G | None) -> Pairs:
        return scene_sections(
            None if draft is None else self.world_of(draft), () if draft is None else draft.log
        )

    def narrator_view(self, state: G) -> NarratorView:
        world = self.world_of(state)
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
            sheet=world.sheet_rows(),
        )

    def player_view(self, state: G) -> PlayerView:
        world = self.world_of(state)
        player = world.player
        me = player.subject()
        return PlayerView(
            player=me,
            scene_title=world.run.title,
            situation=world.run.situation,
            panels=(
                character_panel(world.sheet_rows()),
                *self.panels(state),
                *world.scene_panel(),
                *party_panel(world.members()),
                here_panel(other.subject() for other in world.others()),
                trail_panel(run.title for run in world.runs),
            ),
            decision=state.pending,
            action=MOVE_ON if world.run.offered else None,
            over=self.over(state),
        )

    def master_tools(self) -> tuple[MasterTool[G], ...]:
        return (
            *super().master_tools(),
            master_tool("enter", ENTER, Enter, self.enter),
            master_tool("leave", LEAVE, Leave, self.leave),
            master_tool("next_scene", NEXT_SCENE, NextScene, self.next_scene),
        )

    def enter(self, draft: G, args: Enter, _rng: Random) -> list[Fact]:
        return self.world_of(draft).enter(args.entity_id)

    def leave(self, draft: G, args: Leave, _rng: Random) -> list[Fact]:
        return self.world_of(draft).leave(args.entity_id)

    def next_scene(self, draft: G, args: NextScene, _rng: Random) -> list[Fact]:
        if args.pursuit:
            draft.generation = Generation(operation=DEPARTURE, detail=args.pursuit)
            return [SCENE_LEFT]
        if not args.complication:
            return self.world_of(draft).offer()
        draft.generation = Generation(operation=COMPLICATION, detail=args.complication)
        return [
            Fact(
                trace=f"the worldsmith writes the complication once this turn ends: "
                f"{args.complication}. Nothing more lands this turn; stop and exit",
            )
        ]

    def act(self, draft: G, action: Slug, _words: str) -> None:
        if action != MOVE_ON.id or not self.world_of(draft).run.offered:
            raise Refusal("the way on has changed since the page was drawn")
        draft.note(MOVING_ON)

    def pack_step(self) -> CreationStep:
        return CreationStep(id="pack", label="Choose a table set", options=self.pack_options())

    def srd_pack(self) -> K:
        return self.packs[SRD_PACK]

    def pack_content(
        self,
        picks: Sequence[Slug],
        *,
        include: set[str] | None = None,
        exclude_defaults: bool = False,
    ) -> str:
        selected = {
            pack_id: self.packs[pack_id].model_dump(
                mode="json", include=include, exclude_defaults=exclude_defaults
            )
            for pack_id in picks
        }
        return f"SELECTED PACK CONTENT\n{json.dumps(selected)}"

    def first_pack(self, draft: G) -> K:
        return self.packs[draft.packs[0]]

    def render_next(self, draft: G, intent: str) -> str:
        world = self.world_of(draft)
        if world.arc:
            intent += (
                f"\n\nThe arc as last written:\n{world.arc}\n"
                "Revise `arc` only where what happened warrants it. Leave it empty to keep it."
            )
        return self.render_request(
            draft, guidance=self.guidance(draft.packs), intent=intent, answer=NextDraft[self.member]
        )

    async def write_next(self, draft: G, intent: str, worldsmith: WorldsmithAnswer) -> NextDraft[C]:
        world = self.world_of(draft)
        prompt = self.render_next(draft, intent)
        return await worldsmith(
            prompt, NextDraft[self.member], lambda answer: check_scene(answer, world)
        )

    def install(self, draft: G, scene: SceneDraft[C]) -> list[Fact]:
        world = self.world_of(draft)
        if isinstance(scene, NextDraft):
            draft.log[-1].recap = scene.recap
        world.apply_scene(scene)
        self.open_chapter(draft)
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
        check: Callable[[AnyScenario], None],
    ) -> AnyScenario:
        def built(draft: SceneDraft[C]) -> AnyScenario:
            return self.build_scenario(meta, tuple(packs), draft, source, draft.situation)

        guidance = self.guidance(packs)
        prompt = self.render_opening(
            source, meta.scope, intent=OPENING, guidance=guidance, answer=SceneDraft[self.member]
        )
        return await compose(worldsmith, prompt, SceneDraft[self.member], built, check)

    def worldsmith_requests(self) -> dict[Slug, Request[G]]:
        return {
            **super().worldsmith_requests(),
            DEPARTURE: Request(WAY_UNWRITTEN, self.depart),
            COMPLICATION: Request(COMPLICATION_UNWRITTEN, self.complicate),
        }

    async def depart(self, draft: G, request: Generation, worldsmith: WorldsmithAnswer) -> Written:
        left = self.world_of(draft).run.title
        scene = await self.write_next(draft, request.detail, worldsmith)
        # The engine's own closing reads the scene being left, so it runs before the install.
        facts = [*self.leaving(draft), *self.install(draft, scene)]
        return tuple(facts), CROSSING.format(left=left, pursuit=request.detail)

    async def complicate(
        self, draft: G, request: Generation, worldsmith: WorldsmithAnswer
    ) -> Written:
        scene = await self.write_next(draft, COMPLICATING.format(brief=request.detail), worldsmith)
        return tuple(self.install(draft, scene)), TURNING

    def panels(self, _state: G) -> tuple[Panel, ...]:
        return ()

    def leaving(self, _draft: G) -> list[Fact]:
        """The engine's own closing before the next scene installs; it may change the draft."""
        return []

    @abstractmethod
    def guidance(self, picks: Sequence[Slug], /) -> str: ...
