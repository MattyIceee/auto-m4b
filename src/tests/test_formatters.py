import pytest

duration_tests = [
    (0, False, "-"),
    (0, True, "-"),
    (1, False, "00m:01s"),
    (1, True, "0h:00m:01s"),
    (59, False, "00m:59s"),
    (59, True, "0h:00m:59s"),
    (60, False, "01m:00s"),
    (60, True, "0h:01m:00s"),
    (61, False, "01m:01s"),
    (61, True, "0h:01m:01s"),
    (3599, False, "59m:59s"),
    (3599, True, "0h:59m:59s"),
    (3600, False, "1h:00m:00s"),
    (3601, False, "1h:00m:01s"),
    (3661, False, "1h:01m:01s"),
    (27733, False, "7h:42m:13s"),
    (27733, True, "7h:42m:13s"),
    (43199, False, "11h:59m:59s"),
    (43200, False, "12h:00m:00s"),
    (43201, False, "12h:00m:01s"),
]


@pytest.mark.parametrize(
    "input, always_hours, units, expected",
    [t for t in [(i, a, u, e) for i, a, e in duration_tests for u in [False, True]]],
)
def test_human_elapsed_time(input: int, always_hours: bool, units: bool, expected: str):
    from src.lib.formatters import format_duration

    expected_no_units = "".join([c for c in expected if c not in "hms"])
    assert format_duration(
        input, "human", always_show_hours=always_hours, show_units=units
    ) == (expected if units else expected_no_units)
