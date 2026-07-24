"""What the Maintainer asks to create, screened before the Creator runs. Pure: imports only
`domain`, does no I/O. Deciding what may be created is exactly the rule `engine/` exists for."""

from collections.abc import Mapping, Sequence

from ..domain.models import Entity, EntityId, Frozen, GrowthRequest, RejectedGrowth


class Screened(Frozen):
    """What survived screening, and what did not — every drop kept with its reason, because
    silently dropping a request in an app whose selling feature is the trace panel is a regression.

    A duplicate *name* is a visible pre-filter rejection here (the turn proceeds); a duplicate
    *id* is instead a hard `ValueError` inside the reducer. That asymmetry is intended: an id
    collision is a broken invariant, a name collision is a judgement call."""

    accepted: list[GrowthRequest]
    rejected: list[RejectedGrowth]


def screen(
    requests: Sequence[GrowthRequest], entities: Mapping[EntityId, Entity], cap: int
) -> Screened:
    """Reject a request whose name already exists, then cap the rest. Name checks are
    case-insensitive, because the Maintainer restates a name as the narration spelled it; a name
    repeated within one batch is likewise rejected, so the Creator never mints `elgin_2`."""
    seen = {e.name.casefold() for e in entities.values()}
    accepted: list[GrowthRequest] = []
    rejected: list[RejectedGrowth] = []
    for request in requests:
        folded = request.name.casefold()
        if folded in seen:
            rejected.append(RejectedGrowth(request=request, reason="duplicate_name"))
        elif len(accepted) >= cap:
            rejected.append(RejectedGrowth(request=request, reason="over_cap"))
        else:
            seen.add(folded)
            accepted.append(request)
    return Screened(accepted=accepted, rejected=rejected)
