# Breathless

A rules-light survival system: risky actions roll a skill or item die that steps down one size
after every roll, until Catch Your Breath resets them and adds a complication.

## Official sources

- SRD (v2.1, 2026-05-08 — the text this repo's engine is built from):
  <https://keeper.farirpgs.com/resources/fari-rpgs/breathless/breathless-srd/>
- Official itch.io page: <https://farirpgs.itch.io/breathless-srd>

## Licence and attribution

ORC License. The required credit, verbatim, wherever a copyright appears:

> This work is based on Breathless, product of Fari RPGs (https://farirpgs.com/), developed and
> authored by René-Pier Deshaies-Gélinas. This product is licensed under the ORC License available
> online at various locations including www.azoralaw.com/orclicense.

## Pack sources

No separate pack sources. The six skills and the rolling tables (jobs, weapons, long-range weapons,
locations, complications, missions) are all in the SRD at the page above, transcribed into
`packs/srd.json`.

## Deviations in this repo

Every divergence between `src/aidm/engines/breathless/` and the official rules, with the reason it
stands. Nothing diverges silently: a rule not listed here is implemented as printed.

1. **Before We Start is not modelled.** The SRD opens with a content warning and a lines-and-veils
   step before play. This is a table procedure with no rule inside it; the app has no seat for it.
   Nothing in play depends on it.

Three readings the SRD leaves open are settled without diverging from it: stress is a counter that
stops at 4 (the SRD names 4 as the threshold for vulnerable and nothing above it); a luck test is
read on the check ladder, the SRD's "interpret the result as you see fit"; and a med kit is a
mark on the sheet rather than an item, since the SRD counts it apart from the three items.

## Where the rules live

Mechanics are in `src/aidm/engines/breathless/`. `packs/srd.json` — not this file — is the
transcription of record.
