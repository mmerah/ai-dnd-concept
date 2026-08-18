from dataclasses import dataclass, field
from pathlib import Path

from pydantic_ai import Agent, UsageLimits
from pydantic_ai.messages import ModelMessage

from aidm.config import Settings
from aidm.content.sources import ExpansionPolicy, whole_text
from aidm.content.store import write_scenario
from aidm.state.base import Slug

from .agents import REQUEST_LIMIT, authored_overlay, summarize, world_agent, world_prompt
from .draft import WorldDraft
from .playability import FULL, Brief, Playtest, playability, playtests


@dataclass
class AuthoringSession:
    """One scenario under authorship across many agent runs; only `write` reaches disk."""

    slug: Slug
    premise: str
    config: Settings
    expansion: ExpansionPolicy
    art_style: str = ""
    document: Path | None = None
    brief: Brief = FULL
    history: list[ModelMessage] = field(default_factory=list)
    busy: bool = False
    playing: tuple[Playtest, ...] = field(init=False)
    agent: Agent[WorldDraft, str] = field(init=False)
    draft: WorldDraft = field(init=False)
    opening_prompt: str = field(init=False)

    def __post_init__(self) -> None:
        if self.document is None and not self.premise:
            raise ValueError("give a premise, a document, or both: there is nothing to author from")
        if self.expansion in ("cited", "cited_or_invented") and self.document is None:
            raise ValueError(
                f"a {self.expansion!r} scenario expands from a document: give one, or author it "
                "as `invented` or `closed`"
            )
        if (self.config.scenarios_dir / self.slug).exists():
            raise ValueError(f"scenario {self.slug!r} already exists")
        self.playing = playtests(self.config)
        self.agent = world_agent(self.slug, self.playing, self.config, self.brief)
        self.draft = WorldDraft(expansion=self.expansion)
        given = self.premise if self.document is None else whole_text(self.document)
        self.opening_prompt = world_prompt(self.slug, given, self.document is not None)

    async def send(self, instruction: str) -> str:
        """One agent turn against the same draft and the same history."""
        result = await self.agent.run(
            instruction,
            deps=self.draft,
            message_history=self.history,
            usage_limits=UsageLimits(request_limit=REQUEST_LIMIT),
        )
        self.history = list(result.all_messages())
        return result.output

    def refusal(self) -> str | None:
        return playability(self.draft, self.slug, self.playing, self.brief)

    async def write(self) -> str:
        """Revalidates the draft — the agent's 'ok' is never trusted — before writing overlays."""
        if reason := self.refusal():
            raise ValueError(f"the draft does not play: {reason}")
        # The form's style overrides whatever the author wrote from the source's own tone.
        self.draft.art_style = self.art_style or self.draft.art_style
        world = self.draft.world()
        overlays = {
            playtest.engine.id: await authored_overlay(playtest, self.slug, world, self.config)
            for playtest in self.playing
        }
        write_scenario(
            self.config.scenarios_dir, self.slug, world, overlays, self.document or self.premise
        )
        return summarize(world, overlays)
