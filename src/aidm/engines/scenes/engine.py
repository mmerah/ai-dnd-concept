from collections.abc import Callable, Sequence
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
    PackSelection,
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
from aidm.engines.packs import SRD_PACK, Pack
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
from aidm.engines.scenes.worldsmith import COMPLICATING, CROSSING, TURNING, check_scene
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
MEANWHILE_NUDGE = (
    "Time has passed since the player last saw the people they are not with. Let one of "
    "them have moved on without the player, if the scene has room for it."
)


class SceneEngine[C: Person, G: Game[Any], K: Pack](Engine[C, C, G, K]):
    world: type[SceneWorld[C]]
    family_dir = Path(__file__).parent
    opening_sections = (
        ("SCENES SO FAR", "(no scenes yet — write the opening)"),
        ("THE WHOLE CAST", "(no cast yet — write the people and things this scene needs)"),
        ("THE SCENE NOW", "(none yet)"),
    )

    def __init__(self, written: Path) -> None:
        super().__init__(written)
        self.packs.srd()  # an engine that ships no srd pack is a bug, not a refusal

    def world_of(self, state: G) -> SceneWorld[C]:
        return state.payload

    def pack_ids(self, supplements: Sequence[Slug]) -> tuple[Slug, ...]:
        return (SRD_PACK, *supplements)

    def validate(self, state: G) -> None:
        super().validate(state)
        if SRD_PACK not in self.packs.require(state.packs).ids:
            raise Refusal(f"a {self.id!r} game plays the {SRD_PACK!r} tables")

    def guidance(self, selection: PackSelection | None, /, *, opening: bool) -> str:
        return super().guidance(self.packs.require(selection), opening=opening)

    def admit(self, packs: PackSelection | None, character: AnyCharacter) -> None:
        selection = self.packs.require(packs)
        if character.packs is None:
            raise Refusal(f"{character.id!r} was made with no table set")
        super().admit(selection, character)

    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> SceneWorld[C]:
        # Copied: a restart reopens the same scenario file.
        draft: SceneDraft[C] = scenario.payload.model_copy(deep=True)
        check_scene(draft)
        return self.world.opening(draft, self.player_of(character), scenario.source)

    def master_sections(self, state: G) -> Sections:
        world = self.world_of(state)
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
            *self.packs.rules_sections(state.packs),
        )

    def sheet_sections(self, _state: G) -> Sections:
        return ()

    def family_sections(self, draft: G) -> Sections:
        world = self.world_of(draft)
        return (
            ("SCENES SO FAR", render_history(draft.log)),
            ("THE WHOLE CAST", world.cast_lines()),
            ("THE SCENE NOW", world.scene_lines()),
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
        world_of = self.world_of
        return (
            *super().master_tools(),
            master_tool("enter", ENTER, Enter, lambda d, a, _: world_of(d).enter(a.entity_id)),
            master_tool("leave", LEAVE, Leave, lambda d, a, _: world_of(d).leave(a.entity_id)),
            master_tool("next_scene", NEXT_SCENE, NextScene, self.next_scene),
        )

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

    def render_next(self, draft: G, intent: str) -> str:
        world = self.world_of(draft)
        if world.arc:
            intent += (
                f"\n\nThe arc as last written:\n{world.arc}\n"
                "Revise `arc` only where what happened warrants it. Leave it empty to keep it."
            )
        if world.meanwhile_due:
            intent += f"\n\n{MEANWHILE_NUDGE}"
        return self.render_request(
            draft,
            guidance=self.guidance(draft.packs, opening=False),
            intent=intent,
            answer=NextDraft[self.member],
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
        packs: PackSelection | None,
        worldsmith: WorldsmithAnswer,
        check: Callable[[AnyScenario], None],
    ) -> AnyScenario:
        selection = self.packs.select(self.packs.require(packs))

        def built(draft: SceneDraft[C]) -> AnyScenario:
            return self.build_scenario(meta, selection, draft, source, draft.situation)

        guidance = self.guidance(selection, opening=True)
        model = SceneDraft[self.member]
        prompt = self.render_worldsmith(
            source, meta.scope, self.opening_sections, OPENING, guidance, model
        )
        return built(await worldsmith(prompt, model, lambda answer: check(built(answer))))

    def worldsmith_requests(self) -> dict[Slug, Request[G]]:
        return {
            **super().worldsmith_requests(),
            DEPARTURE: Request(WAY_UNWRITTEN, self.depart),
            COMPLICATION: Request(COMPLICATION_UNWRITTEN, self.complicate),
        }

    async def depart(self, draft: G, request: Generation, worldsmith: WorldsmithAnswer) -> Written:
        left = self.world_of(draft).run.title
        exchanges = draft.exchanges()
        # The master's `pursuit` is free text; the narrator reads the player's own words instead.
        asked = exchanges[-1].words if exchanges else ""
        scene = await self.write_next(draft, request.detail, worldsmith)
        return Written(tuple(self.install(draft, scene)), CROSSING.format(left=left, asked=asked))

    async def complicate(
        self, draft: G, request: Generation, worldsmith: WorldsmithAnswer
    ) -> Written:
        scene = await self.write_next(draft, COMPLICATING.format(brief=request.detail), worldsmith)
        return Written(tuple(self.install(draft, scene)), TURNING)

    def panels(self, _state: G) -> tuple[Panel, ...]:
        return ()
