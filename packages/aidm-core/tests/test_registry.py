from aidm.domain.engine import EngineRef, EngineStamp
from aidm.engine_api.contracts import (
    AdvancementEngine,
    EngineDescriptor,
    EngineDirector,
    EngineLifecycle,
    EnginePresentation,
    EngineRules,
)
from aidm.engine_api.registry import EngineRegistry


class StubEngine:
    descriptor = EngineDescriptor(
        ref=EngineRef(id="story", rules_version=1),
        schema_version=1,
    )

    @property
    def stamp(self) -> EngineStamp:
        return EngineStamp(id="story", rules_version=1, schema_version=1)

    @property
    def lifecycle(self) -> EngineLifecycle:
        raise AssertionError("not used")

    @property
    def director(self) -> EngineDirector:
        raise AssertionError("not used")

    @property
    def rules(self) -> EngineRules:
        raise AssertionError("not used")

    @property
    def presentation(self) -> EnginePresentation:
        raise AssertionError("not used")

    @property
    def advancement(self) -> AdvancementEngine | None:
        return None


def test_registry_constructs_only_the_selected_exact_engine() -> None:
    calls = 0

    def factory() -> StubEngine:
        nonlocal calls
        calls += 1
        return StubEngine()

    registry = EngineRegistry()
    registry.register(StubEngine.descriptor, factory)

    assert calls == 0
    assert registry.require(EngineRef(id="story", rules_version=1)).stamp.id == "story"
    assert registry.require(EngineRef(id="story", rules_version=1)).stamp.id == "story"
    assert calls == 1


def test_registry_rejects_a_wrong_exact_rules_version_before_construction() -> None:
    calls = 0

    def factory() -> StubEngine:
        nonlocal calls
        calls += 1
        return StubEngine()

    registry = EngineRegistry()
    registry.register(StubEngine.descriptor, factory)

    try:
        registry.require(EngineRef(id="story", rules_version=2))
    except ValueError as error:
        assert "rules_version" in str(error)
        assert "'rules_version': 2" in str(error)
        assert "'rules_version': 1" in str(error)
    else:
        raise AssertionError("wrong rules version was accepted")
    assert calls == 0
