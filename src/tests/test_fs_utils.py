from pathlib import Path

import pytest

from src.lib.audiobook import Audiobook
from src.lib.fs_utils import find_first_audio_file, find_next_audio_file
from src.tests.conftest import TESTS_TMP_ROOT

INBOX = TESTS_TMP_ROOT / "inbox"

expect_flat_dirs = [
    INBOX / "mock_book_1",
    INBOX / "mock_book_2",
    INBOX / "mock_book_3",
    INBOX / "mock_book_4",
]

expect_deep_dirs = [
    INBOX / "mock_book_multi_disc",
    INBOX / "mock_book_multi_series",
    INBOX / "mock_book_nested",
]

expect_all_dirs = expect_flat_dirs + expect_deep_dirs

expect_only_standalone_files = [
    INBOX / "mock_book_standalone_file_a.mp3",
    INBOX / "mock_book_standalone_file_b.mp3",
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
    from src.lib.fs_utils import find_base_dirs_with_audio_files

    assert find_base_dirs_with_audio_files(path, mindepth, maxdepth) == expected


def test_find_first_audio_file(tower_treasure__flat_mp3: Audiobook):
    assert (
        find_first_audio_file(tower_treasure__flat_mp3.path)
        == tower_treasure__flat_mp3.path / "towertreasure4_01_dixon_64kb.mp3"
    )


def test_find_next_audio_file(tower_treasure__flat_mp3: Audiobook):
    first_audio_file = find_first_audio_file(tower_treasure__flat_mp3.path)
    assert (
        find_next_audio_file(first_audio_file)
        == tower_treasure__flat_mp3.path / "towertreasure4_02_dixon_64kb.mp3"
    )
