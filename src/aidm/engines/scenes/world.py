from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import (
    Mutable,
    Refusal,
    Slug,
    check_unique,
    parse,
)
from aidm.core.facts import Fact
from aidm.core.play import Exchange, SceneRecord
from aidm.core.prompt import lines_of, sentence
from aidm.core.views import Panel, PanelRow
from aidm.engines.base import IS_DEAD, UNKNOWN_ID, Person, Thing, World, check_filing
from aidm.engines.scenes.tools import NextDraft, SceneDraft

WAY_OFFERED = Fact(
    trace=(
        "this scene offers a way on. Ask the player what they want to pursue next — in the "
        "fiction, naming what the scene left open, never as a list of choices. They may also "
        "stay and keep playing here, so ask; do not push them out"
    ),
    told=True,
)

SCENE_LEFT = Fact(
    trace=(
        "the player has left this place; close the scene on their going and describe nothing "
        "of where they arrive: the crossing is written next"
    ),
    told=True,
)


class SceneRun(Mutable):
    # Names the art cache entry, so returning to a place reuses its picture.
    place: Slug
    title: str
    focus: str = ""
    situation: str = Field(min_length=1)
    here: list[Slug] = Field(default_factory=list)
    exchanges: list[Exchange] = Field(default_factory=list)
    offered: bool = False
    recap: str = ""


class SceneWorld[C: Person](World[C, C]):
    runs: list[SceneRun] = Field(min_length=1)
    cast: dict[Slug, C] = Field(default_factory=dict)
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
        check_unique("party", self.party)
        for member_id in self.party:
            if member_id not in self.cast or not self.cast[member_id].known:
                raise ValueError(
                    f"{member_id!r} travels with the player but is not met in the cast"
                )
            if not self.cast[member_id].alive:
                raise ValueError(f"{member_id!r} is dead and cannot travel with the player")
        if left := sorted(set(self.party) - set(self.run.here)):
            raise ValueError(f"the party is in every scene; {left} are not in this one")
        return self

    @classmethod
    def opening(cls, draft: SceneDraft[C], player: C, source: str) -> Self:
        """The player is added by code and never authored, so no scenario can claim their id."""
        cast, run = settled(draft, player, dict(draft.cast), ())
        return parse(
            cls, {"player": player, "cast": cast, "runs": [run], "arc": draft.arc, "source": source}
        )

    @property
    def run(self) -> SceneRun:
        return self.runs[-1]

    def present(self) -> list[Slug]:
        return [entity_id for entity_id in self.run.here if self.cast[entity_id].known]

    def hidden(self) -> list[Slug]:
        return [entity_id for entity_id in self.run.here if not self.cast[entity_id].known]

    def record(self, exchange: Exchange) -> None:
        self.run.exchanges.append(exchange)

    def records(self) -> tuple[SceneRecord, ...]:
        return tuple(
            SceneRecord(
                title=run.title,
                focus=run.focus,
                recap=run.recap,
                exchanges=tuple(run.exchanges),
            )
            for run in self.runs
        )

    def last_seen(self, entity_id: Slug) -> str:
        """Scans every run so an entity the story dropped is still placed."""
        for run in reversed(self.runs):
            if entity_id in run.here:
                return f"last seen in: {run.title}"
        return ""

    def members(self) -> list[C]:
        return [self.cast[member_id] for member_id in self.party]

    def require(self, entity_id: Slug) -> C:
        if entity_id == self.player.id:
            return self.player
        entity = self.cast.get(entity_id)
        if entity is None:
            raise Refusal(UNKNOWN_ID.format(entity_id=entity_id))
        return entity

    def require_here(self, entity_id: Slug, *, alive: bool = False) -> C:
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

    def here(self) -> Iterator[C]:
        yield self.player
        for entity_id in self.present():
            yield self.cast[entity_id]

    def require_member_here(self, entity_id: Slug) -> C:
        return self.require_here(entity_id, alive=True)

    def others(self) -> Iterator[C]:
        return (self.cast[entity_id] for entity_id in self.present() if entity_id not in self.party)

    def here_lines(self) -> str:
        return lines_of(other.line() for other in self.others())

    def hidden_lines(self) -> str:
        return lines_of(self.require(entity_id).line() for entity_id in self.hidden())

    def scene_lines(self) -> str:
        run = self.run
        present = ", ".join(self.cast[entity_id].tag for entity_id in self.present())
        hidden = ", ".join(self.cast[entity_id].tag for entity_id in self.hidden())
        return (
            f"{run.title} [{run.place}]\n{run.situation}\n"
            f"present: {present or '(nobody)'}\nhidden: {hidden or '(nothing)'}"
        )

    def cast_lines(self) -> str:
        lines = [self.player.line()]
        for entry in self.cast.values():
            where = (
                "travels with the player" if entry.id in self.party else self.last_seen(entry.id)
            )
            lines.append(
                entry.line(detail=f"{entry.met_label}; {where}" if where else entry.met_label)
            )
        return "\n".join(lines)

    def reveal_hidden(self, entity_id: Slug) -> list[Fact]:
        """The discovery itself, distinct from what `enter` tells about someone walking in."""
        entity = self.require(entity_id)
        if entity_id not in self.run.here or entity.known:
            raise Refusal(f"{entity_id!r} is not hidden here")
        return entity.reveal(card=sentence(f"{entity.name} discovered"))

    def enter(self, entity_id: Slug) -> list[Fact]:
        if entity_id == self.player.id:
            raise Refusal("the player is in every scene; move the story on instead")
        entity = self.require(entity_id)
        if entity.id in self.run.here:
            raise Refusal(f"{entity.name} is already here")
        self.run.here.append(entity.id)
        trace = f"{entity.mention} arrives"
        return [
            *entity.reveal(),
            entity.fact(trace, card=f"{entity.name} arrives"),
        ]

    def leave(self, entity_id: Slug) -> list[Fact]:
        if entity_id == self.player.id:
            raise Refusal("the player is in every scene; move the story on instead")
        entity = self.require_here(entity_id)
        if entity.id in self.party:
            raise Refusal(f"{entity.name} travels with the player and leaves through `leave_party`")
        self.run.here.remove(entity.id)
        card = f"{entity.name} leaves"
        return [entity.fact(f"{entity.mention} leaves", card=card)]

    def kill(self, entity_id: Slug) -> list[Fact]:
        entity = self.require_here(entity_id)
        if not entity.alive:
            raise Refusal(f"{entity.name} is already dead")
        facts = entity.reveal()
        if entity.id in self.party:
            self.party.remove(entity.id)
        entity.alive = False
        card = "You are dead" if entity.id == self.player.id else f"{entity.name} is dead"
        facts.append(entity.fact(f"{entity.mention} is dead", card=card))
        return facts

    def join_party(self, entity_id: Slug) -> list[Fact]:
        return self.join(self.require_here(entity_id, alive=True))

    def leave_party(self, entity_id: Slug) -> list[Fact]:
        return self.part(self.require(entity_id))

    def offer(self) -> list[Fact]:
        if self.run.offered:
            raise Refusal("this scene already offers the way on; play on, or send them off")
        self.run.offered = True
        return [WAY_OFFERED]

    def merged_cast(self, cast: Mapping[Slug, C]) -> dict[Slug, C]:
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
        self.cast, run = settled(draft, self.player, self.merged_cast(draft.cast), self.party)
        if isinstance(draft, NextDraft):
            self.run.recap = draft.recap
        self.arc = draft.arc or self.arc
        self.runs.append(run)

    def scene_panel(self) -> tuple[Panel, ...]:
        if not self.run.focus:
            return ()
        return (Panel(title="This scene", rows=(PanelRow(label=self.run.focus, detail=""),)),)


def settled[C: Person](
    draft: SceneDraft[C], player: Person, cast: dict[Slug, C], party: Sequence[Slug]
) -> tuple[dict[Slug, C], SceneRun]:
    """Free: it marks the present met and files the run, for a world that may not exist yet."""
    everyone: Mapping[Slug, Thing] = {player.id: player, **cast}
    present = _resolve_ids(draft.present, everyone, "present")
    hidden = _resolve_ids(draft.hidden, everyone, "hidden")
    for entity_id in present:
        cast[entity_id].known = True
    run = SceneRun(
        place=draft.place,
        title=draft.title,
        focus=draft.focus,
        situation=draft.situation,
        here=[*party, *present, *hidden],
    )
    return cast, run


def check_named(here: Sequence[Slug], cast: Mapping[Slug, Thing]) -> None:
    check_unique("ids in the scene", here)
    for who in here:
        if who not in cast:
            raise ValueError(f"scene names {who!r}, who is not in the cast")


def resolved_id(wanted: str, cast: Mapping[Slug, Thing]) -> Slug | None:
    """Ids are the worldsmith's failure mode: an unknown one matches a cast name before refusal."""
    if wanted in cast:
        return wanted
    matches = [entry.id for entry in cast.values() if entry.name.casefold() == wanted.casefold()]
    return matches[0] if len(matches) == 1 else None


def _resolve_ids(wanted: Iterable[str], cast: Mapping[Slug, Thing], where: str) -> list[Slug]:
    found: list[Slug] = []
    for name in wanted:
        matched = resolved_id(name, cast)
        if matched is None:
            raise Refusal(f"the scene lists {name!r} as {where}, and no such id or name exists")
        if matched not in found:
            found.append(matched)
    return found
