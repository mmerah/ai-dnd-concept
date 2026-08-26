# Fate Condensed

A compact, complete version of Fate Core: aspects, four Fate dice, the adjective ladder, fate
points, stress and consequences.

## Official sources

- CC BY SRD archive, containing `Fate-Condensed-SRD-CC-BY.html`, the file the old extraction was
  taken from: <https://fate-srd.com/downloads/CC-BY-SRDs.zip>
- Evil Hat's licensing page, which names that archive as the source to work from:
  <https://fate-srd.com/official-licensing-fate>
- Browsable rules and explanatory guides: <https://fate-srd.com/fate-condensed>

This file used to hold a near-verbatim extraction of the SRD. It was deleted so that no pack is
ever transcribed out of a copy: build from the archive above. The old text is in git history. Note
that the official archive contains unresolved `page XX` cross-references; they are part of the
source.

## Licence and attribution

Fate Condensed ©2020 Evil Hat Productions, LLC, licensed under Creative Commons Attribution 3.0
Unported (<http://creativecommons.org/licenses/by/3.0/>). The licence requires this exact paragraph
wherever our own copyright appears, in the same size as the copyright text — it is reproduced in
`README.md`, and ships with the engine's pack and `director.md`:

> This work is based on Fate Condensed (found at http://www.faterpg.com/), a product of Evil Hat
> Productions, LLC, developed, authored, and edited by PK Sullivan, Lara Turner, Leonard Balsera,
> Fred Hicks, Richard Bellingham, Robert Hanz, Ryan Macklin, and Sophie Lagacé, and licensed for
> our use under the Creative Commons Attribution 3.0 Unported license
> (http://creativecommons.org/licenses/by/3.0/).

Take this paragraph from the archive, not from the licensing page: the web rendering omits Leonard
Balsera and Ryan Macklin, and the archive is the copy the SRD itself says must be provided.

Credits as printed: Fate Condensed by PK Sullivan, Lara Turner and Fred Hicks, with additional
development by Richard Bellingham, Robert Hanz and Sophie Lagacé; based on prior works by Rob
Donoghue, Fred Hicks, Leonard Balsera, Ryan Macklin, Clark Valentine, Mike Olson, Brian Engard and
Sophie Lagacé; based on Fate Core System by Leonard Balsera, Brian Engard, Jeremy Keller, Ryan
Macklin and Mike Olson, and Fate Accelerated Edition by Clark Valentine.

## Pack sources

No separate pack sources. The 19 skills and the ladder are in the SRD itself; alternate skill lists
are its own optional rule, § "Changing the Skill List".

## Deviations in this repo

The engine is not implemented yet; this list is written when `src/aidm/engines/fate/` lands. It
carries every divergence from the official rules with the reason it stands, so that nothing
diverges silently.

## Where the rules live

Mechanics will live in `src/aidm/engines/fate/`. `packs/srd.json` — not this file — is the
transcription of record.
