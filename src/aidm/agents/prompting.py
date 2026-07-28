"""The entire context policy of the application: one builder per role, and the signature of each
is the policy — a role's prompt cannot be built without the payload its stage carries. Each builder
binds the turn's `Scene` once, and the buckets it reads are what that role may see."""

from ..domain.models import Direction, GrowthRequest, Role
from ..domain.reducer import render
from . import views
from .context import TurnContext

# The roles that also receive play history as native messages; the Creator reads it as RECENT PLAY.
NATIVE_HISTORY: frozenset[Role] = frozenset({"director", "narrator", "maintainer"})


def _sections(*parts: tuple[str, str]) -> str:
    return "\n\n".join(f"{label}:\n{body}" for label, body in parts)


def _premise(context: TurnContext) -> tuple[str, str]:
    return "SCENARIO", f"{context.state.scenario.title}\n{context.state.scenario.premise}"


def director_prompt(context: TurnContext) -> str:
    scene, library = context.scene, context.library
    return _sections(
        _premise(context),
        ("CHARACTER", views.character(scene, library)),
        ("HERE WITH THE PLAYER", views.here(scene)),
        ("STAT BLOCKS OF WHO IS HERE", views.statblocks(scene, library)),
        ("KNOWN TO THE PLAYER, BUT ELSEWHERE", views.elsewhere(scene)),
        ("EXISTS BUT THE PLAYER DOES NOT KNOW IT YET", views.unrevealed(scene)),
        ("PLAYER", context.prompt),
    )


def narrator_prompt(context: TurnContext, direction: Direction) -> str:
    """No unrevealed canon and no catalogue: the Narrator alone writes what the player reads."""
    scene = context.scene
    return _sections(
        _premise(context),
        ("CHARACTER", views.character(scene, context.library)),
        ("HERE WITH THE PLAYER", views.here(scene)),
        ("KNOWN TO THE PLAYER, BUT ELSEWHERE", views.elsewhere(scene)),
        ("THE DIRECTOR'S PLAN — what was meant, not what happened", direction.intent),
        ("THE DIRECTOR ASKS FOR THIS TONE", direction.tone),
        ("SPEAKER", views.speaker(scene, direction)),
        # Last of the three, because a resolved outcome overrules the plan that asked for it.
        ("WHAT HAPPENED", render(context.events)),
        ("PLAYER", context.prompt),
    )


def maintainer_prompt(context: TurnContext) -> str:
    return _sections(
        _premise(context),
        ("EVERYTHING THAT EXISTS", views.catalogue(context.scene)),
        ("PLAYER", context.prompt),
        ("WHAT HAPPENED", render(context.events)),
        ("NARRATION", context.narration),
    )


def creator_prompt(context: TurnContext, request: GrowthRequest) -> str:
    return _sections(
        _premise(context),
        ("EVERYTHING THAT EXISTS", views.catalogue(context.scene)),
        ("RECENT PLAY", views.history(context.recent)),
        ("NARRATION", context.narration),
        ("CREATE", views.request(request)),
    )
