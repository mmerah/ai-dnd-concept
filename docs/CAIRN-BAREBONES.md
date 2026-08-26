# Cairn: Barebones Edition

A classless d20-under fantasy adventure game: three attributes, Hit Protection, slot inventory,
saves for everything risky, damage that hits automatically.

## Official sources

- Rules, eight pages starting at
  <https://cairnrpg.com/barebones/rules/introduction-to-cairn-barebones-edition/>
- Markdown source directory, at the commit the old extraction was taken from
  (`009578e8e98f7d235daf3f884da2ea3c14e758c4`, 2026-08-18):
  <https://github.com/yochaigal/cairn/tree/009578e8e98f7d235daf3f884da2ea3c14e758c4/barebones/rules>
- Release page: <https://yochaigal.itch.io/cairn-barebones-edition>
- Author's site and design notes: <https://newschoolrevolution.com/>

Barebones is presented as an edition rather than a separately versioned SRD; "SRD" in this repo
means that complete open rules reference. This file used to hold a near-verbatim extraction of it.
It was deleted so that no pack is ever transcribed out of a copy: build from the official pages
above. The old text is in git history.

## Licence and attribution

Cairn was written by Yochai Gal. The official repository and site state that the full text is
licensed under Creative Commons Attribution-ShareAlike 4.0 International
(<https://creativecommons.org/licenses/by-sa/4.0/>). ShareAlike binds the adaptations — this repo's
pack and `director.md` — which carry it. The source prints no fixed attribution string, and states
that no permission or notification is required for third-party material; CC BY-SA 4.0 §3(a) asks for
creator, title, licence link and an indication of changes. This repo ships:

> This work is based on Cairn: Barebones Edition (<https://cairnrpg.com/barebones/>) by Yochai Gal,
> licensed under Creative Commons Attribution-ShareAlike 4.0 International.

## Pack sources

- `packs/srd.json` — the eight rules pages above, of which `barebones-character-creation`,
  `barebones-gear-packages`, `barebones-marketplace` and `barebones-core-rules` (the Scars table,
  which is on none of the other three) carry every table the pack needs.
- Barebones itself ships no bestiary; opponents and locations stay scenario canon. Later packs may
  draw on <https://cairnrpg.com/resources/monsters/> and
  <https://cairnrpg.com/resources/third-party-content/>.

## Deviations in this repo

The engine is not implemented yet; this list is written when `src/aidm/engines/cairn/` lands. It
carries every divergence from the official rules with the reason it stands, so that nothing
diverges silently.

## Where the rules live

Mechanics will live in `src/aidm/engines/cairn/`. `packs/srd.json` — not this file — is the
transcription of record.
