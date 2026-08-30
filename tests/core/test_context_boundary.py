from core_test_support import ENGINES_BUILT, LONER3E, game, updated, with_entity
from pydantic import JsonValue

from aidm.engines.core import Engine
from aidm.kernel.views import NarratorView
from aidm.state.entities import PLAYER_ID, Entity, EntityId, Kind
from aidm.state.model import Game, ScenarioMeta, WorldPayload, WorldState
from aidm.turn.context import ANSWERED_BY_OPTION, render_director, render_narrator

DESCRIPTION = "She writes in a compact cipher."
WHEN_REACHED = "Her missing folio points toward the vault."
SHEET: dict[str, JsonValue] = {"concept": "A Cautious Scribe", "skills": ["Reads a Faded Hand"]}


def _with_detail(held: Game, entity_id: EntityId) -> Game:
    entity = held.world.require_kind(entity_id, "actor")
    detailed = updated(entity, description=DESCRIPTION, when_reached=WHEN_REACHED)
    return with_entity(held, detailed)


def _entity(entity_id: str, kind: Kind, name: str, brief: str, **fields: object) -> Entity:
    return Entity.model_validate(
        {"id": entity_id, "kind": kind, "name": name, "brief": brief} | fields
    )


def state() -> Game:
    entities = (
        _entity("study", "location", "Study", "A small room.", known=True),
        _entity("player", "actor", "Kael", "A hunter.", known=True, parent_id="study"),
        _entity("hidden-actor", "actor", "The Secret", "Unrevealed canon.", parent_id="study"),
        _entity("mara", "actor", "Mara", "A known scribe.", known=True, parent_id="study"),
        _entity("lantern", "item", "a lantern", "A dented light.", known=True, parent_id=PLAYER_ID),
        _entity("ledger", "item", "a ledger", "Mara's notes.", known=True, parent_id="mara"),
    )
    held = Game(
        scenario_id="whispering-vault",
        character_id="kael",
        scenario=ScenarioMeta(title="Test", premise="Test"),
        engine=LONER3E,
        packs=("srd",),
        payload=WorldPayload(
            player_id=PLAYER_ID,
            world=WorldState(
                entities={entity.id: entity for entity in entities},
                mechanics={"sheets": {"player": SHEET, "mara": SHEET, "hidden-actor": SHEET}},
            ),
        ),
        turn_facts=(),
    )
    return held.committed()


def _engine() -> Engine:
    return ENGINES_BUILT[LONER3E]


def _directed(held: Game, prompt: str, *, resumed: str = "") -> str:
    return render_director(
        _engine().views(held).director.sections,
        held.scenario,
        prompt,
        resumed=resumed,
    )


def test_the_narrators_view_has_no_field_that_could_hold_unrevealed_canon() -> None:
    held = _with_detail(state(), EntityId("mara"))
    scene = _engine().scene(held)

    narrator = _engine().views(held).narrator

    assert set(NarratorView.model_fields) == {
        "key",
        "label",
        "summary",
        "sections",
        "prompts",
        "art_prompt",
        "subjects",
        "speakers",
    }
    dumped = str(narrator.model_dump())
    assert "The Secret" not in dumped
    assert WHEN_REACHED not in dumped
    assert WHEN_REACHED in str(scene.model_dump())


def test_a_placement_never_names_an_entity_the_player_has_not_met() -> None:
    held = state()
    ledger = held.world.require_kind(EntityId("ledger"), "item")
    held = with_entity(held, updated(ledger, parent_id="hidden-actor"))

    narrator = _engine().views(held).narrator

    assert "held by The Secret" in _directed(held, "I look around.")
    assert "The Secret" not in str(narrator.sections)


def test_the_director_is_shown_authored_detail() -> None:
    held = _with_detail(state(), EntityId("mara"))

    director = _directed(held, "I look around.")

    assert "Kael[player]" in director
    assert "a lantern[lantern] — A dented light." in director
    assert "a ledger[ledger] (item) — held by Mara" in director
    assert "The Secret[hidden-actor]" in director
    assert "luck: 6/6" in director
    assert f"detail: {DESCRIPTION}" in director
    assert f"when reached: {WHEN_REACHED}" in director


def test_narrator_prompt_names_only_ids_of_entities_the_player_has_met() -> None:
    held = state()

    prompt = render_narrator(
        _engine().views(held).narrator,
        held.scenario,
        evidence="- the map was found",
        prompt="What does Mara say?",
    )

    assert "luck: 6/6" in prompt
    assert "The Secret" not in prompt
    # The Narrator names an id only in `speaker_id`; every id it is shown belongs to someone met.
    assert "Mara[mara]" in prompt
    assert "hidden-actor" not in prompt


def test_a_chosen_option_is_not_shown_as_the_players_own_words() -> None:
    resumed = "asked: A hit is coming.\nthe player chose: Take the hit\n- the hit lands in full"

    director = _directed(state(), "Take the hit", resumed=resumed)

    assert director.count("Take the hit") == 1
    assert director.endswith(f"PLAYER ACTION:\n{ANSWERED_BY_OPTION}")


def test_the_engines_own_describer_reads_the_blob_once() -> None:
    engine, held = game(LONER3E)
    assert "concept:" in str(engine.scene(held).sections)
