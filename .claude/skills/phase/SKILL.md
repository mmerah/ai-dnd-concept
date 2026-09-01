---
name: phase
description: Run one PLAN.md phase end to end — brief, Opus implementer driving Codex Luna, Fable + Codex Sol adversarial reviews, fold, PROGRESS.md entry — and stop before the commit. Use when the user says "implement phase N", "run phase N", or "/phase N".
argument-hint: <phase number or name>
---

# /phase $ARGUMENTS

You are the orchestrator. You read, brief, spawn, relay, verify, and record. You do not write
code and you do not commit. Restate `step k of 6` at the top of every message to the user.

## 1. Brief

Read `PLAN.md` (the "How to work" rules and phase $ARGUMENTS), `PROGRESS.md` (standing
decisions), and `CLAUDE.md`. Record the `src` line count from the `PLAN.md` command.
Write `/tmp/phase-$ARGUMENTS/brief.md`:

```
# Phase <N> — <title>
## Goal            one paragraph, copied intent not paraphrased rules
## Steps           numbered, one action each, straight from PLAN.md
## Done when       observable checks: tests named, behaviour named, line-count target
## Out of scope    what the phase must not touch; standing decisions it must not re-open
## Files           the files each step touches, as far as PLAN.md names them
```

If PLAN.md is ambiguous on something that changes the work, ask the user once, now.

## 2. Implement

`Agent(subagent_type="implementer", prompt="Implement the brief at /tmp/phase-N/brief.md")`.
Keep its agent id; you will message it again. When it reports, check the four commands yourself
and `git diff --cached --stat`. A skipped step goes back to the implementer before any review.

## 3. Review — both at once, in one message

- `Agent(subagent_type="reviewer", prompt="Review the staged phase; brief: /tmp/phase-N/brief.md")`
- `cat .claude/prompts/review.md > /tmp/phase-N/sol.md; echo "Brief: /tmp/phase-N/brief.md" >> /tmp/phase-N/sol.md;
   .claude/scripts/codex.sh gpt-5.6-sol high read-only < /tmp/phase-N/sol.md > /tmp/phase-N/review-sol.md`
  (Bash, `run_in_background: true`)

Save the Fable review to `/tmp/phase-N/review-fable.md`.

## 4. Fold

`SendMessage` both review files' contents to the implementer: "Fold these. Fix or refute each."
Read its table. Any refutation you do not agree with: hand it to the user with the reviewer's
finding and the implementer's reason side by side. Do not decide it for them.

## 5. Verify

Run the four `PLAN.md` commands and `uv run aidm` smoke if the phase touched the game. Count `src`
lines again. Read the staged diff's `--stat` and open anything the reviews flagged as fixed.

## 6. Record and stop

Add the phase's `PROGRESS.md` entry: counts before/after, decisions made off-plan, refuted
findings and why, anything known-and-accepted. Stage it. Tell the user in five lines: counts,
refutations awaiting their call, and "ready to commit". The commit is theirs.
