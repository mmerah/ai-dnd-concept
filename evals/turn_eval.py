import argparse
import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from statistics import mean
from time import perf_counter

from aidm.app.launch import begin_game, build_engine
from aidm.config import Settings, load_settings
from aidm.content.io import load_character, load_scenario
from aidm.engines.core import Engine
from aidm.state.model import Answer, EngineId, EntityId, Frozen, Game, Turn
from aidm.turn.run import TurnResult, build_turn_agents, run_segment

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"
SCENARIO_ID = "whispering-vault"
CHARACTER_ID = "kael"
ENGINES = (EngineId("loner3e"), EngineId("twentyfourxx"))
# Both engines' outcomes for an attempt that got what it reached for.
WON = ("yes-and", "yes", "yes-but", "success")
# The longest valid chain is stake -> proceed -> defence.
SEGMENT_CAP = 4
# Script option-bearing decisions that continue the action; Loner conflicts have no options.
ANSWERS: Mapping[str, str] = {"stake": "proceed", "defence": "take-it"}


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
    # Which option answers each pending kind this case's fixture can suspend on.
    answers: Mapping[str, str] = field(default_factory=lambda: ANSWERS)


class Run(Frozen):
    error: str | None = None
    passed: dict[str, bool] = {}
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


def begin(engine_id: EngineId, settings: Settings) -> tuple[Engine, Game]:
    engine = build_engine(engine_id)
    scenario = load_scenario(ROOT / settings.scenarios_dir, SCENARIO_ID)
    character = load_character(
        ROOT / settings.characters_dir, CHARACTER_ID, engine.id, engine.check_overlay
    )
    return engine, begin_game(engine, SCENARIO_ID, scenario, character)


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


def luck_moved(result: TurnResult) -> bool:
    return any(
        fact.kind == "counter_changed" and fact.data.get("counter") == "luck"
        for fact in result.turn.facts
    )


def conflict_handed_back(result: TurnResult) -> bool:
    pending = result.state.pending
    return pending is not None and pending.kind == "conflict"


def staked_before_rolling(result: TurnResult) -> bool:
    """The first segment ended on the stake's hand-back, with no roll taken in it."""
    history = result.state.history
    return (
        bool(history)
        and bool(history[0].decision)
        and not any(event.tool == "roll_attempt" for event in history[0].events)
    )


def won_climbs_arrive(result: TurnResult) -> bool:
    """Require successful climbs to arrive while allowing failed climbs to remain below."""
    won = any(fact.data.get("outcome") in WON for fact in result.turn.facts)
    return not won or inside(result, "player", "bell_tower")


def cases_for(engine_id: EngineId, settings: Settings) -> tuple[Case, ...]:
    _, start = begin(engine_id, settings)
    before = frozenset(trait.id for trait in start.player.traits)

    def in_cloister(far: str) -> Callable[[Game], Game]:
        return lambda state: staged(state, "cloister", [("cloister", far)])

    # Only 24XX declares the stake tool, so only there is skipping it a miss.
    stake_checks = (
        (Expectation("staked", staked_before_rolling),) if engine_id == "twentyfourxx" else ()
    )
    cases = (
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
            # Exclude searches because a valid failed search leaves Elena hidden.
            prompt=(
                "I climb the stair from the cloister up into the bell tower, and the moment I am "
                "up there I see the woman who keeps it standing among the beams."
            ),
            expectations=(
                Expectation("player-in-tower", lambda r: inside(r, "player", "bell_tower")),
                Expectation("elena-known", lambda r: known(r, "elena")),
                Expectation(
                    "archivist-found", lambda r: staged_at(r, "vault-seal", "archivist-found")
                ),
            ),
            setup=in_cloister("bell_tower"),
        ),
        Case(
            id=f"{engine_id}/three-things",
            engine_id=engine_id,
            # Require a lasting effect because both engines define `add_trait` that way.
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
            id=f"{engine_id}/risky-climb",
            engine_id=engine_id,
            # Reckless climbing implies danger without accepting a risk, so 24XX must stake it.
            prompt=(
                "I go up the bell tower's ladders at a run, two rungs at a time — I have to "
                "reach the top before the light goes."
            ),
            expectations=(
                *stake_checks,
                Expectation("dice-rolled", lambda r: has_fact(r, "dice_rolled")),
                Expectation("win-upstairs", won_climbs_arrive),
            ),
            setup=in_cloister("bell_tower"),
        ),
    )
    if engine_id == "loner3e":
        cases += (
            Case(
                id=f"{engine_id}/fight-the-rat",
                engine_id=engine_id,
                prompt=(
                    "The bloated rat springs at my throat and I fight it in earnest — it has "
                    "to die before it slips back into the walls."
                ),
                expectations=(
                    # Require the rat so a Tomas conflict cannot satisfy the other checks.
                    Expectation("rat-engaged", lambda r: known(r, "cloister_rat")),
                    Expectation("luck-moved", luck_moved),
                    Expectation("hands-back", conflict_handed_back),
                ),
                setup=lambda state: staged(state, "cloister", []),
            ),
        )
    return cases


async def play(case: Case, settings: Settings, seed: int) -> Run:
    engine, state = begin(case.engine_id, settings)
    stages = build_turn_agents(engine, settings)
    rng = Random(seed)
    started = perf_counter()
    try:
        segments: list[TurnResult] = []
        played, player_input = case.setup(state), case.prompt
        for _ in range(SEGMENT_CAP):
            result = await run_segment(
                played,
                player_input,
                engine=engine,
                stages=stages,
                settings=settings,
                rng=rng,
            )
            segments.append(result)
            played = result.state
            if played.pending is None:
                break
            chosen = case.answers.get(played.pending.kind)
            if chosen is None:
                # An unscripted hand-back ends the interaction; the expectations judge it.
                break
            player_input = Answer(option_id=chosen)
        else:
            raise ValueError(f"the interaction was still going after {SEGMENT_CAP} segments")
        merged = _merged(case.prompt, segments)
        steps = merged.turn.steps
        return Run(
            passed={check.name: check.holds(merged) for check in case.expectations},
            facts=[fact.kind for fact in merged.turn.facts],
            director_calls=sum(1 for step in steps if step.name == "director"),
            total_steps=len(steps),
            seconds=perf_counter() - started,
            narration_chars=len(merged.turn.narration),
        )
    except Exception as error:
        return Run(
            error=f"{type(error).__name__}: {error}",
            passed={check.name: False for check in case.expectations},
            seconds=perf_counter() - started,
        )


def _merged(prompt: str, segments: Sequence[TurnResult]) -> TurnResult:
    """The interaction as one result: every segment's prose, facts and steps, the last state."""
    return TurnResult(
        state=segments[-1].state,
        turn=Turn(
            prompt=prompt,
            facts=tuple(fact for segment in segments for fact in segment.turn.facts),
            narration="\n".join(
                segment.turn.narration for segment in segments if segment.turn.narration
            ),
            steps=tuple(step for segment in segments for step in segment.turn.steps),
        ),
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
