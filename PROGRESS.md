# Progress

Tracking PLAN.md. One bullet per landed step; `uv run pytest && ruff check && ruff format --check
&& basedpyright` green at each.

## Done

- 2026-08-13: recentering decided and PLAN.md rewritten — phases: 1 delete story, 2 oracle→loner3e
  (SRD-compliant, tables resolver-side), 3 docs-only engine shelf, then scenario creator, media.
- 2026-08-13: docs/24XX.md — exact SRD v1.4 (CC BY), engine package sketch filled.
- 2026-08-13: docs/LONER-3E.md — full 3e SRD from the lonersrd GitHub source (CC BY-SA); sketch
  filled; PLAN phase 2 gap list corrected against the exact text (conflict-no-tick is already
  SRD-exact; no Luck-spend rule exists).
- 2026-08-13: docs/CAIRN-2E.md — 2e Player's Guide mechanics extraction (CC BY-SA); sketch
  filled; verdict ~2× loner3e code, stays on the shelf.

- 2026-08-13: Phase 1 done — `cce1701` eval harness deleted (−1,199), `d20da72` story engine +
  tests + fixtures + overlays deleted, core tests repointed to oracle (−3,177/+123), `459a8d7`
  stranded trims: offer choice fields, `AllocationStep`, dice `vs=` (−183/+31). Suite 99 green,
  no SAVE_VERSION bump; only fixture movement is the always-null `vs`/`success` keys leaving
  the turn trace. Reviewed: sweeps clean, probe/oracle engines untouched.

## Next

- Phase 2: rename oracle→loner3e, roll the twist table resolver-side, settle the named gaps.
