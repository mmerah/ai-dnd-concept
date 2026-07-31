from dataclasses import dataclass, field

from aidm.domain.base import EngineId, Slug

from .bootstrap import Composition
from .session_model import Session


@dataclass(frozen=True, slots=True)
class _Origin:
    scenario_id: Slug
    character_id: Slug
    engine_id: EngineId

    def __str__(self) -> str:
        return f"{self.scenario_id}/{self.character_id} under {self.engine_id}"


@dataclass(slots=True)
class SessionRegistry:
    composition: Composition
    _sessions: dict[str, tuple[_Origin, Session]] = field(default_factory=dict)

    def session(
        self,
        slug: str,
        scenario_id: Slug,
        character_id: Slug,
        engine_id: EngineId,
    ) -> Session:
        wanted = _Origin(scenario_id, character_id, engine_id)
        held = self._sessions.get(slug)
        if held is not None:
            origin, session = held
            if origin != wanted:
                raise ValueError(f"open session {slug!r} plays {origin}, not {wanted}")
            return session
        application = self.composition.application(slug, scenario_id, character_id, engine_id)
        created = Session(
            app=application,
            advancement=self.composition.advancement_ui(application.engine),
        )
        self._sessions[slug] = (wanted, created)
        return created
