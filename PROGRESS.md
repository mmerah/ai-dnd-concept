# PROGRESS

Tracks `PLAN.md`. One section per phase; done items stay so the next reader sees what landed.

## Phase 0 — docs become pointers, not copies — DONE

- Fate Condensed's CC BY 3.0 attribution paragraph moved into `README.md` **before** the deletion,
  quoted verbatim (the licence breach risk of this phase).
- `docs/24XX.md` 367 → 60 lines, `docs/LONER-3E.md` 946 → 80, `docs/CAIRN-BAREBONES.md` 1476 → 48,
  `docs/FATE-CONDENSED.md` 1408 → 53. Each carries: official source URLs + guides, the archive or
  commit the old extraction came from, licence and exact attribution string, per-pack source URLs,
  deviations, and where the mechanics live.
- Deviations carried over whole, unnumbered preambles included (24XX help/bulky/shares-the-risk/
  invent-branch; Loner Adventure Maker/5W+H/mood-roll/Appendix A). Cairn and Fate get an empty
  Deviations section for their own phases to fill.
- Loner deviation 2 reworded per the plan's reverse case: a non-living character is refused, not
  given a sheet on demand.
- `Planned engine package` / `Engine package sketch` sections deleted — superseded by `plans/L5-*`
  and `plans/L6-*`.
- Prose references updated: `README.md` engine-shelf paragraph and licensing table (per-doc rows
  dropped, one line points at the pointer files), `loner3e/rules.py:25`, `twentyfourxx/rules.py:27`,
  `IDEAS.md:7-8`. README's "next engine" order now matches the plan: Cairn, then Fate.
- Verified: `pytest` 253 passed, `ruff check`, `ruff format --check`, `basedpyright` clean.
- Adversarial review round (every URL fetched, licences checked live, deviations diffed byte-wise).
  Fate's attribution confirmed byte-identical to the archive copy — no breach. Nine findings fixed:
  Cairn's Scars table is on `barebones-core-rules`, not the three pages named; Cairn's "required
  attribution" was a composed string the source does not print (relabelled); the Loner explanatory
  guide covers 2e, now caveated; the dead `faterpg.com/licensing` bullet dropped; the Loner
  extraction pinned to commit `2946f2f`; the AP01 footer quoted exactly (`© 2021-2026`, and the page
  carries no CC declaration at all); the 24XX credit condition includes the version number;
  `plans/L3-engine-shape.md:71` retargeted off the deleted section; `PLAN.md` now points here.

## Phase 1 — L3 engine shape — not started
## Phase 2 — L4 rules compliance — not started
## Phase 3 — L6 Cairn Barebones — not started
## Phase 4 — L5 Fate Condensed — not started
