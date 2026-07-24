"""The block vocabulary: the concrete renderable fragments a role's prompt is assembled from."""

from ..domain.models import hidden, known
from ..domain.reducer import render
from . import views
from .context import Block, DirectionBlock, RequestBlock

PREMISE = Block("SCENARIO", lambda c: f"{c.state.scenario.title}\n{c.state.scenario.premise}")
CHARACTER = Block("CHARACTER", lambda c: views.character(c.state))
KNOWN_ENTITIES = Block("KNOWN TO THE PLAYER", lambda c: views.briefs(known(c.state.world.entities)))
UNREVEALED_CANON = Block(
    "EXISTS BUT THE PLAYER DOES NOT KNOW IT YET",
    lambda c: views.briefs(hidden(c.state.world.entities)),
)
ENTITY_CATALOGUE = Block(
    "EVERYTHING THAT EXISTS", lambda c: views.briefs(c.state.world.entities.values())
)
RECENT_PLAY = Block("RECENT PLAY", lambda c: views.history(c.recent))

DIRECTOR_PLAN = DirectionBlock(
    "THE DIRECTOR'S PLAN — what was meant, not what happened", lambda c, d: d.intent
)
DIRECTOR_TONE = DirectionBlock("THE DIRECTOR ASKS FOR THIS TONE", lambda c, d: d.tone)
SPEAKER = DirectionBlock("SPEAKER", lambda c, d: views.speaker(c.state, d))
WHAT_HAPPENED = Block("WHAT HAPPENED", lambda c: render(c.events))
NARRATION = Block("NARRATION", lambda c: c.narration)
GROWTH_REQUEST = RequestBlock("CREATE", lambda c, r: views.request(r))
PLAYER_PROMPT = Block("PLAYER", lambda c: c.prompt)
