from pathlib import Path

import pytest

from src.tests.helpers.pytest_utils import testutils


@pytest.mark.parametrize(
    "indirect_fixture, expected",
    [
        (
            "test_out_chanur_txt",
            [
                "Chanur Series/01 - Pride Of Chanur",
                "Chanur Series/02 - Chanur's Venture",
                "Chanur Series/03 - Kif Strikes Back",
                "Chanur Series/04 - Chanur's Homecoming",
                "Chanur Series/05 - Chanur's Legacy",
            ],
        ),
        (
            "test_out_tower_txt",
            ["tower_treasure__flat_mp3"],
        ),
    ],
    indirect=["indirect_fixture"],
)
def test_get_all_processed_books(indirect_fixture, expected):
    assert (
        testutils.get_all_processed_books(
            indirect_fixture, root_dir=Path("/auto-m4b/src/tests/tmp/inbox")
        )
        == expected
    )
