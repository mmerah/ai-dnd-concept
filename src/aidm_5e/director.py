import json
from random import Random

from pydantic import TypeAdapter, ValidationError
from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.output import OutputSpec

from aidm.agents.context import DirectorScene
from aidm.domain.base import EntityId
from aidm.domain.direction import DirectionRecord
from aidm.domain.entities import ActorEntity

from .agents.instructions import MECHANICS
from .constants import ENGINE_ID, SCHEMA_VERSION
from .domain.models.consequences import Consequence, References, flatten
from .domain.models.direction import Dnd5eDirection
from .rules import Dnd5eRules
from .scene_state import state_from_scene

MECHANICS_ADAPTER: TypeAdapter[list[Consequence]] = TypeAdapter(list[Consequence])

_DRY_RUN_SEEDS = (2, 5)


class Dnd5eDirector:
    def __init__(self, rules: Dnd5eRules) -> None:
        self._rules = rules

    @property
    def output(self) -> OutputSpec[Dnd5eDirection]:
        return NativeOutput(Dnd5eDirection)

    def instructions(self) -> str:
        return MECHANICS

    def validate(
        self,
        ctx: RunContext[DirectorScene],
        direction: Dnd5eDirection,
    ) -> Dnd5eDirection:
        scene = ctx.deps
        refs = [
            (EntityId(str(entity_id)), reference) for entity_id, reference in direction.canon_refs()
        ]
        if direction.speaker_id is not None:
            refs.append(
                (
                    EntityId(str(direction.speaker_id)),
                    References("actor", present=True),
                )
            )
        faults = [direction.check()]
        faults.extend(consequence.check() for consequence in flatten(direction.mechanics))
        if fault := next((item for item in faults if item is not None), None):
            raise ModelRetry(fault)
        canon = scene.canon.entities
        missing = sorted({entity_id for entity_id, _ in refs if entity_id not in canon})
        if missing:
            raise ModelRetry(f"unknown entity id(s): {missing}. Use only ids you were shown.")
        mismatched = sorted(
            f"{entity_id} is a {canon[entity_id].kind}, not a {reference.kind}"
            for entity_id, reference in refs
            if reference.kind is not None and canon[entity_id].kind != reference.kind
        )
        if mismatched:
            raise ModelRetry(
                f"wrong kind of entity: {'; '.join(mismatched)}. "
                "Use an id of the kind each field asks for."
            )
        absent = sorted(
            {
                entity_id
                for entity_id, reference in refs
                if reference.present and not scene.is_here(canon[entity_id])
            }
        )
        if absent:
            raise ModelRetry(
                f"not here with the player: {absent}. Move them here first, or act on who is here."
            )
        if direction.speaker_id is not None:
            speaker = canon[EntityId(str(direction.speaker_id))]
            if (
                not isinstance(speaker, ActorEntity)
                or not speaker.known
                or not scene.is_here(speaker)
            ):
                raise ModelRetry(
                    f"speaker {str(direction.speaker_id)!r} must be an NPC the player has met "
                    "and who is here with them. Use null if nobody is being addressed."
                )
        self._dry_run(direction, scene)
        return direction

    def _dry_run(self, direction: Dnd5eDirection, scene: DirectorScene) -> None:
        state = state_from_scene(scene, ENGINE_ID)
        for seed in _DRY_RUN_SEEDS:
            try:
                _ = self._rules.resolve(direction, state, Random(seed))
            except ValidationError:
                raise
            except ValueError as error:
                raise ModelRetry(f"{error}. Propose mechanics this state allows.") from error

    def record(self, direction: Dnd5eDirection) -> DirectionRecord:
        mechanics: object = json.loads(MECHANICS_ADAPTER.dump_json(direction.mechanics))
        return DirectionRecord.model_validate(
            {
                "engine": ENGINE_ID,
                "schema_version": SCHEMA_VERSION,
                "intent": direction.intent,
                "tone": direction.tone,
                "speaker_id": direction.speaker_id,
                "mechanics": mechanics,
            }
        )
