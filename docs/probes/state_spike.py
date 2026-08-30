"""Probe: SceneState[S] round-trip. 16 checks, all passing; basedpyright keeps full types.
Reference only — PLAN.md phase 2 copies from this."""
def _expect(fn, needle):
    try:
        fn()
    except Exception as e:
        assert needle in str(e), f"expected {needle!r} in: {e}"
        return
    raise AssertionError("no error raised")

"""Spike: SceneState[S] generic + discriminated sheet union + discriminated payload,
round-tripped through the save envelope. Assert-based; run it, it either passes or raises."""
import json
from typing import Annotated, Literal, Self
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
class Mutable(BaseModel):
    model_config = ConfigDict(extra="forbid")

# ---------- the engine's sheet union (plain aliases: a `type` alias defeats discrimination) ----------
class ActorSheet(Mutable):
    kind: Literal["actor"] = "actor"
    concept: str
    skills: tuple[str, ...] = ()
    luck: int = Field(default=6, ge=0, le=6)

class ItemSheet(Mutable):
    kind: Literal["item"] = "item"
    die: int = Field(ge=4, le=12)
    broken: bool = False

class ShipSheet(Mutable):                       # the 24XX case, to prove a third arm fits
    kind: Literal["ship"] = "ship"
    upgrades: tuple[str, ...] = ()

LonerSheet = Annotated[ActorSheet | ItemSheet, Field(discriminator="kind")]
XXSheet = Annotated[ActorSheet | ItemSheet | ShipSheet, Field(discriminator="kind")]

# ---------- the kit, generic over the engine's sheet union ----------
class Trait(Frozen):
    id: str
    name: str

class Entity[S](Mutable):
    id: str
    kind: Literal["actor", "item", "prop"]
    name: str
    brief: str = ""
    known: bool = False
    traits: list[Trait] = Field(default_factory=list)
    carried_by: str | None = None
    sheet: S | None = None

class Scene(Frozen):
    id: str
    place: str
    title: str
    situation: str = Field(min_length=10)
    present: tuple[str, ...] = ()
    hidden: tuple[str, ...] = ()
    note: str = ""

class Thread(Mutable):
    id: str
    title: str
    status: Literal["active", "resolved", "dormant"] = "active"
    note: str = ""

class SceneState[S](Mutable):
    cast: dict[str, Entity[S]] = Field(default_factory=dict)
    played: tuple[Scene, ...] = ()
    current: Scene
    threads: dict[str, Thread] = Field(default_factory=dict)
    companions: list[str] = Field(default_factory=list)
    player_id: str
    source: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        for key, one in self.cast.items():
            if key != one.id:
                raise ValueError(f"entity {one.id!r} filed under {key!r}")
        for who in (*self.current.present, *self.current.hidden):
            if who not in self.cast:
                raise ValueError(f"scene names {who!r}, not in the cast")
        if self.player_id not in self.cast:
            raise ValueError("the player is not in the cast")
        return self

# ---------- engine states, each tagged for the payload discriminator ----------
class LonerState(Mutable):
    engine: Literal["loner3e"] = "loner3e"
    world: SceneState[LonerSheet]
    twist_pack: str | None = None

class XXState(Mutable):
    engine: Literal["twentyfourxx"] = "twentyfourxx"
    world: SceneState[XXSheet]
    credits: int = 0

Payload = Annotated[LonerState | XXState, Field(discriminator="engine")]

# ---------- the save envelope ----------
class Save(Mutable):
    scenario_id: str
    character_id: str
    turn: int = Field(default=0, ge=0)
    packs: tuple[str, ...] = Field(min_length=1)
    payload: Payload

SAVE = TypeAdapter(Save)

# ================================ the spike ================================
def build() -> Save:
    cast: dict[str, Entity[LonerSheet]] = {
        "player": Entity[LonerSheet](id="player", kind="actor", name="Kael", known=True,
            traits=[Trait(id="soaked", name="Soaked")],
            sheet=ActorSheet(concept="courier", skills=("read weather",), luck=4)),
        "gideon": Entity[LonerSheet](id="gideon", kind="actor", name="Gideon", known=True,
            sheet=ActorSheet(concept="ferryman", luck=5)),
        "lantern": Entity[LonerSheet](id="lantern", kind="item", name="a lantern",
            known=True, carried_by="player", sheet=ItemSheet(die=8)),
        "bell-rope": Entity[LonerSheet](id="bell-rope", kind="prop", name="the bell rope",
            known=True, sheet=None),
        "wren": Entity[LonerSheet](id="wren", kind="actor", name="Wren",
            sheet=ActorSheet(concept="the one the water kept")),
    }
    scene = Scene(id="chapel-1", place="the-chapel", title="The Chapel at Last Light",
                  situation="Water to the knee and the bell above.",
                  present=("player", "gideon", "lantern", "bell-rope"), hidden=("wren",))
    world = SceneState[LonerSheet](cast=cast, current=scene, player_id="player",
        threads={"the-bell": Thread(id="the-bell", title="Who rings the bell")},
        companions=["gideon"], source="THE DROWNED ROAD ...")
    return Save(scenario_id="drowned-road", character_id="kael", turn=7,
                packs=("grim",), payload=LonerState(world=world, twist_pack="grim"))

def check(name: str, fn) -> None:
    try:
        fn(); print(f"  PASS  {name}")
    except Exception as e:
        print(f"  FAIL  {name}: {type(e).__name__}: {str(e).splitlines()[0][:120]}"); raise

print("=== 1. round-trip ===")
save = build()
raw = save.model_dump_json(indent=1)
back = SAVE.validate_json(raw)
check("json round-trip is byte-identical", lambda: (_ for _ in ()).throw(AssertionError("x"))
      if back.model_dump_json(indent=1) != raw else None)
check("payload narrows to LonerState", lambda: isinstance(back.payload, LonerState) or 1/0)
check("actor sheet survives typed", lambda:
      isinstance(back.payload.world.cast["player"].sheet, ActorSheet) or 1/0)
check("item sheet survives typed", lambda:
      isinstance(back.payload.world.cast["lantern"].sheet, ItemSheet) or 1/0)
check("prop keeps a null sheet", lambda:
      back.payload.world.cast["bell-rope"].sheet is None or 1/0)
check("luck value preserved", lambda: back.payload.world.cast["player"].sheet.luck == 4 or 1/0)

print("\n=== 2. the discriminators actually discriminate ===")
def wrong_sheet_kind():
    bad = json.loads(raw)
    bad["payload"]["world"]["cast"]["player"]["sheet"]["kind"] = "ship"
    SAVE.validate_python(bad)
check("a sheet kind the engine's union lacks is rejected",
      lambda: _expect(wrong_sheet_kind, "ship"))
def unknown_engine():
    bad = json.loads(raw); bad["payload"]["engine"] = "breathless"
    SAVE.validate_python(bad)
check("an unknown engine tag is rejected", lambda: _expect(unknown_engine, "breathless"))
def bad_die():
    bad = json.loads(raw)
    bad["payload"]["world"]["cast"]["lantern"]["sheet"]["die"] = 20
    SAVE.validate_python(bad)
check("a sheet field out of range is rejected", lambda: _expect(bad_die, "12"))
def stray_id():
    bad = json.loads(raw); bad["payload"]["world"]["current"]["hidden"] = ["nobody"]
    SAVE.validate_python(bad)
check("the kit validator still runs through the generic", lambda: _expect(stray_id, "nobody"))
def extra_field():
    bad = json.loads(raw); bad["payload"]["world"]["cast"]["player"]["mood"] = "grim"
    SAVE.validate_python(bad)
check("extra=forbid holds inside the generic", lambda: _expect(extra_field, "mood"))

print("\n=== 3. a second engine coexists ===")
xx = Save(scenario_id="skiff", character_id="kael", turn=1, packs=("void",),
    payload=XXState(credits=3, world=SceneState[XXSheet](
        cast={"player": Entity[XXSheet](id="player", kind="actor", name="Vell", known=True,
                  sheet=ActorSheet(concept="pilot")),
              "skiff": Entity[XXSheet](id="skiff", kind="item", name="the skiff", known=True,
                  sheet=ShipSheet(upgrades=("long-range scanner",)))},
        current=Scene(id="dock-1", place="the-dock", title="Dock 9",
                      situation="Rain on the gantry.", present=("player", "skiff")),
        player_id="player")))
xx_raw = xx.model_dump_json(indent=1)
check("second engine round-trips", lambda:
      SAVE.validate_json(xx_raw).model_dump_json(indent=1) == xx_raw or 1/0)
check("ship sheet only legal in the 24XX union", lambda:
      isinstance(SAVE.validate_json(xx_raw).payload.world.cast["skiff"].sheet, ShipSheet) or 1/0)
check("one adapter routes both by tag", lambda:
      isinstance(SAVE.validate_json(xx_raw).payload, XXState)
      and isinstance(SAVE.validate_json(raw).payload, LonerState) or 1/0)

print("\n=== 4. schemas generate (tools need this) ===")
s1 = json.dumps(Save.model_json_schema(), separators=(",", ":"))
s2 = json.dumps(SceneState[LonerSheet].model_json_schema(), separators=(",", ":"))
check("save schema generates", lambda: len(s1) > 100 or 1/0)
check("generic kit schema generates", lambda: len(s2) > 100 or 1/0)
print(f"  save schema {len(s1)} B · SceneState[LonerSheet] schema {len(s2)} B")

print("\n=== 5. stale-save policy still bites ===")
def old_shape():
    bad = json.loads(raw); del bad["payload"]["world"]["player_id"]
    SAVE.validate_python(bad)
check("a save missing a field is invalid, not migrated", lambda: _expect(old_shape, "player_id"))
print("\nALL CHECKS PASSED")
