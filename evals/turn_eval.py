import argparse
import asyncio
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from importlib import import_module
from pathlib import Path
from random import Random
from statistics import mean
from time import perf_counter
from types import ModuleType

from pydantic import JsonValue
from pydantic_ai import capture_run_messages
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from aidm.config import Settings, load_settings
from aidm.content.io import load_character, load_scenario
from aidm.engines.core import Engine
from aidm.engines.registry import begin_game, build_engines
from aidm.state.entities import EngineId, Frozen, Slug
from aidm.state.facts import Fact
from aidm.state.model import Game
from aidm.state.play import Answer, PendingDecision
from aidm.turn.run import TurnStep, build_turn_agents, run_segment

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"
# Started as a script, `sys.path` holds `evals/` alone, and the case modules import this one.
sys.path.append(str(ROOT))

# The longest valid chain is stake -> proceed -> defence.
SEGMENT_CAP = 4


@cache
def built() -> dict[EngineId, Engine]:
    return build_engines(ROOT / load_settings().packs_dir)


def cases_module(engine_id: EngineId) -> ModuleType:
    """An engine's canon and cases live in its own module, so the runner names no engine."""
    return import_module(f"evals.cases.{engine_id}")


def begin(engine_id: EngineId, settings: Settings) -> tuple[Engine, Game]:
    engine = built()[engine_id]
    scenario_id: Slug = cases_module(engine_id).CANON.scenario_id
    scenario = load_scenario(ROOT / settings.scenarios_dir, scenario_id)
    character = load_character(
        ROOT / settings.characters_dir, settings.authoring.starter_character, engine.id
    )
    return engine, begin_game(engine, scenario_id, scenario, character)


class Played(Frozen):
    """The whole interaction as one record: what the deleted turn trace used to carry."""

    state: Game
    facts: tuple[Fact, ...] = ()
    director_calls: int = 0
    retry_prompts: tuple[str, ...] = ()
    prompts: tuple[str, ...] = ()
    calls: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Expectation:
    name: str
    holds: Callable[[Played], bool]


def _last_option(pending: PendingDecision) -> Slug:
    return pending.options[-1].id


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    engine_id: EngineId
    prompt: str
    expectations: tuple[Expectation, ...]
    setup: Callable[[Game], Game] = lambda state: state
    # True sends the prompt as a written Answer: how the app delivers text over a staged decision.
    answers_decision: bool = False
    # Which option answers a mid-run hand-back; stake offers proceed, defence ends on take-it.
    choose: Callable[[PendingDecision], Slug] = _last_option


class Run(Frozen):
    error: str | None = None
    passed: dict[str, bool] = {}
    facts: list[str] = []
    # The Director's prompts, kept only for a run that failed: the debugging record.
    prompts: list[str] = []
    director_calls: int = 0
    refusals: list[str] = []
    calls: list[str] = []
    seconds: float = 0.0

    @property
    def scored(self) -> bool:
        return self.error is None and all(self.passed.values())


class CaseResult(Frozen):
    id: str
    engine: str
    prompt: str
    expectations: list[str]
    runs: list[Run]

    def rate(self, name: str) -> float:
        return mean([float(run.passed.get(name, False)) for run in self.runs])


class Report(Frozen):
    label: str
    repeats: int
    seed: int
    cases: list[CaseResult]


def _asked(messages: Sequence[ModelMessage]) -> str:
    """What the Director was shown: the last user part, after the replayed exchange history."""
    return next(
        str(part.content)
        for message in reversed(messages)
        for part in message.parts
        if isinstance(part, UserPromptPart)
    )


def _called(messages: Sequence[ModelMessage]) -> tuple[str, ...]:
    """Tool calls that got a plain return back, each with the union arm its args selected."""
    landed = {
        part.tool_call_id
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    }
    calls: list[str] = []
    for message in messages:
        if not isinstance(message, ModelResponse):
            continue
        for part in message.parts:
            if not isinstance(part, ToolCallPart) or part.tool_call_id not in landed:
                continue
            raw: dict[str, JsonValue] = part.args_as_dict()
            change = raw.get("change")
            arm = change.get("verb") if isinstance(change, dict) else None
            calls.append(f"{part.tool_name}:{arm}" if isinstance(arm, str) else part.tool_name)
    return tuple(calls)


def _refused(messages: Sequence[ModelMessage]) -> tuple[str, ...]:
    return tuple(
        part.model_response()
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, RetryPromptPart)
    )


async def play(case: Case, settings: Settings, seed: int) -> Run:
    engine, state = begin(case.engine_id, settings)
    stages = build_turn_agents(engine, settings)
    rng = Random(seed)
    started = perf_counter()
    played = Played(state=state)
    try:
        played = Played(state=case.setup(state))
        player_input: str | Answer = (
            Answer(text=case.prompt) if case.answers_decision else case.prompt
        )
        answered: set[Slug] = set()
        for _ in range(SEGMENT_CAP):
            facts: list[Fact] = []
            steps: list[TurnStep] = []
            # The Director runs first, so its messages are the ones this context keeps.
            with capture_run_messages() as messages:
                committed = await run_segment(
                    played.state,
                    player_input,
                    engine=engine,
                    stages=stages,
                    settings=settings,
                    rng=rng,
                    on_step=steps.append,
                    on_fact=facts.append,
                )
            # Only a committed segment's facts join the record: a failed narrator rolled its back.
            played = Played(
                state=committed,
                facts=(*played.facts, *facts),
                director_calls=played.director_calls + steps.count("director"),
                retry_prompts=(*played.retry_prompts, *_refused(messages)),
                prompts=(*played.prompts, _asked(messages)),
                calls=(*played.calls, *_called(messages)),
            )
            pending = committed.pending
            if pending is None:
                break
            # A case scripts one answer per decision kind: an unscripted hand-back, or a kind
            # already answered (a fight's next exchange), is a choice no case scripts.
            if not pending.options or pending.kind in answered:
                break
            answered.add(pending.kind)
            player_input = Answer(option_id=case.choose(pending))
        else:
            raise ValueError(f"the interaction was still going after {SEGMENT_CAP} segments")
        passed = {check.name: check.holds(played) for check in case.expectations}
        return Run(
            passed=passed,
            facts=[f"{fact.kind}: {fact.trace}" for fact in played.facts],
            prompts=[] if all(passed.values()) else list(played.prompts),
            director_calls=played.director_calls,
            refusals=list(played.retry_prompts),
            calls=list(played.calls),
            seconds=perf_counter() - started,
        )
    except Exception as error:
        return Run(
            error=f"{type(error).__name__}: {error}",
            passed={check.name: False for check in case.expectations},
            facts=[f"{fact.kind}: {fact.trace}" for fact in played.facts],
            prompts=list(played.prompts),
            calls=list(played.calls),
            seconds=perf_counter() - started,
        )


async def play_all(
    cases: Sequence[Case], settings: Settings, repeats: int, seed: int, concurrency: int
) -> list[CaseResult]:
    limit = asyncio.Semaphore(concurrency)

    async def one(case: Case, repeat: int) -> Run:
        async with limit:
            return await play(case, settings, seed + repeat)

    async with asyncio.TaskGroup() as group:
        tasks = [[group.create_task(one(case, n)) for n in range(repeats)] for case in cases]
    return [
        CaseResult(
            id=case.id,
            engine=case.engine_id,
            prompt=case.prompt,
            expectations=[check.name for check in case.expectations],
            runs=[task.result() for task in row],
        )
        for case, row in zip(cases, tasks, strict=True)
    ]


def print_report(report: Report) -> None:
    for case in report.cases:
        runs, total = case.runs, len(case.runs)
        scored = sum(1 for run in runs if run.scored)
        errors = sum(1 for run in runs if run.error is not None)
        print(
            f"{case.id:<40} score {scored}/{total} ({scored / total:.0%})"
            f"  errors {errors}/{total}"
            f"  director_calls {mean([run.director_calls for run in runs]):.1f}"
            f"  refusals {sum(len(run.refusals) for run in runs)}"
            f"  {mean([run.seconds for run in runs]):.1f}s"
        )
        for refusal in sorted({one for run in runs for one in run.refusals}):
            print(f"    ! refused: {refusal.splitlines()[0][:110]}")
        for name in case.expectations:
            print(f"    {name:<36} {case.rate(name):.0%}")
        for run in runs:
            if run.error is not None:
                print(f"    ! {run.error}")


def select(settings: Settings, ids: Sequence[str], engine: str | None) -> list[Case]:
    engines = tuple(built()) if engine is None else (EngineId(engine),)
    if unknown := [name for name in engines if name not in built()]:
        raise SystemExit(f"unknown engine(s): {unknown}")
    cases: list[Case] = [case for name in engines for case in cases_module(name).CASES(settings)]
    if not ids:
        return cases
    chosen = [case for case in cases if case.id in ids]
    if missing := sorted(set(ids) - {case.id for case in chosen}):
        raise SystemExit(f"unknown case id(s): {missing}. Known: {[c.id for c in cases]}")
    return chosen


def run_command(args: argparse.Namespace) -> None:
    label: str = args.label
    settings = load_settings()
    cases = select(settings, args.case, args.engine)
    started = perf_counter()
    results = asyncio.run(
        play_all(cases, settings, args.repeats, args.seed, args.concurrency),
    )
    report = Report(label=label, repeats=args.repeats, seed=args.seed, cases=results)
    RESULTS.mkdir(parents=True, exist_ok=True)
    written = RESULTS / f"{label}.json"
    _ = written.write_text(report.model_dump_json(indent=2))
    print_report(report)
    print(f"\n{label}: {len(cases)} cases in {perf_counter() - started:.1f}s -> {written}")


def _overall(report: Report) -> tuple[float, float, float, float]:
    runs = [run for case in report.cases for run in case.runs]
    return (
        mean([float(run.scored) for run in runs]),
        mean([float(run.error is not None) for run in runs]),
        mean([run.director_calls for run in runs]),
        mean([run.seconds for run in runs]),
    )


def _delta(before: float, after: float) -> str:
    return f"{before:.0%} -> {after:.0%} ({after - before:+.0%})"


def compare_command(args: argparse.Namespace) -> None:
    baseline = Report.model_validate_json(Path(args.baseline).read_text())
    candidate = Report.model_validate_json(Path(args.candidate).read_text())
    was = {case.id: case for case in baseline.cases}
    for case in candidate.cases:
        old = was.pop(case.id, None)
        if old is None:
            print(f"{case.id:<40} new")
            continue
        scored = mean([float(run.scored) for run in case.runs])
        print(f"{case.id:<40} score {_delta(mean([float(r.scored) for r in old.runs]), scored)}")
        for name in case.expectations:
            seen = f"{case.rate(name):.0%}" if name in old.expectations else "new"
            known_before = f"{old.rate(name):.0%} -> " if name in old.expectations else ""
            print(f"    {name:<36} {known_before}{seen}")
    for case_id in was:
        print(f"{case_id:<40} missing from candidate")
    labels = (baseline.label, candidate.label)
    old_score, old_errors, old_calls, old_seconds = _overall(baseline)
    new_score, new_errors, new_calls, new_seconds = _overall(candidate)
    print(f"\noverall {labels[0]} -> {labels[1]}")
    print(f"  score          {_delta(old_score, new_score)}")
    print(f"  errors         {_delta(old_errors, new_errors)}")
    print(f"  director_calls {old_calls:.2f} -> {new_calls:.2f} ({new_calls - old_calls:+.2f})")
    gap = new_seconds - old_seconds
    print(f"  seconds        {old_seconds:.1f} -> {new_seconds:.1f} ({gap:+.1f})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Turn-quality benchmark (makes real model calls)")
    commands = parser.add_subparsers(dest="command", required=True)

    runner = commands.add_parser("run")
    _ = runner.add_argument("--label", required=True)
    _ = runner.add_argument("--repeats", type=int, default=9)
    _ = runner.add_argument("--concurrency", type=int, default=4)
    _ = runner.add_argument("--seed", type=int, default=1000)
    _ = runner.add_argument("--case", action="append", default=[])
    _ = runner.add_argument("--engine", default=None)
    runner.set_defaults(handler=run_command)

    comparison = commands.add_parser("compare")
    _ = comparison.add_argument("--baseline", required=True)
    _ = comparison.add_argument("--candidate", required=True)
    comparison.set_defaults(handler=compare_command)

    args = parser.parse_args()
    handler: Callable[[argparse.Namespace], None] = args.handler
    handler(args)


if __name__ == "__main__":
    main()
