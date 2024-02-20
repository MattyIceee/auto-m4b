from pathlib import Path

import pytest

from src.tests.conftest import TESTS_TMP_ROOT

INBOX = TESTS_TMP_ROOT / "inbox"

expect_flat_dirs = [
    INBOX / "test_book_1",
    INBOX / "test_book_2",
    INBOX / "test_book_3",
    INBOX / "test_book_4",
]

expect_deep_dirs = [
    INBOX / "test_book_multi_disc",
    INBOX / "test_book_multi_series",
    INBOX / "test_book_nested",
]

expect_all_dirs = expect_flat_dirs + expect_deep_dirs

expect_only_standalone_files = [
    INBOX / "test_book_standalone_file_a.mp3",
    INBOX / "test_book_standalone_file_b.mp3",
]

expect_all = expect_all_dirs + expect_only_standalone_files


@pytest.mark.parametrize(
    "path, mindepth, maxdepth, expected",
    [
        (INBOX, None, None, expect_all_dirs),
        (INBOX, 0, None, expect_all_dirs),
        (INBOX, None, 0, []),
        (INBOX, 0, 1, expect_flat_dirs),
        (INBOX, 1, 1, expect_flat_dirs),
        (INBOX, 1, 2, expect_all_dirs),
        (INBOX, 2, 2, expect_deep_dirs),
    ],
)
@pytest.mark.usefixtures("mock_inbox", "setup")
def test_find_root_dirs_with_audio_files(
    path: Path, mindepth: int, maxdepth: int, expected: list[Path]
):
    from src.lib.fs_utils import find_root_dirs_with_audio_files

    assert find_root_dirs_with_audio_files(path, mindepth, maxdepth) == expected
