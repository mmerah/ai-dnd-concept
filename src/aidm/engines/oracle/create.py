from collections.abc import Mapping

from aidm.content.authored import CharacterOverlay, CharacterProfile, CreatedCharacter
from aidm.engines.loader import Creation
from aidm.state.base import Slug
from aidm.state.creation import CreationOption, CreationStep, Picks, check_picks, picked

_CONCEPTS: Mapping[Slug, tuple[str, str]] = {
    "wary-relic-hunter": (
        "A Wary Relic-Hunter",
        "Digs old ruins for pay and trusts nothing found inside them.",
    ),
    "broken-inquisitor": (
        "A Broken Inquisitor",
        "Once hunted heresies for a faith that no longer answers.",
    ),
    "runaway-cartographer": (
        "A Runaway Cartographer",
        "Fled a survey that found something no map should show.",
    ),
    "hedge-surgeon": (
        "A Hedge Surgeon",
        "Patches wounds and worse for coin, no questions asked.",
    ),
    "disgraced-duellist": (
        "A Disgraced Duellist",
        "Lost the duel that mattered, and lives with who saw it.",
    ),
}

_EDGES: Mapping[Slug, tuple[str, str]] = {
    "reads-old-stonework": (
        "Reads Old Stonework",
        "Makes sense of inscriptions and stonework that everyone else reads as rubble.",
    ),
    "quiet-hands": (
        "Quiet Hands",
        "Picks locks, pockets, and latches without a sound.",
    ),
    "steady-under-fire": (
        "Steady Under Fire",
        "Keeps a clear head once things turn violent.",
    ),
    "talks-their-way-in": (
        "Talks Their Way In",
        "Talks past guards, clerks, and doors that should stay shut.",
    ),
    "knows-the-old-rites": (
        "Knows the Old Rites",
        "Recognizes an old rite or ritual for what it actually is.",
    ),
    "never-loses-the-trail": (
        "Never Loses the Trail",
        "Follows a trail across ground that hides it from anyone else.",
    ),
}

_BURDENS: Mapping[Slug, tuple[str, str]] = {
    "never-walks-away": (
        "Never Walks Away",
        "Cannot leave a fight, or a wrong, unfinished.",
    ),
    "owes-a-bad-debt": (
        "Owes a Bad Debt",
        "Owes someone dangerous, and they will collect.",
    ),
    "cannot-leave-a-question-alone": (
        "Cannot Leave a Question Alone",
        "Cannot let a loose thread go unpulled, whatever it costs.",
    ),
    "known-to-the-wrong-people": (
        "Known to the Wrong People",
        "Recognized by people who are best left as strangers.",
    ),
    "flinches-at-the-dark": (
        "Flinches at the Dark",
        "Freezes when the light goes and the dark closes in.",
    ),
}

_GEAR: Mapping[Slug, tuple[str, str]] = {
    "pry-bar": (
        "Pry Bar",
        "Forces a door, a crate, or a stubborn slab of stone.",
    ),
    "chalk-and-wire": (
        "Chalk and Wire",
        "Marks a trail and rigs a lock from chalk and a length of wire.",
    ),
    "guttering-lantern": (
        "Guttering Lantern",
        "Throws light into places that would rather stay dark.",
    ),
    "worn-duelling-blade": (
        "Worn Duelling Blade",
        "A blade worn smooth from a life spent drawing it.",
    ),
    "physicians-roll": (
        "Physician's Roll",
        "Splints, stitches, and staves off the worst of a wound.",
    ),
    "forged-seal-and-ink": (
        "Forged Seal and Ink",
        "Forges a seal and passes as someone with the right to be there.",
    ),
}


def _options(entries: Mapping[Slug, tuple[str, str]]) -> tuple[CreationOption, ...]:
    return tuple(
        CreationOption(id=key, label=label, detail=detail)
        for key, (label, detail) in entries.items()
    )


_STEPS = (
    CreationStep(id="concept", prompt="Choose a concept", options=_options(_CONCEPTS)),
    CreationStep(id="edges", prompt="Choose two edges", options=_options(_EDGES), choose=2),
    CreationStep(id="burden", prompt="Choose a burden", options=_options(_BURDENS)),
    CreationStep(id="gear", prompt="Choose two pieces of gear", options=_options(_GEAR), choose=2),
)


class OracleCreation(Creation):
    def steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        del picks  # every oracle step is static
        return _STEPS

    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        check_picks(_STEPS, picks)
        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief),
            overlay=CharacterOverlay(
                character={
                    "concept": _CONCEPTS[picked(picks, "concept")[0]][0],
                    "edges": [_EDGES[edge][0] for edge in picked(picks, "edges")],
                    "burdens": [_BURDENS[picked(picks, "burden")[0]][0]],
                    "gear": [_GEAR[gear][0] for gear in picked(picks, "gear")],
                }
            ),
        )
