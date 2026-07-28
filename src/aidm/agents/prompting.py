from ..domain.models import Direction, GrowthRequest, Role
from ..domain.reducer import render
from . import views
from .context import TurnContext

NATIVE_HISTORY: frozenset[Role] = frozenset({"director", "narrator", "maintainer"})


def _sections(*parts: tuple[str, str]) -> str:
    return "\n\n".join(f"{label}:\n{body}" for label, body in parts)


def _premise(context: TurnContext) -> tuple[str, str]:
    return "SCENARIO", f"{context.state.scenario.title}\n{context.state.scenario.premise}"


def director_prompt(context: TurnContext) -> str:
    scene, content = context.scene, context.content
    return _sections(
        _premise(context),
        ("CHARACTER", views.character(scene, content)),
        ("HERE WITH THE PLAYER", views.here(scene)),
        ("STAT BLOCKS OF WHO IS HERE", views.statblocks(scene, content)),
        ("KNOWN TO THE PLAYER, BUT ELSEWHERE", views.elsewhere(scene)),
        ("EXISTS BUT THE PLAYER DOES NOT KNOW IT YET", views.unrevealed(scene)),
        ("PLAYER", context.prompt),
    )


def narrator_prompt(context: TurnContext, direction: Direction) -> str:
    """Exclude unrevealed canon from the role that writes player prose."""
    scene = context.scene
    return _sections(
        _premise(context),
        ("CHARACTER", views.character(scene, context.content)),
        ("HERE WITH THE PLAYER", views.here(scene)),
        ("KNOWN TO THE PLAYER, BUT ELSEWHERE", views.elsewhere(scene)),
        ("THE DIRECTOR'S PLAN — what was meant, not what happened", direction.intent),
        ("THE DIRECTOR ASKS FOR THIS TONE", direction.tone),
        ("SPEAKER", views.speaker(scene, direction)),
        # Resolved events must override intent.
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
