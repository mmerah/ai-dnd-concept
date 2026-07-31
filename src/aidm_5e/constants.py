from aidm.domain.base import Slug
from aidm.domain.engine import EngineRef
from aidm.engine_api.contracts import EngineDescriptor

ENGINE_ID: Slug = "dnd5e"
RULES_VERSION = 1
SCHEMA_VERSION = 1
ENGINE_REF = EngineRef(id=ENGINE_ID, rules_version=RULES_VERSION)
DESCRIPTOR = EngineDescriptor(ref=ENGINE_REF, schema_version=SCHEMA_VERSION)
