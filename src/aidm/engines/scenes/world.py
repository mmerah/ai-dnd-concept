from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import (
    CheckedEntityId,
    EntityId,
    Mutable,
    Refusal,
    Slug,
    parse,
    require_unique,
)
from aidm.core.facts import Fact
from aidm.core.play import Exchange, SceneRecord
from aidm.core.views import Panel, PanelRow, Sections, lines_of
from aidm.engines.base import IS_DEAD, UNKNOWN_ID, Person, Thing, World, check_filing, sentence
from aidm.engines.scenes.drafts import NextDraft, SceneDraft

SCENE_SETTLED = Fact(
    kind="scene_settled",
    trace=(
        "this scene is settled. Bring it to a close, then ask the player what they want to "
        "pursue next — in the fiction, naming what the scene left open, never as a list of "
        "choices. They may also stay and keep playing here, so ask; do not push them out"
    ),
    told=True,
)

SCENE_LEFT = Fact(
    kind="scene_left",
    trace=(
        "the player has left this place; close the scene on their going and describe nothing "
        "of where they arrive: the page carries them on"
    ),
    told=True,
)


class SceneRun(Mutable):
    # Names the art cache entry, so returning to a place reuses its picture.
    place: Slug
    title: str
    # The player reads it; settling it ends the scene.
    question: str = Field(min_length=1)
    situation: str = Field(min_length=1)
    here: list[CheckedEntityId] = Field(default_factory=list)
    exchanges: list[Exchange] = Field(default_factory=list)
    # None while open; "" once settled here; the player's words when they left for elsewhere
    left: str | None = None
    recap: str = ""  # written when the player left


class SceneCanon[C: Person](Mutable):
    """A scenario as authored: its opening scene and cast, with no player in it yet."""

    cast: dict[EntityId, C] = Field(default_factory=dict)
    opening: SceneRun
    source: str = ""
    arc: str = ""

    @model_validator(mode="after")
    def _playable_canon(self) -> Self:
        check_filing(self.cast)
        check_named(self.opening.here, self.cast)
        opening = self.opening
        if opening.exchanges or opening.left is not None or opening.recap:
            raise ValueError("an opening with play in it")
        return self


class SceneWorld[C: Person, P: Person](World[P]):
    """The world as a sequence of scenes: the player is a sheet, never a cast entry."""

    runs: list[SceneRun] = Field(min_length=1)
    cast: dict[EntityId, C] = Field(default_factory=dict)
    party: list[EntityId] = Field(default_factory=list)
    arc: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_filing(self.cast)
        check_named(self.run.here, self.cast)
        if not self.player.known:
            raise ValueError("the player is unknown to themselves")
        if self.player.id in self.cast:
            raise ValueError("the player is in the cast")
        if self.player.id in self.run.here:
            raise ValueError("the player is in every scene and is never listed in it")
        if self.player.id in self.party:
            raise ValueError("the player cannot travel with themselves")
        require_unique("party", self.party)
        for member_id in self.party:
            if member_id not in self.cast:
                raise ValueError(f"{member_id!r} travels with the player but is not in the cast")
            if not self.cast[member_id].alive:
                raise ValueError(f"{member_id!r} is dead and cannot travel with the player")
        if left := sorted(set(self.party) - set(self.run.here)):
            raise ValueError(f"the party is in every scene; {left} are not in this one")
        return self

    @classmethod
    def begin(cls, canon: SceneCanon[C], player: P) -> Self:
        """The player is added by code and never authored, so no scenario can claim their id."""
        return parse(
            cls,
            {
                "cast": canon.cast,
                "player": player,
                "runs": [canon.opening],
                "source": canon.source,
                "arc": canon.arc,
            },
        )

    @property
    def run(self) -> SceneRun:
        return self.runs[-1]

    def present(self) -> list[EntityId]:
        return [entity_id for entity_id in self.run.here if self.cast[entity_id].known]

    def hidden(self) -> list[EntityId]:
        return [entity_id for entity_id in self.run.here if not self.cast[entity_id].known]

    def record(self, exchange: Exchange) -> None:
        self.run.exchanges.append(exchange)

    def records(self) -> tuple[SceneRecord, ...]:
        return tuple(
            SceneRecord(
                title=run.title,
                focus=run.question,
                recap=run.recap,
                exchanges=tuple(run.exchanges),
            )
            for run in self.runs
        )

    def last_seen(self, entity_id: EntityId) -> str:
        """The prompt's own line; scanning back keeps what the story dropped from being lost."""
        for run in reversed(self.runs):
            if entity_id in run.here:
                return f"last seen in: {run.title}"
        return ""

    def members(self) -> list[C]:
        return [self.cast[member_id] for member_id in self.party]

    def require(self, entity_id: EntityId) -> C | P:
        if entity_id == self.player.id:
            return self.player
        entity = self.cast.get(entity_id)
        if entity is None:
            raise Refusal(UNKNOWN_ID.format(entity_id=entity_id))
        return entity

    def require_here(self, entity_id: EntityId, *, alive: bool = False) -> C | P:
        entity = self.require(entity_id)
        if alive and not entity.alive:
            raise Refusal(IS_DEAD.format(name=entity.name))
        if entity.id == self.player.id:
            return entity
        if entity.id not in self.run.here or not entity.known:
            raise Refusal(
                f"{entity.name} is not here with the player. "
                "Bring them here first, or act on who is here."
            )
        return entity

    def here(self) -> Iterator[C | P]:
        yield self.player
        for entity_id in self.present():
            yield self.cast[entity_id]

    def here_lines(self) -> str:
        return lines_of(member.line() for member in self.here() if member.id != self.player.id)

    def hidden_lines(self) -> str:
        return lines_of(self.require(entity_id).line() for entity_id in self.hidden())

    def cast_lines(self) -> str:
        """The worldsmith must know who is met, and who follows the player out of the scene."""
        lines = [self.player.line()]
        for entry in self.cast.values():
            where = (
                "travels with the player" if entry.id in self.party else self.last_seen(entry.id)
            )
            lines.append(
                entry.line(detail=f"{entry.met_label}; {where}" if where else entry.met_label)
            )
        return "\n".join(lines)

    def reveal_hidden(self, entity_id: EntityId) -> list[Fact]:
        """The discovery itself, distinct from what `enter` tells about someone walking in."""
        entity = self.require(entity_id)
        if entity_id not in self.run.here or entity.known:
            raise Refusal(f"{entity_id!r} is not hidden here")
        return entity.reveal(card=sentence(f"{entity.name} discovered"))

    def enter(self, entity_id: EntityId) -> list[Fact]:
        if entity_id == self.player.id:
            raise Refusal("the player is in every scene; move the story on instead")
        entity = self.require(entity_id)
        if entity.id in self.run.here:
            raise Refusal(f"{entity.name} is already here")
        self.run.here.append(entity.id)
        trace = f"{entity.label} arrives"
        return [
            *entity.reveal(),
            entity.fact("entity_entered", trace, card=f"{entity.name} arrives"),
        ]

    def leave(self, entity_id: EntityId) -> list[Fact]:
        if entity_id == self.player.id:
            raise Refusal("the player is in every scene; move the story on instead")
        entity = self.require_here(entity_id)
        if entity.id in self.party:
            raise Refusal(f"{entity.name} travels with the player and leaves through `leave_party`")
        self.run.here.remove(entity.id)
        return [entity.fact("entity_left", f"{entity.label} leaves", card=f"{entity.name} leaves")]

    def kill(self, entity_id: EntityId) -> list[Fact]:
        entity = self.require_here(entity_id)
        if not entity.alive:
            raise Refusal(f"{entity.name} is already dead")
        facts = entity.reveal()
        if entity.id in self.party:
            self.party.remove(entity.id)
        entity.alive = False
        card = "You are dead" if entity.id == self.player.id else f"{entity.name} is dead"
        facts.append(entity.fact("actor_killed", f"{entity.label} is dead", card=card))
        return facts

    def join_party(self, entity_id: EntityId) -> list[Fact]:
        entity = self.require_here(entity_id, alive=True)
        if entity.id in self.party:
            raise Refusal(f"{entity.name} already travels with the player")
        facts = entity.reveal()
        self.party.append(entity.id)
        trace = f"{entity.tag} travels with the player"
        facts.append(entity.fact("party_joined", trace, card=f"{entity.name} joins your party"))
        return facts

    def leave_party(self, entity_id: EntityId) -> list[Fact]:
        entity = self.require(entity_id)
        if entity.id not in self.party:
            raise Refusal(f"{entity.name} does not travel with the player")
        self.party.remove(entity.id)
        trace = f"{entity.tag} no longer travels with the player"
        return [entity.fact("party_left", trace, card=f"{entity.name} leaves your party")]

    def settle(self, pursuit: str) -> list[Fact]:
        self._require_open()
        self.run.left = pursuit
        return [SCENE_LEFT if pursuit else SCENE_SETTLED]

    def complicate(self, brief: str) -> Fact:
        self._require_open()
        return Fact(
            kind="complication_asked",
            told=False,
            trace=f"the worldsmith writes the complication once this turn ends: {brief}. "
            "Nothing more lands this turn; stop and exit",
        )

    def _require_open(self) -> None:
        if self.run.left is not None:
            raise Refusal("this scene is already settled; the player has the way on")

    def merged_cast(self, cast: Mapping[EntityId, C]) -> dict[EntityId, C]:
        return {
            **self.cast,
            **{
                entity_id: filed.model_copy(update={"brief": entry.brief})
                if (filed := self.cast.get(entity_id)) is not None
                else entry
                for entity_id, entry in cast.items()
            },
        }

    def apply_scene(self, draft: SceneDraft[C]) -> None:
        self.cast = self.merged_cast(draft.cast)
        everyone: Mapping[EntityId, Thing] = {self.player.id: self.player, **self.cast}
        present = resolve_ids(draft.present, everyone, "present")
        hidden = resolve_ids(draft.hidden, everyone, "hidden")
        for entity_id in present:
            self.cast[entity_id].known = True
        if isinstance(draft, NextDraft):
            self.run.recap = draft.recap
        self.arc = draft.arc or self.arc
        self.runs.append(run_of(draft, [*self.party, *present, *hidden]))

    def party_rows(self) -> Sections:
        members = self.members()
        if not members:
            return ()
        listed = "\n".join(f"- {m.tag}" for m in members)
        return (("THE PARTY (led by the player)", listed),)

    def party_panel(self) -> tuple[Panel, ...]:
        members = self.members()
        if not members:
            return ()
        rows = tuple(PanelRow(label=m.name, detail=m.brief, icon_id=m.id) for m in members)
        return (Panel(title="Party", rows=rows),)

    def scene_rows(self) -> tuple[PanelRow, ...]:
        rows = [PanelRow(label=self.run.question, detail="")]
        if (left := self.run.left) is not None:
            if left:
                rows.append(PanelRow(label="Go on", detail=left, intent=left))
            else:
                rows.append(
                    PanelRow(
                        label="Way on", detail="Keep playing, or name where you go and move on."
                    )
                )
        return tuple(rows)


def check_named(here: Sequence[EntityId], cast: Mapping[EntityId, Thing]) -> None:
    require_unique("ids in the scene", here)
    for who in here:
        if who not in cast:
            raise Refusal(f"scene names {who!r}, who is not in the cast")


def resolved_id(wanted: str, cast: Mapping[EntityId, Thing]) -> EntityId | None:
    """Ids are the worldsmith's failure mode: an unknown one matches a cast name before refusal."""
    if wanted in cast:
        return EntityId(wanted)
    matches = [entry.id for entry in cast.values() if entry.name.casefold() == wanted.casefold()]
    return EntityId(matches[0]) if len(matches) == 1 else None


def resolve_ids(
    wanted: Iterable[str], cast: Mapping[EntityId, Thing], where: str
) -> list[EntityId]:
    found: list[EntityId] = []
    for name in wanted:
        matched = resolved_id(name, cast)
        if matched is None:
            raise Refusal(f"the scene lists {name!r} as {where}, and no such id or name exists")
        if matched not in found:
            found.append(matched)
    return found


def run_of[C: Person](draft: SceneDraft[C], here: list[EntityId]) -> SceneRun:
    """Free: it builds a `SceneRun` from a draft the run does not own."""
    return SceneRun(
        place=draft.place,
        title=draft.title,
        question=draft.question,
        situation=draft.situation,
        here=here,
    )
