"""A second engine that shares no concept with the rooms engines: one resource and a stage."""

from collections.abc import Sequence
from pathlib import Path
from random import Random
from typing import Literal

import pytest
from core_test_support import narrated, offline_settings, scripted, text, tool_call
from pydantic import BaseModel, Field
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models.function import FunctionModel

from aidm.app.runtime import GameService, LaunchTarget
from aidm.content.io import FileStore
from aidm.kernel.envelope import CharacterEnvelope, SaveEnvelope
from aidm.kernel.views import (
    ArtSubject,
    CreationPreview,
    DirectorView,
    NarratorView,
    PlayerPrompt,
    PlayerView,
    Views,
    speaker_of,
)
from aidm.state.creation import CreationStep, Picks, check_picks, picked
from aidm.state.entities import EngineId, Frozen, Mutable, slug
from aidm.state.facts import Fact
from aidm.state.model import Character, Game, Scenario, ScenarioMeta
from aidm.state.play import Answer, DecisionOption, PendingDecision, PendingOption
from aidm.state.tools import DirectorTool, director_tool
from aidm.turn.run import build_turn_agents

HOSTILE = EngineId("hostile")
OPERATOR_ID = "operator"
Stage = Literal["listening", "burning", "waiting"]


class SignalState(Mutable):
    """The whole played state: how much signal is left, what the rules last did, and who plays."""

    level: int = Field(ge=0)
    stage: Stage
    callsign: str


class SignalScenario(Frozen):
    opening_level: int = Field(ge=1)


class SignalCharacter(Frozen):
    callsign: str


def signal_of(state: Game) -> SignalState:
    payload = state.payload
    if not isinstance(payload, SignalState):
        raise ValueError(f"a {state.engine!r} game holds no signal state")
    return payload


class Burn(Frozen):
    cost: int = Field(ge=1, description="How much signal the transmission burns.")


def _burn(draft: Game, args: Burn, rng: Random) -> Sequence[Fact]:
    del rng
    signal = signal_of(draft)
    if signal.level < args.cost:
        raise ValueError(f"the relay holds {signal.level} signal, so {args.cost} cannot be spent.")
    signal.level -= args.cost
    signal.stage = "burning"
    moved = f"signal {-args.cost:+d} -> {signal.level}"
    return (Fact(kind="signal_burned", trace=moved, told=True, card=moved),)


class Hail(Frozen):
    question: str = Field(description="What the rules put to the player, in one line.")


_CHANNEL = (
    PendingOption(id="boost", label="Boost the carrier", detail="One more signal."),
    PendingOption(id="damp", label="Damp the carrier", detail="One less signal."),
)


def _hail(draft: Game, args: Hail, rng: Random) -> Sequence[Fact]:
    del rng
    signal = signal_of(draft)
    signal.stage = "waiting"
    draft.pending = PendingDecision(
        kind="channel", prompt=args.question, options=_CHANNEL, allows_text=False
    )
    return (Fact(kind="channel_opened", trace=f"the channel is open: {args.question}", told=True),)


class SignalCreation:
    def steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        del picks
        return (CreationStep(id="callsign", prompt="Choose a callsign"),)

    def created(
        self, name: str, brief: str, picks: Picks
    ) -> tuple[CharacterEnvelope, CreationPreview]:
        check_picks(self.steps(picks), picks)
        callsign = picked(picks, "callsign")
        envelope = CharacterEnvelope(
            id=slug(name, ()),
            engine=HOSTILE,
            name=name,
            brief=brief,
            payload={"callsign": callsign},
        )
        return envelope, CreationPreview(rows=(("callsign", callsign),))


class SignalEngine:
    """Implements `aidm.kernel.protocol.Engine` with no entity, location or world behind it."""

    id = HOSTILE
    title = "Signal Lock"
    instructions = "Burn signal to transmit, hail the operator when the rules need their choice."
    state: type[BaseModel] = SignalState
    scenario: type[BaseModel] = SignalScenario
    character: type[BaseModel] = SignalCharacter
    creation = SignalCreation()
    tools: tuple[DirectorTool, ...] = (
        director_tool("burn_signal", "Spend signal to push a transmission through.", Burn, _burn),
        director_tool("hail_operator", "Ask the player how to hold the carrier.", Hail, _hail),
    )

    def new_game(self, scenario: Scenario, character: Character) -> SignalState:
        opening = SignalScenario.model_validate(scenario.payload.model_dump())
        played = SignalCharacter.model_validate(character.payload.model_dump())
        return SignalState(level=opening.opening_level, stage="listening", callsign=played.callsign)

    def restored(self, raw: str) -> Game:
        envelope = SaveEnvelope.model_validate_json(raw)
        if envelope.engine != self.id:
            raise ValueError(f"the save plays {envelope.engine!r}, not {self.id!r}")
        payload = SignalState.model_validate(envelope.payload)
        state = Game.model_validate(envelope.model_dump() | {"payload": payload})
        self.validate(state)
        return state

    def validate(self, state: Game) -> None:
        _ = signal_of(state)

    def views(self, state: Game) -> Views:
        signal = signal_of(state)
        operator = ArtSubject(id=OPERATOR_ID, name=signal.callsign, brief="A relay operator.")
        summary = f"The carrier holds at {signal.level}."
        sections = (("SIGNAL", str(signal.level)), ("STAGE", signal.stage))
        pending = state.pending
        return Views(
            director=DirectorView(sections=sections),
            narrator=NarratorView(
                key=f"{signal.stage}-{signal.level}",
                label="the relay",
                summary=summary,
                sections=sections,
                prompts=(("TONE", "Static and patience."),),
                art_prompt=summary,
                subjects=(),
                speakers=(speaker_of(operator),),
            ),
            player=PlayerView(
                player=operator,
                prompt=None
                if pending is None
                else PlayerPrompt(
                    prompt=pending.prompt,
                    options=tuple(
                        DecisionOption(id=one.id, label=one.label, detail=one.detail)
                        for one in pending.options
                    ),
                    allows_text=pending.allows_text,
                ),
            ),
        )

    def answer(self, draft: Game, chosen: PendingOption, rng: Random) -> tuple[Fact, ...]:
        del rng
        signal = signal_of(draft)
        signal.level = max(0, signal.level + (1 if chosen.id == "boost" else -1))
        signal.stage = "listening"
        moved = f"the carrier is {chosen.label.lower()}: signal -> {signal.level}"
        return (Fact(kind="carrier_held", trace=moved, told=True, card=moved),)

    def over(self, state: Game) -> str | None:
        return "The signal is gone." if signal_of(state).level == 0 else None


ENGINE = SignalEngine()
TARGET = LaunchTarget(slug="hostile", scenario_id="signal-lock", character_id="vesper")


def _session(directory: Path) -> GameService:
    settings = offline_settings()
    return GameService(
        target=TARGET,
        scenario=Scenario(
            meta=ScenarioMeta(title="Signal Lock", premise="A relay answers nobody."),
            engine=HOSTILE,
            packs=("carrier",),
            grows=False,
            payload=SignalScenario(opening_level=3),
        ),
        character=Character(
            id="vesper",
            engine=HOSTILE,
            name="Vesper",
            brief="A relay operator.",
            payload=SignalCharacter(callsign="Vesper"),
        ),
        engine=ENGINE,
        stages=build_turn_agents(ENGINE, settings),
        store=FileStore(directory),
        settings=settings,
        media=None,
        rng=Random(7),
    )


async def _played(game: GameService, player_input: str | Answer, *director: ModelResponse) -> None:
    stages = game.stages
    assert stages is not None
    with (
        stages.director.override(model=FunctionModel(scripted(*director))),
        stages.narrator.override(model=FunctionModel(scripted(narrated("The static thins.")))),
    ):
        await game.submit(player_input)


async def test_a_turn_burns_the_resource_and_lands_in_history(tmp_path: Path) -> None:
    game = _session(tmp_path)

    await _played(game, "I push the transmission.", tool_call("burn_signal", cost=2), text("done"))

    assert signal_of(game.state).level == 1
    exchange = game.state.history[-1]
    assert exchange.speaker.id == OPERATOR_ID
    assert exchange.narration == "The static thins."
    assert FileStore(tmp_path).load("hostile") is not None


async def test_a_prompt_round_trips_from_the_player_view_back_through_answer(
    tmp_path: Path,
) -> None:
    game = _session(tmp_path)

    await _played(
        game, "I hail them.", tool_call("hail_operator", question="Boost or damp?"), text("asked")
    )
    prompt = game.view().player.prompt
    assert prompt is not None
    assert [one.id for one in prompt.options] == ["boost", "damp"]
    assert not prompt.allows_text

    await _played(game, Answer(option_id="boost"), text("held"))

    assert game.state.pending is None
    assert signal_of(game.state).level == 4


def test_a_second_service_over_the_same_store_restores_the_state(tmp_path: Path) -> None:
    game = _session(tmp_path)
    game.commit(game.state)

    assert _session(tmp_path).state == game.state


def test_the_kernel_drove_a_payload_that_holds_no_world(tmp_path: Path) -> None:
    game = _session(tmp_path)

    with pytest.raises(ValueError, match="holds no rooms world"):
        _ = game.state.world
