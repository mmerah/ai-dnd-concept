import argparse
import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random
from statistics import mean
from time import perf_counter

from aidm.app.registry import begin_game, build_engine
from aidm.config import Settings, load_settings
from aidm.content.store import load_character, load_scenario
from aidm.engines.engine import Engine
from aidm.engines.sheets import SheetBase
from aidm.state.base import EngineId, EntityId, Frozen
from aidm.state.trace import StepTrace
from aidm.state.world import Game
from aidm.turn.agents import build_turn_agents
from aidm.turn.pipeline import TurnResult, run_turn

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"
SCENARIO_ID = "whispering-vault"
CHARACTER_ID = "kael"
ENGINES = (EngineId("loner3e"), EngineId("twentyfourxx"))
# Both engines' outcomes for an attempt that got what it reached for.
WON = ("yes-and", "yes", "yes-but", "success")


@dataclass(frozen=True, slots=True)
class Expectation:
    name: str
    holds: Callable[[TurnResult], bool]


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    engine_id: EngineId
    prompt: str
    expectations: tuple[Expectation, ...]
    setup: Callable[[Game], Game] = lambda state: state


class Run(Frozen):
    error: str | None = None
    passed: dict[str, bool] = {}
    # The plan beside the facts: a failure says whether a mechanic was never named or never run.
    planned: list[str] = []
    facts: list[str] = []
    director_calls: int = 0
    total_steps: int = 0
    seconds: float = 0.0
    narration_chars: int = 0

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


def begin(engine_id: EngineId, settings: Settings) -> tuple[Engine[SheetBase], Game]:
    engine = build_engine(engine_id)
    binding = engine.binding()
    scenario = load_scenario(ROOT / settings.scenarios_dir, SCENARIO_ID, binding)
    character = load_character(ROOT / settings.characters_dir, CHARACTER_ID, binding)
    return engine, begin_game(engine, scenario, character)


def staged(state: Game, at: str, ways: Sequence[tuple[str, str]]) -> Game:
    draft = state.draft()
    for source, target in ways:
        source_id, target_id = EntityId(source), EntityId(target)
        exit_ = draft.world.require_kind(source_id, "location").exit_to(target_id)
        if exit_ is None:
            raise ValueError(f"no way joins {source!r} and {target!r}")
        # A known way needs both ends known: the world refuses a known exit to an unmet place.
        draft.world.require(source_id).known = True
        draft.world.require(target_id).known = True
        exit_.known = True
        mirror = draft.world.require_kind(target_id, "location").exit_to(source_id)
        if mirror is not None:
            mirror.known = True
    draft.player.parent_id = EntityId(at)
    return draft.committed()


def known(result: TurnResult, entity_id: str) -> bool:
    entity = result.state.world.find(EntityId(entity_id))
    return entity is not None and entity.known


def inside(result: TurnResult, entity_id: str, holder: str) -> bool:
    entity = result.state.world.find(EntityId(entity_id))
    return entity is not None and entity.parent_id == EntityId(holder)


def staged_at(result: TurnResult, thread_id: str, stage: str) -> bool:
    thread = result.state.world.thread(thread_id)
    return thread is not None and thread.stage == stage


def has_fact(result: TurnResult, kind: str) -> bool:
    return any(fact.kind == kind for fact in result.turn.facts)


def gained_a_trait(result: TurnResult, before: frozenset[str]) -> bool:
    return bool({trait.id for trait in result.state.player.traits} - before)


def won_ways_are_open(result: TurnResult) -> bool:
    """A roll the player won has to open the door they forced; a roll they lost may leave the
    world exactly as it was — "the door holds" is a legitimate turn."""
    won = any(fact.data.get("outcome") in WON for fact in result.turn.facts)
    return not won or has_fact(result, "exit_unlocked")


def cases_for(engine_id: EngineId, settings: Settings) -> tuple[Case, ...]:
    _, start = begin(engine_id, settings)
    before = frozenset(trait.id for trait in start.player.traits)

    def in_cloister(far: str) -> Callable[[Game], Game]:
        return lambda state: staged(state, "cloister", [("cloister", far)])

    return (
        Case(
            id=f"{engine_id}/take-the-chart",
            engine_id=engine_id,
            prompt=(
                "I search the abbot's desk, find the folded chart hidden under the loose "
                "flagstone beneath it, and pick the chart up and keep it."
            ),
            expectations=(
                Expectation("chart-known", lambda r: known(r, "vault_map")),
                Expectation("chart-carried", lambda r: inside(r, "vault_map", "player")),
                Expectation("stair-charted", lambda r: staged_at(r, "vault-seal", "stair-charted")),
            ),
        ),
        Case(
            id=f"{engine_id}/walk-and-look",
            engine_id=engine_id,
            prompt="I walk from the study out into the cloister, and there I look around.",
            expectations=(
                Expectation("player-in-cloister", lambda r: inside(r, "player", "cloister")),
                Expectation("nothing-invented", lambda r: not has_fact(r, "entity_created")),
            ),
        ),
        Case(
            id=f"{engine_id}/open-the-way-and-climb",
            engine_id=engine_id,
            # No searching: a search for a hidden person is a legitimate roll under both engines,
            # and a `no` correctly leaves Elena unrevealed — which this case would score a miss.
            prompt=(
                "I climb the stair from the cloister up into the bell tower, and the moment I am "
                "up there I see the woman who keeps it standing among the beams."
            ),
            expectations=(
                Expectation("player-in-tower", lambda r: inside(r, "player", "bell_tower")),
                Expectation("elena-known", lambda r: known(r, "elena")),
                Expectation("rite-known", lambda r: staged_at(r, "vault-seal", "rite-known")),
            ),
            setup=in_cloister("bell_tower"),
        ),
        Case(
            id=f"{engine_id}/three-things",
            engine_id=engine_id,
            # The third clause has to be lasting: both engines define `add_trait` that way, so
            # "winded and shaking" scored rule-compliance as failure.
            prompt=(
                "I climb up from the cloister into the bell tower, hand my lantern to the woman "
                "I find there, and the climb leaves me with a wrenched knee I will be limping on "
                "for a long while."
            ),
            expectations=(
                Expectation("player-in-tower", lambda r: inside(r, "player", "bell_tower")),
                Expectation("elena-known", lambda r: known(r, "elena")),
                Expectation("lantern-given", lambda r: inside(r, "lantern", "elena")),
                Expectation(
                    "trait-gained",
                    lambda r: gained_a_trait(r, before),
                ),
            ),
            setup=in_cloister("bell_tower"),
        ),
        Case(
            id=f"{engine_id}/risky-lock",
            engine_id=engine_id,
            prompt=(
                "I set my shoulder to the locked vault door and try to force it open with my "
                "bare hands, knowing it may go badly for me."
            ),
            expectations=(
                Expectation("dice-rolled", lambda r: has_fact(r, "dice_rolled")),
                Expectation("win-written", won_ways_are_open),
            ),
            setup=in_cloister("vault"),
        ),
    )


def planned_steps(steps: Sequence[StepTrace]) -> list[str]:
    output = next((step.output for step in steps if step.name == "interpreter"), None)
    mechanics = output.get("mechanics") if isinstance(output, dict) else None
    if not isinstance(mechanics, list):
        return []
    return [
        f"{step.get('tool')}{' if ' + str(when) if (when := step.get('when')) else ''}"
        for step in mechanics
        if isinstance(step, dict)
    ]


async def play(case: Case, settings: Settings, seed: int) -> Run:
    engine, state = begin(case.engine_id, settings)
    opening = case.setup(state)
    # No source: a closed scenario builds no Expander, so no turn can expand its canon.
    stages = build_turn_agents(engine, settings, None)
    started = perf_counter()
    try:
        result = await run_turn(
            opening,
            case.prompt,
            engine=engine,
            stages=stages,
            settings=settings,
            rng=Random(seed),
        )
        steps = result.turn.steps
        return Run(
            passed={check.name: check.holds(result) for check in case.expectations},
            planned=planned_steps(steps),
            facts=[fact.kind for fact in result.turn.facts],
            director_calls=sum(1 for step in steps if step.name == "director"),
            total_steps=len(steps),
            seconds=perf_counter() - started,
            narration_chars=len(result.turn.narration),
        )
    except Exception as error:  # one failed turn is data, not the end of the benchmark
        return Run(
            error=f"{type(error).__name__}: {error}",
            passed={check.name: False for check in case.expectations},
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
            f"  {mean([run.seconds for run in runs]):.1f}s"
        )
        for name in case.expectations:
            print(f"    {name:<36} {case.rate(name):.0%}")
        for run in runs:
            if run.error is not None:
                print(f"    ! {run.error}")


def select(settings: Settings, ids: Sequence[str], engine: str | None) -> list[Case]:
    engines = ENGINES if engine is None else (EngineId(engine),)
    if unknown := [name for name in engines if name not in ENGINES]:
        raise SystemExit(f"unknown engine(s): {unknown}")
    cases = [case for name in engines for case in cases_for(name, settings)]
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
