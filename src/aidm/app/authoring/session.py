from dataclasses import dataclass, field
from pathlib import Path

from pydantic_ai import Agent, UsageLimits
from pydantic_ai.messages import ModelMessage

from aidm.config import Settings
from aidm.content.io import whole_text, write_scenario
from aidm.state.model import EngineId, Slug

from .agents import REQUEST_LIMIT, summarize, world_agent, world_prompt
from .draft import WorldDraft
from .playability import FULL, Brief, Playtest, playability, playtests


@dataclass
class AuthoringSession:
    """One scenario under authorship across many agent runs; only `write` reaches disk."""

    slug: Slug
    premise: str
    config: Settings
    grows: bool
    engines: tuple[EngineId, ...]
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
        if (self.config.scenarios_dir / self.slug).exists():
            raise ValueError(f"scenario {self.slug!r} already exists")
        self.playing = playtests(self.config, self.engines)
        self.agent = world_agent(self.playing, self.config, self.brief)
        self.draft = WorldDraft(grows=self.grows)
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
        return playability(self.draft, self.playing, self.brief)

    async def write(self) -> str:
        """Revalidates the draft — the agent's 'ok' is never trusted — before it reaches disk."""
        if reason := self.refusal():
            raise ValueError(f"the draft does not play: {reason}")
        # The form's style overrides whatever the author wrote from the source's own tone.
        self.draft.art_style = self.art_style or self.draft.art_style
        scenario = self.draft.scenario(self.engines)
        write_scenario(
            self.config.scenarios_dir, self.slug, scenario, self.document or self.premise
        )
        return summarize(scenario)
