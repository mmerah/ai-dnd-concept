from collections.abc import Callable
from pathlib import Path
from random import Random
from typing import Any, ClassVar

from aidm.core.entities import Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    Commission,
    Game,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import DecisionOption
from aidm.core.prompt import Sections, render_history, section_if
from aidm.core.tools import tool
from aidm.core.views import NarratorView, PlayerView
from aidm.engines.base import (
    Person,
    character_panel,
    here_panel,
    party_panel,
    party_section,
    trail_panel,
)
from aidm.engines.engine import WRITES_NO, Engine, Written
from aidm.engines.packs import Pack, render_worldsmith
from aidm.engines.scenes.tools import MOVING_ON, SCENE_LEFT, Enter, Leave, NextScene
from aidm.engines.scenes.world import NextProposal, SceneProposal, SceneWorld
from aidm.engines.scenes.worldsmith import (
    COMPLICATING,
    CROSSING,
    MEANWHILE_NUDGE,
    OPENING,
    OPENING_SECTIONS,
    TURNING,
    check_scene,
)

DEPARTURE: Slug = "departure"
COMPLICATION: Slug = "complication"
MOVE_ON = DecisionOption(
    id="move-on", name="Move on", brief="Keep playing, or say where you go and move on."
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


class SceneEngine[C: Person, W: SceneWorld[Any], K: Pack](Engine[W, K]):
    family_dir = Path(__file__).parent
    member: type[C]
    unwritten: ClassVar[dict[Slug, Fact]] = {
        DEPARTURE: WAY_UNWRITTEN,
        COMPLICATION: COMPLICATION_UNWRITTEN,
    }

    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> W:
        # Copied: a restart reopens the same scenario file.
        draft: SceneProposal[C] = scenario.opening.model_copy(deep=True)
        check_scene(draft)
        return self.world.opening(draft, self.player_of(character))

    def master_sections(self, state: Game[W]) -> Sections:
        world = state.world
        scene = world.scene
        return (
            ("SCENE", f"{scene.title}\n{scene.situation}"),
            *section_if("WHAT THIS SCENE IS ABOUT", scene.focus),
            ("YOU PLAY FOR", world.player.line()),
            ("HERE WITH THE PLAYER", world.here_lines()),
            *party_section(world.members()),
            ("HIDDEN HERE (the player has not found these)", world.hidden_lines()),
            *section_if("THE ARC (the player has not found this)", world.arc),
            *self.packs.rules_section(state.pack_id),
        )

    def worldsmith_sections(self, draft: Game[W]) -> Sections:
        world = draft.world
        return (
            ("SCENES SO FAR", render_history(draft.log)),
            ("THE WHOLE CAST", world.cast_lines()),
            ("THE SCENE NOW", world.scene_lines()),
        )

    def narrator_view(self, state: Game[W]) -> NarratorView:
        world = state.world
        scene = world.scene
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
        return PlayerView(
            player=player.subject(),
            scene_title=world.scene.title,
            situation=world.scene.situation,
            panels=(
                character_panel(world.sheet_rows()),
                *world.scene_panel(),
                *party_panel(world.members()),
                here_panel(other.subject() for other in world.others()),
                trail_panel(scene.title for scene in world.scenes),
            ),
            decision=state.pending,
            action=MOVE_ON if world.scene.way_offered else None,
            ending=self.ending(state),
        )

    @tool
    def enter(self, draft: Game[W], args: Enter, _rng: Random) -> list[Fact]:
        """A cast member comes into the scene."""
        return draft.world.enter(args.target_id)

    @tool
    def leave(self, draft: Game[W], args: Leave, _rng: Random) -> list[Fact]:
        """A cast member goes out of the scene."""
        return draft.world.leave(args.target_id)

    @tool
    def next_scene(self, draft: Game[W], args: NextScene, _rng: Random) -> list[Fact]:
        """Call this with nothing set when the scene reaches a stopping point. Set `pursuit` instead
        once the player has left this place. Set `complication` instead to bring a new situation
        down on this place."""
        if args.pursuit:
            draft.commission = Commission(operation=DEPARTURE, detail=args.pursuit)
            return [SCENE_LEFT]
        if not args.complication:
            return draft.world.offer_way_on()
        draft.commission = Commission(operation=COMPLICATION, detail=args.complication)
        return [
            Fact(
                trace=f"the worldsmith writes the complication once this turn ends: "
                f"{args.complication}. Nothing more lands this turn; stop and exit",
            )
        ]

    def act(self, draft: Game[W], action_id: Slug, _words: str) -> None:
        if action_id != MOVE_ON.id or not draft.world.scene.way_offered:
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
        return self.render_commission(
            draft,
            guidance=self.guidance(draft.pack_id, opening=False),
            intent=intent,
            answer_model=NextProposal[self.member],
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
        prompt = render_worldsmith(
            self.worldsmith_role,
            source=source,
            scope=meta.scope,
            world_sections=OPENING_SECTIONS,
            intent=OPENING,
            guidance=guidance,
            answer_model=model,
        )
        return built(await worldsmith(prompt, model, lambda answer: check(built(answer))))

    async def advance(
        self, draft: Game[W], commission: Commission, worldsmith: WorldsmithAnswer
    ) -> Written:
        if commission.operation == DEPARTURE:
            return await self.depart(draft, commission, worldsmith)
        if commission.operation == COMPLICATION:
            return await self.complicate(draft, commission, worldsmith)
        raise ValueError(WRITES_NO.format(engine=self.id, operation=commission.operation))

    async def depart(
        self, draft: Game[W], commission: Commission, worldsmith: WorldsmithAnswer
    ) -> Written:
        left = draft.world.scene.title
        exchanges = draft.exchanges()
        # The master's `pursuit` is free text; the narrator reads the player's own words instead.
        asked = exchanges[-1].words if exchanges else ""
        scene = await self.write_next(draft, commission.detail, worldsmith)
        return Written(tuple(self.install(draft, scene)), CROSSING.format(left=left, asked=asked))

    async def complicate(
        self, draft: Game[W], commission: Commission, worldsmith: WorldsmithAnswer
    ) -> Written:
        scene = await self.write_next(
            draft, COMPLICATING.format(brief=commission.detail), worldsmith
        )
        return Written(tuple(self.install(draft, scene)), TURNING)
