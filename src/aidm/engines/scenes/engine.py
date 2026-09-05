from abc import abstractmethod
from collections.abc import Callable, Sequence
from pathlib import Path
from random import Random
from typing import Any

from aidm.core.creation import CreationStep
from aidm.core.entities import Refusal, Slug, parse
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, AnyScenario, Game, ScenarioMeta, WorldsmithAnswer
from aidm.core.play import DecisionOption
from aidm.core.views import NarratorView, Panel, PlayerView, Sections, render_history
from aidm.engines.base import (
    SRD_PACK,
    Pack,
    Person,
    character_panel,
    here_panel,
    read_packs,
    trail_panel,
)
from aidm.engines.scenes.drafts import NextDraft, SceneDraft
from aidm.engines.scenes.tools import (
    Enter,
    JoinParty,
    Kill,
    Leave,
    LeaveParty,
    NextScene,
    Reveal,
    SharedChange,
)
from aidm.engines.scenes.world import SceneCanon, SceneWorld, resolve_ids, run_of
from aidm.engines.scenes.worldsmith import (
    COMPLICATION,
    CROSSING,
    TURNING,
    scene_refusal,
    worldsmith_prompt,
)
from aidm.engines.seam import Engine

WORLDSMITH = (Path(__file__).parent / "worldsmith.md").read_text(encoding=ENCODING)
OPENING = (
    "Write the opening scene of this adventure: the one place the player starts in, who is "
    "there, and a `question` that settles in that place. A scene ends when the player leaves "
    "it, so a question about somewhere farther on belongs to a later scene. `cast` is the "
    "adventure's people and things, not the scene's: write who is met here and who the player "
    "will meet farther in, and list under `present` and `hidden` only who is here now. "
    "`hidden` is for something worth finding here; it is not required. The opening also writes "
    "`arc`, the setup beyond this scene for the game master and the worldsmith, never the "
    "player: pressures, motives, secrets, what may come; a few lines, or none."
)


class SceneEngine[C: Person, P: Person, G: Game[Any], K: Pack](Engine[P, G]):
    cast: type[C]
    pack: type[K]
    world_type: type[SceneWorld[C, P]]
    packs: dict[str, K]

    def __init__(self) -> None:
        self.packs = read_packs(self.directory / "packs", self.pack)
        super().__init__()  # last: `master_tools` reads the packs

    def world(self, state: G) -> SceneWorld[C, P]:
        return state.payload

    def crossing(self, state: G, pursuit: str) -> str | None:
        if state.handoff:
            return TURNING
        return CROSSING.format(left=self.world(state).run.title, pursuit=pursuit)

    def page_word(self, state: G, intent: str) -> bool:
        return intent == self.world(state).run.left

    def pack_options(self) -> tuple[DecisionOption, ...]:
        """The create page's table sets, and the first step of every scene engine's creation."""
        return tuple(DecisionOption(id=key, label=pack.name) for key, pack in self.packs.items())

    def validate(self, state: G) -> None:
        if not state.packs:
            raise Refusal(f"a {state.engine!r} game needs at least one table set")
        if missing := sorted(set(state.packs) - set(self.packs)):
            raise Refusal(f"the game names packs not installed: {missing}")

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
            ("THE QUESTION THIS SCENE SETTLES", scene.question),
            ("YOU PLAY FOR", world.player.line()),
            *self.sheet_sections(state),
            ("HERE WITH THE PLAYER", world.here_lines()),
            *world.party_rows(),
            ("HIDDEN HERE (the player has not found these)", world.hidden_lines()),
            *((("THE ARC (the player has not found this)", world.arc),) if world.arc else ()),
            *self.glossary(state),
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
        sheet = world.player.rows()
        if members := world.members():
            sheet = (*sheet, ("Travelling with", ", ".join(member.name for member in members)))
        return NarratorView(
            place=scene.place,
            title=scene.title,
            focus=scene.question,
            situation=scene.situation,
            subjects=tuple(member.subject() for member in here),
            speakers=tuple(member.id for member in here),
            sheet=sheet,
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
                *world.party_panel(),
                here_panel(
                    me, (member.subject() for member in world.here() if member.id != player.id)
                ),
                trail_panel(run.title for run in world.runs),
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
        if args.pursuit and args.complication:
            raise Refusal("a pursuit or a complication, not both")
        if args.complication:
            asked = self.world(draft).complicate(args.complication)
            draft.handoff = args.complication
            return [asked]
        return self.world(draft).settle(args.pursuit)

    def pack_step(self) -> CreationStep:
        return CreationStep(id="pack", prompt="Choose a table set", options=self.pack_options())

    def srd_pack(self) -> K:
        pack = self.packs.get(SRD_PACK)
        if pack is None:
            raise Refusal("the SRD table set is not installed")
        return pack

    def render_next(self, draft: G, intent: str) -> str:
        world = self.world(draft)
        if world.arc:
            intent += (
                f"\n\nThe arc as last written: {world.arc}. Revise `arc` only where what "
                "happened warrants it; leave it empty to keep it."
            )
        return worldsmith_prompt(
            WORLDSMITH,
            source=world.source,
            scope=draft.scenario.scope,
            history=render_history(world.records()),
            cast=world.cast_lines(),
            guidance=self.guidance(draft.packs),
            intent=intent,
            answer=NextDraft[self.cast],
        )

    def render_opening(self, source: str, guidance: str, scope: str) -> str:
        return worldsmith_prompt(
            WORLDSMITH,
            source=source,
            scope=scope,
            history="(no scenes yet — write the opening)",
            cast="(no cast yet — write the people and things this scene needs)",
            guidance=guidance,
            intent=OPENING,
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
            payload=self.opening_canon(draft, source),
        )

    def opening_canon(self, draft: SceneDraft[C], source: str) -> SceneCanon[C]:
        """Parametrized on the engine's cast, so the canon revalidates as its own people."""
        cast = draft.cast
        present = resolve_ids(draft.present, cast, "present")
        hidden = resolve_ids(draft.hidden, cast, "hidden")
        for entity_id in present:
            cast[entity_id].known = True
        return parse(
            SceneCanon[self.cast],
            {
                "cast": cast,
                "opening": run_of(draft, [*present, *hidden]),
                "source": source,
                "arc": draft.arc,
            },
        )

    async def write_next(self, draft: G, intent: str, worldsmith: WorldsmithAnswer) -> NextDraft[C]:
        world = self.world(draft)
        model = NextDraft[self.cast]
        asked = COMPLICATION.format(brief=draft.handoff) if draft.handoff else intent
        prompt = self.render_next(draft, asked)
        return await worldsmith(prompt, model, lambda answer: scene_refusal(answer, world))

    def install(self, draft: G, scene: SceneDraft[C]) -> list[Fact]:
        world = self.world(draft)
        world.apply_scene(scene.model_copy(deep=True))
        moved = "the scene turns to" if draft.handoff else "the story moves to"
        trace = f"{moved} {scene.title}"
        if travelling := [member.name for member in world.members()]:
            trace += f", the player travelling with {', '.join(travelling)}"
        card = f"New scene: {scene.title}\nAt stake: {scene.question}"
        return [Fact(kind="scene_opened", trace=trace, told=True, card=card)]

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

    def ready(self, state: G) -> bool:
        return self.world(state).run.left is not None

    async def advance(
        self, draft: G, intent: str, worldsmith: WorldsmithAnswer
    ) -> tuple[Fact, ...]:
        scene = await self.write_next(draft, intent, worldsmith)
        # The engine's own closing reads the scene being left, so it runs before the install.
        # A complication turns the scene, it does not end it: no closing (Loner refills pools) runs.
        leaving = () if draft.handoff else self.leaving(draft)
        return (*leaving, *self.install(draft, scene))

    def panels(self, state: G) -> tuple[Panel, ...]:
        return ()

    def leaving(self, state: G) -> tuple[Fact, ...]:
        return ()

    @abstractmethod
    def guidance(self, picks: Sequence[Slug]) -> str: ...
