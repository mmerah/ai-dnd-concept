# PROGRESS

One entry per `PLAN.md` phase: the counts it moved, what was decided off-plan, and what is known
and accepted.

## Phase 1: the dictation button

The mic button, its `SpeechRecognition` component, the page handlers, the CSS pulse and the three
tests went whole. The want is `IDEAS.md` item 22: a server-side transcription with its own key.

### Counts

| | before | after | plan target |
|---|---|---|---|
| `src` | 10,181 | **10,143** | about 10,143, within 10,136 to 10,150 |
| `tests` | 12,222 | **12,182** | about 12,182, within 12,176 to 12,188 |
| `qa` | 2,088 | **2,088** | unchanged |

Both counts landed on the plan's number.

### Decided off-plan

None. Every step landed as written.

### Reviews

Phases 1 and 2 were run in one pass and reviewed together as one staged diff by two Opus
reviewers (no `codex` on the machine, and the maintainer asked for Opus only). No finding named
phase 1. The two phases are two commits: the phase 1 tree was rebuilt from the shared files
(`game.py`, `theme.css`, `tests/ui/test_game.py`, `IDEAS.md`) and checked on its own.

### Known and accepted

Nothing.
