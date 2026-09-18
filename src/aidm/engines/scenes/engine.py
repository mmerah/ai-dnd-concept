from collections.abc import Callable
from pathlib import Path
from random import Random
from typing import Any

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
from aidm.core.prompt import Sections, render_history, section_if
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
from aidm.engines.packs import Pack
from aidm.engines.scenes.tools import (
    ENTER,
    LEAVE,
    MOVING_ON,
    NEXT_SCENE,
    SCENE_LEFT,
    Enter,
    Leave,
    NextScene,
)
from aidm.engines.scenes.world import NextProposal, SceneProposal, SceneWorld
from aidm.engines.scenes.worldsmith import (
    COMPLICATING,
    CROSSING,
    MEANWHILE_NUDGE,
    OPENING,
    TURNING,
    check_scene,
)
from aidm.engines.seam import Engine, Request, Written

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


class SceneEngine[C: Person, W: SceneWorld[Any], K: Pack](Engine[C, C, W, K]):
    family_dir = Path(__file__).parent
    opening_sections = (
        ("SCENES SO FAR", "(no scenes yet — write the opening)"),
        ("THE WHOLE CAST", "(no cast yet — write the people and things this scene needs)"),
        ("THE SCENE NOW", "(none yet)"),
    )

    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> W:
        # Copied: a restart reopens the same scenario file.
        draft: SceneProposal[C] = scenario.opening.model_copy(deep=True)
        check_scene(draft)
        return self.world.opening(draft, self.player_of(character))

    def master_sections(self, state: Game[W]) -> Sections:
        world = state.world
        scene = world.run
        return (
            ("SCENE", f"{scene.title}\n{scene.situation}"),
            *section_if("WHAT THIS SCENE IS ABOUT", scene.focus),
            ("YOU PLAY FOR", world.player.line()),
            *self.sheet_sections(state),
            ("HERE WITH THE PLAYER", world.here_lines()),
            *party_section(world.members()),
            ("HIDDEN HERE (the player has not found these)", world.hidden_lines()),
            *section_if("THE ARC (the player has not found this)", world.arc),
            *self.packs.rules_section(state.pack_id),
        )

    def sheet_sections(self, _state: Game[W]) -> Sections:
        return ()

    def family_sections(self, draft: Game[W]) -> Sections:
        world = draft.world
        return (
            ("SCENES SO FAR", render_history(draft.log)),
            ("THE WHOLE CAST", world.cast_lines()),
            ("THE SCENE NOW", world.scene_lines()),
        )

    def narrator_view(self, state: Game[W]) -> NarratorView:
        world = state.world
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

    def player_view(self, state: Game[W]) -> PlayerView:
        world = state.world
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

    def master_tools(self) -> tuple[MasterTool[Game[W]], ...]:
        return (
            *super().master_tools(),
            master_tool("enter", ENTER, Enter, lambda d, a, _: d.world.enter(a.target_id)),
            master_tool("leave", LEAVE, Leave, lambda d, a, _: d.world.leave(a.target_id)),
            master_tool("next_scene", NEXT_SCENE, NextScene, self.next_scene),
        )

    def next_scene(self, draft: Game[W], args: NextScene, _rng: Random) -> list[Fact]:
        if args.pursuit:
            draft.generation = Generation(operation=DEPARTURE, detail=args.pursuit)
            return [SCENE_LEFT]
        if not args.complication:
            return draft.world.offer()
        draft.generation = Generation(operation=COMPLICATION, detail=args.complication)
        return [
            Fact(
                trace=f"the worldsmith writes the complication once this turn ends: "
                f"{args.complication}. Nothing more lands this turn; stop and exit",
            )
        ]

    def act(self, draft: Game[W], action: Slug, _words: str) -> None:
        if action != MOVE_ON.id or not draft.world.run.offered:
            raise Refusal("the way on has changed since the page was drawn")
        draft.note(MOVING_ON)

    def render_next(self, draft: Game[W], intent: str) -> str:
        world = draft.world
        if world.arc:
            intent += (
                f"\n\nThe arc as last written:\n{world.arc}\n"
                "Revise `arc` only where what happened warrants it. Leave it empty to keep it."
            )
        if world.meanwhile_due:
            intent += f"\n\n{MEANWHILE_NUDGE}"
        return self.render_request(
            draft,
            guidance=self.guidance(draft.pack_id, opening=False),
            intent=intent,
            answer=NextProposal[self.member],
        )

    async def write_next(
        self, draft: Game[W], intent: str, worldsmith: WorldsmithAnswer
    ) -> NextProposal[C]:
        world = draft.world
        prompt = self.render_next(draft, intent)
        return await worldsmith(
            prompt, NextProposal[self.member], lambda answer: check_scene(answer, world)
        )

    def install(self, draft: Game[W], scene: SceneProposal[C]) -> list[Fact]:
        world = draft.world
        if isinstance(scene, NextProposal):
            draft.log[-1].recap = scene.recap
        world.apply_scene(scene)
        world.disarm()
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
        pack_id: Slug,
        worldsmith: WorldsmithAnswer,
        check: Callable[[AnyScenario], None],
    ) -> AnyScenario:
        def built(draft: SceneProposal[C]) -> AnyScenario:
            return self.build_scenario(meta, pack_id, draft, source, draft.situation)

        guidance = self.guidance(pack_id, opening=True)
        model = SceneProposal[self.member]
        prompt = self.render_worldsmith(
            source, meta.scope, self.opening_sections, OPENING, guidance, model
        )
        return built(await worldsmith(prompt, model, lambda answer: check(built(answer))))

    def worldsmith_requests(self) -> dict[Slug, Request[Game[W]]]:
        return {
            **super().worldsmith_requests(),
            DEPARTURE: Request(WAY_UNWRITTEN, self.depart),
            COMPLICATION: Request(COMPLICATION_UNWRITTEN, self.complicate),
        }

    async def depart(
        self, draft: Game[W], request: Generation, worldsmith: WorldsmithAnswer
    ) -> Written:
        left = draft.world.run.title
        exchanges = draft.exchanges()
        # The master's `pursuit` is free text; the narrator reads the player's own words instead.
        asked = exchanges[-1].words if exchanges else ""
        scene = await self.write_next(draft, request.detail, worldsmith)
        return Written(tuple(self.install(draft, scene)), CROSSING.format(left=left, asked=asked))

    async def complicate(
        self, draft: Game[W], request: Generation, worldsmith: WorldsmithAnswer
    ) -> Written:
        scene = await self.write_next(draft, COMPLICATING.format(brief=request.detail), worldsmith)
        return Written(tuple(self.install(draft, scene)), TURNING)

    def panels(self, _state: Game[W]) -> tuple[Panel, ...]:
        return ()
