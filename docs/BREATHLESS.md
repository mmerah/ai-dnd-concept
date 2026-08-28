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

`packs/srd.json` will be transcribed from the SRD page above.

## Deviations in this repo

The engine is not built yet. Nothing to list: a rule not listed here is implemented as printed
once it exists.

## Settled before building

Catch Your Breath is a player action, so it runs with no Director turn. The complication it
introduces is Director judgement: the action writes one note to `world.pending_notes` ("the rules
owe a complication; open the next turn with one"), which the next Director prompt already renders.
No new core hook.

## Where the rules live

Mechanics will be in `src/aidm/engines/breathless/`. `packs/srd.json` — not this file — is the
transcription of record.
