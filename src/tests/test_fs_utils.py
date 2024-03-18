import shutil
import time
from pathlib import Path

import pytest

from src.lib.audiobook import Audiobook
from src.lib.fs_utils import find_first_audio_file, find_next_audio_file
from src.tests.conftest import TEST_INBOX

expect_flat_dirs = [
    TEST_INBOX / "mock_book_1",
    TEST_INBOX / "mock_book_2",
    TEST_INBOX / "mock_book_3",
    TEST_INBOX / "mock_book_4",
]

expect_deep_dirs = [
    TEST_INBOX / "mock_book_multi_disc",
    TEST_INBOX / "mock_book_multi_series",
    TEST_INBOX / "mock_book_nested",
]

expect_all_dirs = expect_flat_dirs + expect_deep_dirs

expect_only_standalone_files = [
    TEST_INBOX / "mock_book_standalone_file_a.mp3",
    TEST_INBOX / "mock_book_standalone_file_b.mp3",
]

expect_all = expect_all_dirs + expect_only_standalone_files


@pytest.mark.parametrize(
    "path, mindepth, maxdepth, expected",
    [
        (TEST_INBOX, None, None, expect_all_dirs),
        (TEST_INBOX, 0, None, expect_all_dirs),
        (TEST_INBOX, None, 0, []),
        (TEST_INBOX, 0, 1, expect_flat_dirs),
        (TEST_INBOX, 1, 1, expect_flat_dirs),
        (TEST_INBOX, 1, 2, expect_all_dirs),
        (TEST_INBOX, 2, 2, expect_deep_dirs),
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


def test_folder_recently_modified():
    from src.lib.fs_utils import find_recently_modified_files_and_dirs

    (TEST_INBOX / "recently_modified_file.txt").unlink(missing_ok=True)
    time.sleep(2)
    assert find_recently_modified_files_and_dirs(TEST_INBOX, 1) == []

    # create a file
    time.sleep(0.5)
    (TEST_INBOX / "recently_modified_file.txt").touch()
    assert (
        find_recently_modified_files_and_dirs(TEST_INBOX, 5)[0][0]
        == TEST_INBOX / "recently_modified_file.txt"
    )
    # remove the file
    (TEST_INBOX / "recently_modified_file.txt").unlink()


def test_was_recently_modified():
    from src.lib.fs_utils import was_recently_modified

    nested_dir = TEST_INBOX / "test_was_recently_modified"
    shutil.rmtree(nested_dir, ignore_errors=True)
    nested_dir.mkdir(parents=True, exist_ok=True)

    time.sleep(1)
    (nested_dir / "recently_modified_file.txt").unlink(missing_ok=True)
    assert not was_recently_modified(TEST_INBOX, 1)

    # create a file
    (nested_dir / "recently_modified_file.txt").touch()
    assert was_recently_modified(TEST_INBOX, 1)
    # remove the file
    (nested_dir / "recently_modified_file.txt").unlink()
