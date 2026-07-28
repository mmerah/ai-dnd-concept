from collections.abc import Mapping, Sequence

from ..domain.models import Entity, EntityId, Frozen, GrowthRequest, RejectedGrowth


class Screened(Frozen):
    accepted: list[GrowthRequest]
    rejected: list[RejectedGrowth]


def screen(
    requests: Sequence[GrowthRequest], entities: Mapping[EntityId, Entity], cap: int
) -> Screened:
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
