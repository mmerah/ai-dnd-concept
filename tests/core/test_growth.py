from aidm.state.turn import GrowthRequest, screen_growth


def request(name: str) -> GrowthRequest:
    return GrowthRequest(kind="actor", name=name, brief="New canon.")


def test_growth_screening_rejects_duplicates_then_records_the_cap() -> None:
    screened = screen_growth(
        (
            request("mara"),
            request("Iven"),
            request("iven"),
            request("Nia"),
            request("Sol"),
        ),
        {"Mara"},
        maximum=2,
    )

    assert [held.name for held in screened.accepted] == ["Iven", "Nia"]
    assert [(held.request.name, held.reason) for held in screened.rejected] == [
        ("mara", "duplicate_name"),
        ("iven", "duplicate_name"),
        ("Sol", "over_cap"),
    ]
