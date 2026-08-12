"""Live-model eval harness. Never run from pytest: it needs the network.

    uv run python scripts/evals/run.py [--only <engine|role|tag|id>] [--runs N] [--concurrency N]

Each scenario builds a real game from shipped content, applies its setup, runs one role against it,
then checks the committed state and the recorded facts. Rates land in `results/`.
"""

import asyncio
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from hashlib import sha1
from pathlib import Path
from random import Random
from typing import Literal, Self

from probes import CheckStep, Outcome, Setup, SetupStep, apply_setup, check
from pydantic import Field, JsonValue, model_validator
from pydantic_ai.messages import ModelMessage, ModelRequest, RetryPromptPart

from aidm.app.session import begin_game, build_engine
from aidm.config import Settings, load_settings
from aidm.content.store import load_character, load_scenario
from aidm.engines.loader import Engine
from aidm.state.base import EngineId, Frozen, Slug
from aidm.state.turn import SceneDirective
from aidm.state.world import GameState
from aidm.turn.pipeline import apply_hooks, apply_report, resolve_plan
from aidm.turn.prompts import SceneSnapshot, render_director, render_proposal, render_worldkeeper
from aidm.turn.roles import (
    AdvisorContext,
    PlanContext,
    advisor,
    director_stage,
    scene_stage,
    worldkeeper_stage,
)

EVALS = Path(__file__).parent
SCENARIOS = EVALS / "scenarios"
RESULTS = EVALS / "results"
SEED = 1000
FLAGS = ("--only", "--runs", "--concurrency")
USAGE = "usage: run.py [--only <engine|role|tag|id>] [--runs N] [--concurrency N]"

_ENGINES: dict[EngineId, Engine] = {}


class Options(Frozen):
    only: str | None = None
    runs: int | None = Field(default=None, ge=1)
    concurrency: int = Field(default=4, ge=1)


@dataclass(frozen=True, slots=True)
class Attempt:
    outcome: Outcome
    plan: JsonValue
    retries: tuple[str, ...]
    tokens: int
    directive: JsonValue = None


type Role = Literal["director", "advisor", "worldkeeper"]


class EvalCase(Frozen):
    id: Slug
    engine: EngineId
    role: Role = "director"
    tags: tuple[str, ...] = ()
    scenario: Slug
    character: Slug
    setup: tuple[SetupStep, ...] = ()
    prompt: str
    narration: str = ""
    checks: tuple[CheckStep, ...] = Field(min_length=1)
    runs: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def _narration_belongs_to_the_worldkeeper(self) -> Self:
        if bool(self.narration) != (self.role == "worldkeeper"):
            raise ValueError(f"{self.id}: only a worldkeeper case carries a narration")
        return self


class RunRecord(Frozen):
    """A turn that never finished is a different fault from one whose checks disagreed."""

    run: int
    passed: bool
    duration_s: float = Field(default=0.0, ge=0.0)
    error: str | None = None
    failures: tuple[str, ...] = ()
    # Diagnosis: the plan the Director settled on, the validator refusals it burned on the way,
    # and each recorded fact's trace line.
    plan: JsonValue = None
    directive: JsonValue = None
    retries: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()
    tokens: int = Field(default=0, ge=0)

    @property
    def completed(self) -> bool:
        return self.error is None


class CaseRecord(Frozen):
    id: Slug
    tags: tuple[str, ...]
    rate: float
    completion: float
    mean_duration_s: float
    mean_tokens: float
    runs: tuple[RunRecord, ...] = Field(min_length=1)


class SuiteRecord(Frozen):
    date: str
    commit: str
    model: str
    retries: int
    overall: float
    # Turns that reached a legal plan at all; the rest died on plan-validation retries.
    completion: float
    # Pass rate among completed turns: the rules-interpretation signal, with crashes taken out.
    interpretation: float
    mean_duration_s: float
    mean_tokens: float
    by_tag: dict[str, float]
    cases: tuple[CaseRecord, ...]


def load_cases(directory: Path = SCENARIOS) -> tuple[EvalCase, ...]:
    cases = tuple(
        EvalCase.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    )
    if not cases:
        raise ValueError(f"no eval scenarios under {directory}")
    ids = [case.id for case in cases]
    repeated = sorted({name for name in ids if ids.count(name) > 1})
    if repeated:
        raise ValueError(f"eval scenario ids collide: {repeated}")
    return cases


def initial_state(case: EvalCase, engine: Engine, config: Settings) -> GameState:
    scenario = load_scenario(config.scenarios_dir, case.scenario, case.engine)
    character = load_character(config.characters_dir, case.character, case.engine)
    return begin_game(engine, scenario, character)


async def run_case(case: EvalCase, run: int, config: Settings) -> RunRecord:
    """A failed turn is this run's failure: a live model must never abort the suite."""
    started = time.perf_counter()
    try:
        attempt = await _turn(case, run, config)
    except Exception as error:
        elapsed = time.perf_counter() - started
        return RunRecord(
            run=run, passed=False, duration_s=elapsed, error=f"{type(error).__name__}: {error}"
        )
    elapsed = time.perf_counter() - started
    outcome = attempt.outcome
    failures = tuple(reason for step in case.checks if (reason := check(outcome, step)) is not None)
    return RunRecord(
        run=run,
        passed=not failures,
        duration_s=elapsed,
        failures=failures,
        plan=attempt.plan,
        directive=attempt.directive,
        retries=attempt.retries,
        facts=tuple(fact.trace for fact in outcome.facts),
        tokens=attempt.tokens,
    )


async def run_suite(cases: Sequence[EvalCase], config: Settings, concurrency: int) -> SuiteRecord:
    limit = asyncio.Semaphore(concurrency)

    async def one(case: EvalCase, run: int) -> RunRecord:
        async with limit:
            record = await run_case(case, run, config)
        print(_line(case, record), flush=True)
        return record

    ordered = [(case, run) for case in cases for run in range(case.runs)]
    records = await asyncio.gather(*(one(case, run) for case, run in ordered))
    by_case: dict[Slug, list[RunRecord]] = {case.id: [] for case in cases}
    for (case, _), record in zip(ordered, records, strict=True):
        by_case[case.id].append(record)
    results = tuple(
        CaseRecord(
            id=case.id,
            tags=case.tags,
            rate=_rate(by_case[case.id]),
            completion=_completion(by_case[case.id]),
            mean_duration_s=_mean_duration(by_case[case.id]),
            mean_tokens=_mean_tokens(by_case[case.id]),
            runs=tuple(by_case[case.id]),
        )
        for case in cases
    )
    every = [record for case in results for record in case.runs]
    finished = [record for record in every if record.completed]
    roles = [config.role(name) for name in sorted({case.role for case in cases})]
    return SuiteRecord(
        date=date.today().isoformat(),
        commit=_commit(),
        model=", ".join(sorted({role.model for role in roles})),
        retries=max(role.retries for role in roles),
        overall=_rate(every),
        completion=_completion(every),
        interpretation=_rate(finished),
        mean_duration_s=_mean_duration(every),
        mean_tokens=_mean_tokens(every),
        by_tag={tag: _tag_rate(results, tag) for tag in sorted(_tags(results))},
        cases=results,
    )


def write_results(suite: SuiteRecord, directory: Path = RESULTS) -> Path:
    """Repeat runs on one commit are how variance gets measured, so they never overwrite."""
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{suite.date}-{suite.commit}"
    path = directory / f"{stem}.json"
    attempt = 2
    while path.exists():
        path = directory / f"{stem}-{attempt}.json"
        attempt += 1
    path.write_text(suite.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def summarise(suite: SuiteRecord) -> str:
    lines = [
        f"overall {_percent(suite.overall)} — {suite.model} @ {suite.commit}",
        f"  turns completed: {_percent(suite.completion)}"
        f" (retries {suite.retries}; the rest died on plan-validation retries)",
        f"  checks passed when completed: {_percent(suite.interpretation)}",
        f"  mean duration/turn: {suite.mean_duration_s:.1f}s",
        f"  mean tokens/turn: {suite.mean_tokens:.0f}",
        "",
    ]
    lines.extend(f"  {tag}: {_percent(rate)}" for tag, rate in sorted(suite.by_tag.items()))
    lines.append("")
    lines.extend(
        f"  {_percent(case.rate):>4} pass  {_percent(case.completion):>4} ran  {case.id}"
        for case in sorted(suite.cases, key=lambda case: (case.rate, case.id))
    )
    return "\n".join(lines)


def parse_options(argv: Sequence[str]) -> Options:
    if len(argv) % 2:
        raise SystemExit(USAGE)
    given = dict(zip(argv[::2], argv[1::2], strict=True))
    unknown = sorted(set(given) - set(FLAGS))
    if unknown:
        raise SystemExit(f"unknown option {unknown}\n{USAGE}")
    return Options.model_validate({name.removeprefix("--"): value for name, value in given.items()})


def selected(cases: Sequence[EvalCase], options: Options) -> tuple[EvalCase, ...]:
    only = options.only
    chosen = [case for case in cases if only is None or only in _names(case)]
    if not chosen:
        raise SystemExit(f"no eval scenario matches {only!r}")
    runs = options.runs
    return tuple(
        case if runs is None else case.model_copy(update={"runs": runs}) for case in chosen
    )


async def _turn(case: EvalCase, run: int, config: Settings) -> Attempt:
    engine = _engine(case.engine, config)
    rng = Random(SEED + run)
    before = apply_setup(
        Setup(engine=engine, state=initial_state(case, engine, config), rng=rng), case.setup
    )
    match case.role:
        case "director":
            return await _director_turn(case, config, engine, before, rng)
        case "advisor":
            return await _advisor_turn(case, config, engine, before)
        case "worldkeeper":
            return await _worldkeeper_turn(case, config, engine, before)


async def _directive(
    case: EvalCase, config: Settings, engine: Engine, before: GameState
) -> tuple[SceneDirective, tuple[str, ...], int]:
    scene = scene_stage(config)
    rendered = render_director(
        SceneSnapshot.of(before), engine.renderer(before), before.scenario, case.prompt
    )
    result = await scene.agent.run(rendered, deps=before)
    return result.output, _retry_reasons(result.all_messages()), result.usage.total_tokens


async def _director_turn(
    case: EvalCase, config: Settings, engine: Engine, before: GameState, rng: Random
) -> Attempt:
    directive, scene_retries, scene_tokens = await _directive(case, config, engine, before)
    director = director_stage(engine, config)
    # The agent is run directly rather than through `Stage.run`: only the run result carries
    # the retry exchanges a diagnosis needs.
    rendered = render_director(
        SceneSnapshot.of(before), engine.renderer(before), before.scenario, case.prompt, directive
    )
    result = await director.agent.run(rendered, deps=PlanContext(engine=engine, state=before))
    draft, facts = resolve_plan(engine, before.draft(), result.output, rng)
    draft, fired = apply_hooks(draft, facts)
    facts.extend(fired)
    engine.commit(draft)
    after = draft.committed()
    outcome = Outcome(
        before=before,
        after=after,
        facts=tuple(facts),
        plan=result.output.model_dump(mode="json"),
    )
    retries = scene_retries + _retry_reasons(result.all_messages())
    tokens = scene_tokens + result.usage.total_tokens
    return Attempt(
        outcome=outcome,
        plan=outcome.plan,
        retries=retries,
        tokens=tokens,
        directive=directive.model_dump(mode="json"),
    )


async def _advisor_turn(
    case: EvalCase, config: Settings, engine: Engine, before: GameState
) -> Attempt:
    """The stage's own output validator is `Advancement.violation`, so a proposal that reaches
    here is already legal; the checks measure whether it is the right legal proposal."""
    growth = engine.advancement
    if growth is None:
        raise ValueError(f"{case.id}: the {engine.id} engine has no advancement")
    offer = growth.offered(before)
    if offer is None:
        raise ValueError(f"{case.id}: the setup leaves no advancement on offer")
    deps = AdvisorContext(advancement=growth, state=before, offer=offer)
    rendered = render_proposal(engine, before, offer, case.prompt)
    result = await advisor(growth, config).agent.run(rendered, deps=deps)
    draft = before.draft()
    facts = growth.advance(draft, result.output)
    engine.commit(draft)
    after = draft.committed()
    outcome = Outcome(
        before=before, after=after, facts=facts, plan=result.output.model_dump(mode="json")
    )
    return Attempt(
        outcome=outcome,
        plan=outcome.plan,
        retries=_retry_reasons(result.all_messages()),
        tokens=result.usage.total_tokens,
    )


async def _worldkeeper_turn(
    case: EvalCase, config: Settings, engine: Engine, before: GameState
) -> Attempt:
    """Applies creations through `apply_creations`, so the admission code the turn uses is what
    is measured. The narration is authored by the case, so no earlier phase runs."""
    draft = before.draft()
    keeper = worldkeeper_stage(config)
    rendered = render_worldkeeper(
        SceneSnapshot.of(draft),
        engine.renderer(draft),
        draft.scenario,
        prompt=case.prompt,
        evidence="",
        narration=case.narration,
    )
    result = await keeper.agent.run(rendered, deps=draft)
    facts = apply_report(
        draft, result.output, max_growth=config.max_growth, max_memories=config.max_memories
    )
    engine.commit(draft)
    after = draft.committed()
    report = result.output.model_dump(mode="json")
    outcome = Outcome(before=before, after=after, facts=tuple(facts), plan=report)
    return Attempt(
        outcome=outcome,
        plan=report,
        retries=_retry_reasons(result.all_messages()),
        tokens=result.usage.total_tokens,
    )


def _retry_reasons(messages: Sequence[ModelMessage]) -> tuple[str, ...]:
    return tuple(
        part.model_response()
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, RetryPromptPart)
    )


def _engine(engine_id: EngineId, config: Settings) -> Engine:
    """Memoised: every case under one engine shares the one built instance."""
    held = _ENGINES.get(engine_id)
    if held is None:
        held = build_engine(engine_id)
        _ENGINES[engine_id] = held
    return held


def _line(case: EvalCase, record: RunRecord) -> str:
    if record.error is not None:
        return f"DIED {case.id} run {record.run} — {record.error}"
    mark = "PASS" if record.passed else "FAIL"
    detail = "" if record.passed else f" — {'; '.join(record.failures)}"
    return f"{mark} {case.id} run {record.run}{detail}"


def _rate(runs: Sequence[RunRecord]) -> float:
    return sum(record.passed for record in runs) / len(runs) if runs else 0.0


def _completion(runs: Sequence[RunRecord]) -> float:
    return sum(record.completed for record in runs) / len(runs) if runs else 0.0


def _mean_duration(runs: Sequence[RunRecord]) -> float:
    return sum(record.duration_s for record in runs) / len(runs) if runs else 0.0


def _mean_tokens(runs: Sequence[RunRecord]) -> float:
    return sum(record.tokens for record in runs) / len(runs) if runs else 0.0


def _tag_rate(cases: Sequence[CaseRecord], tag: str) -> float:
    return _rate([record for case in cases if tag in case.tags for record in case.runs])


def _tags(cases: Sequence[CaseRecord]) -> set[str]:
    return {tag for case in cases for tag in case.tags}


def _percent(rate: float) -> str:
    return f"{rate * 100:.0f}%"


def _commit() -> str:
    """Names the tree, not just HEAD: three runs of this suite were stamped with one sha while the
    pack under them changed twice, which made two of the records uncomparable after the fact."""
    head = _git("rev-parse", "--short", "HEAD")
    changes = _git("diff", "HEAD")
    return head if not changes else f"{head}+{sha1(changes.encode()).hexdigest()[:7]}"


def _git(*arguments: str) -> str:
    done = subprocess.run(("git", *arguments), capture_output=True, check=True, text=True)
    return done.stdout.strip()


def _names(case: EvalCase) -> frozenset[str]:
    """An engine id or a role selects a whole suite, which is what a gate comparison needs."""
    return frozenset({case.id, case.engine, case.role, *case.tags})


def main(argv: Sequence[str]) -> None:
    config = load_settings()
    options = parse_options(argv)
    cases = selected(load_cases(), options)
    suite = asyncio.run(run_suite(cases, config, options.concurrency))
    print(f"\n{summarise(suite)}")
    print(f"\nwrote {write_results(suite)}")


if __name__ == "__main__":
    main(sys.argv[1:])
