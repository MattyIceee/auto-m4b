import random
import shutil
import time
from pathlib import Path

import pytest
from PIL import Image

from src.lib.audiobook import Audiobook
from src.lib.fs_utils import (
    find_book_audio_files,
    find_cover_art_file,
    find_first_audio_file,
    find_next_audio_file,
)
from src.lib.misc import isorted
from src.lib.typing import BookDirStructure
from src.tests.conftest import TEST_DIRS

flat_dir1 = TEST_DIRS.inbox / "mock_book_1"
flat_dir2 = TEST_DIRS.inbox / "mock_book_2"
flat_dir3 = TEST_DIRS.inbox / "mock_book_3"
flat_dir4 = TEST_DIRS.inbox / "mock_book_4"
expect_flat_dirs = [flat_dir1, flat_dir2, flat_dir3, flat_dir4]

mixed_dir = TEST_DIRS.inbox / "mock_book_mixed"

flat_nested_dir = TEST_DIRS.inbox / "mock_book_flat_nested"
multi_book_dir = TEST_DIRS.inbox / "mock_book_multi_book"
multi_disc_dir = TEST_DIRS.inbox / "mock_book_multi_disc"
multi_nested_dir = TEST_DIRS.inbox / "mock_book_multi_nested"
standalone_nested_dir = TEST_DIRS.inbox / "mock_book_standalone_nested"
expect_deep_dirs = [
    flat_nested_dir,
    multi_book_dir,
    multi_disc_dir,
    multi_nested_dir,
]

expect_all_dirs = isorted(
    expect_flat_dirs + [mixed_dir] + expect_deep_dirs + [standalone_nested_dir]
)

standalone_file1 = TEST_DIRS.inbox / "mock_book_standalone_file_a.mp3"
standalone_file2 = TEST_DIRS.inbox / "mock_book_standalone_file_b.mp3"
expect_only_standalone_files = [
    standalone_file1,
    standalone_file2,
    standalone_nested_dir,
]

expect_all = expect_all_dirs + expect_only_standalone_files


@pytest.mark.parametrize(
    "path, mindepth, maxdepth, expected",
    [
        # fmt: off
        (TEST_DIRS.inbox, None, None, expect_all_dirs),
        (TEST_DIRS.inbox, 0, None, expect_all_dirs),
        (TEST_DIRS.inbox, None, 0, []),
        (TEST_DIRS.inbox, 0, 0, []),
        (TEST_DIRS.inbox, 0, 1, expect_flat_dirs + [mixed_dir] + [standalone_nested_dir]),
        (TEST_DIRS.inbox, 1, 1, expect_flat_dirs + [mixed_dir] + [standalone_nested_dir]),
        (TEST_DIRS.inbox, 1, 2, expect_all_dirs),
        (TEST_DIRS.inbox, 2, 2, [mixed_dir] + expect_deep_dirs),
        # fmt: on
    ],
)
def test_find_root_dirs_with_audio_files(
    path: Path, mindepth: int, maxdepth: int, expected: list[Path], mock_inbox, setup
):
    from src.lib.fs_utils import find_base_dirs_with_audio_files

    assert find_base_dirs_with_audio_files(path, mindepth, maxdepth) == isorted(
        expected
    )


@pytest.mark.parametrize(
    "expected_structure, path",
    [
        *[("flat", d) for d in expect_flat_dirs],
        ("flat_nested", flat_nested_dir),
        (
            "multi_book",
            multi_book_dir,
        ),
        ("multi_disc", multi_disc_dir),
        ("multi_nested", multi_nested_dir),
        ("mixed", mixed_dir),
        ("file", standalone_file1),
        ("standalone", standalone_nested_dir),
        ("empty", TEST_DIRS.inbox / "empty_dir"),
    ],
)
def test_find_book_audio_files(
    expected_structure: BookDirStructure,
    path: Path,
    mock_inbox,
    setup,
):
    structure, _paths = find_book_audio_files(path)

    assert structure == expected_structure


@pytest.mark.parametrize(
    "test_path, predicted, expected",
    [
        (
            multi_book_dir,
            [
                "mock_book_multi_book - ch. 1.mp3",
                "mock_book_multi_book - ch. 2.mp3",
                "mock_book_multi_book - ch. 1.mp3",
                "mock_book_multi_book - ch. 2.mp3",
                "mock_book_multi_book - ch. 3.mp3",
                "mock_book_multi_book - ch. 4.mp3",
                "mock_book_multi_book - ch. 1.mp3",
                "mock_book_multi_book - ch. 2.mp3",
                "mock_book_multi_book - ch. 3.mp3",
            ],
            [
                "mock_book_multi_book - ch. 1.mp3",
                "mock_book_multi_book - ch. 2.mp3",
                "mock_book_multi_book - ch. 3.mp3",
                "mock_book_multi_book - ch. 4.mp3",
            ],
        ),
        (
            multi_disc_dir,
            [
                "mock_book_multi_disc1 - part_1.mp3",
                "mock_book_multi_disc1 - part_2.mp3",
                "mock_book_multi_disc2 - part_3.mp3",
                "mock_book_multi_disc2 - part_4.mp3",
                "mock_book_multi_disc3 - part_5.mp3",
                "mock_book_multi_disc3 - part_6.mp3",
                "mock_book_multi_disc4 - part_7.mp3",
                "mock_book_multi_disc4 - part_8.mp3",
            ],
            [
                "mock_book_multi_disc1 - part_1.mp3",
                "mock_book_multi_disc1 - part_2.mp3",
                "mock_book_multi_disc2 - part_3.mp3",
                "mock_book_multi_disc2 - part_4.mp3",
                "mock_book_multi_disc3 - part_5.mp3",
                "mock_book_multi_disc3 - part_6.mp3",
                "mock_book_multi_disc4 - part_7.mp3",
                "mock_book_multi_disc4 - part_8.mp3",
            ],
        ),
    ],
)
def test_flatten_files_in_dir(
    test_path: Path,
    expected: list[str],
    predicted: list[str],
    mock_inbox,
):
    from src.lib.fs_utils import flatten_files_in_dir

    before_files = [f.name for f in flatten_files_in_dir(test_path, preview=True)]

    flatten_files_in_dir(test_path, on_conflict="skip")

    after_files = list(isorted([f.name for f in test_path.iterdir() if f.is_file()]))
    assert before_files == predicted
    assert after_files == expected


@pytest.mark.parametrize(
    "test_files, expected",
    [
        (multi_book_dir, True),
        (multi_disc_dir, False),
    ],
)
def test_flattening_files_affects_order(
    test_files: Path,
    expected: bool,
    mock_inbox,
):
    from src.lib.fs_utils import flattening_files_in_dir_affects_order

    assert flattening_files_in_dir_affects_order(test_files) == expected


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

    (TEST_DIRS.inbox / "recently_modified_file.txt").unlink(missing_ok=True)
    time.sleep(1)
    assert find_recently_modified_files_and_dirs(TEST_DIRS.inbox, 0.5) == []

    # create a file
    time.sleep(0.5)
    (TEST_DIRS.inbox / "recently_modified_file.txt").touch()
    assert (
        find_recently_modified_files_and_dirs(TEST_DIRS.inbox, 5)[0][0]
        == TEST_DIRS.inbox / "recently_modified_file.txt"
    )
    # remove the file
    (TEST_DIRS.inbox / "recently_modified_file.txt").unlink()


def test_was_recently_modified():
    from src.lib.fs_utils import was_recently_modified

    nested_dir = TEST_DIRS.inbox / "test_was_recently_modified"
    shutil.rmtree(nested_dir, ignore_errors=True)
    nested_dir.mkdir(parents=True, exist_ok=True)

    time.sleep(1)
    (nested_dir / "recently_modified_file.txt").unlink(missing_ok=True)
    assert not was_recently_modified(TEST_DIRS.inbox, 1)

    # create a file
    (nested_dir / "recently_modified_file.txt").touch()
    assert was_recently_modified(TEST_DIRS.inbox, 1)
    # remove the file
    (nested_dir / "recently_modified_file.txt").unlink()


def test_last_updated_at(
    old_mill__multidisc_mp3: Audiobook, capfd: pytest.CaptureFixture[str]
):
    from src.lib.fs_utils import last_updated_at

    inbox_last_updated = last_updated_at(TEST_DIRS.inbox)
    book_last_updated = last_updated_at(old_mill__multidisc_mp3.path)

    # move a file in multi-disc book to its root
    for f in old_mill__multidisc_mp3.path.rglob("*"):
        if f.is_file() and f.suffix == ".mp3":
            f.rename(old_mill__multidisc_mp3.path / f.name)
            f.touch()
            break

    assert last_updated_at(TEST_DIRS.inbox) > inbox_last_updated
    assert last_updated_at(old_mill__multidisc_mp3.path) > book_last_updated


def test_hash_dir(
    old_mill__multidisc_mp3: Audiobook,
    tower_treasure__flat_mp3: Audiobook,
):
    from src.lib.fs_utils import hash_dir

    baseline_inbox_hash = hash_dir(TEST_DIRS.inbox)
    baseline_mill_hash = hash_dir(old_mill__multidisc_mp3.path)
    baseline_tower_hash = hash_dir(tower_treasure__flat_mp3.path)

    # move a file in multi-disc book to its root
    for f in old_mill__multidisc_mp3.path.rglob("*"):
        if f.is_file() and f.suffix == ".mp3":
            f.rename(old_mill__multidisc_mp3.path / f.name)
            f.touch()
            break

    assert hash_dir(TEST_DIRS.inbox) != baseline_inbox_hash
    assert hash_dir(old_mill__multidisc_mp3.path) != baseline_mill_hash
    assert hash_dir(tower_treasure__flat_mp3.path) == baseline_tower_hash


def test_hash_dir_ignores_log_files(
    old_mill__multidisc_mp3: Audiobook,
    tower_treasure__flat_mp3: Audiobook,
):
    from src.lib.fs_utils import hash_dir

    baseline_inbox_hash = hash_dir(TEST_DIRS.inbox, only_file_exts=[".mp3"])
    baseline_mill_hash = hash_dir(old_mill__multidisc_mp3.path, only_file_exts=[".mp3"])
    baseline_tower_hash = hash_dir(
        tower_treasure__flat_mp3.path, only_file_exts=[".mp3"]
    )

    # create a bunch of log files
    for d in [old_mill__multidisc_mp3.path, tower_treasure__flat_mp3.path]:
        (d / "test-m4b-tool.log").touch()

    assert hash_dir(TEST_DIRS.inbox, only_file_exts=[".mp3"]) == baseline_inbox_hash
    assert (
        hash_dir(old_mill__multidisc_mp3.path, only_file_exts=[".mp3"])
        == baseline_mill_hash
    )
    assert (
        hash_dir(tower_treasure__flat_mp3.path, only_file_exts=[".mp3"])
        == baseline_tower_hash
    )

    # remove the log files
    for d in [old_mill__multidisc_mp3.path, tower_treasure__flat_mp3.path]:
        (d / "test-m4b-tool.log").unlink()


def test_hash_dir_respects_only_file_exts(
    old_mill__multidisc_mp3: Audiobook,
    tower_treasure__flat_mp3: Audiobook,
):
    from src.lib.fs_utils import hash_dir

    try:
        baseline_inbox_hash = hash_dir(TEST_DIRS.inbox, only_file_exts=[".mp3"])
        baseline_mill_hash = hash_dir(
            old_mill__multidisc_mp3.path, only_file_exts=[".mp3"]
        )
        baseline_tower_hash = hash_dir(
            tower_treasure__flat_mp3.path, only_file_exts=[".mp3"]
        )

        for d in [
            old_mill__multidisc_mp3.path / d for d in ["Disc 1", "Disc 2", "Disc 3"]
        ]:
            # make a bunch of non-mp3 files
            for ext in [".txt", ".jpg", ".png", ".pdf"]:
                (d / f"non_mp3_file{ext}").touch()

            # make a bunch of mp3 files
            for i in range(1, 4):
                (d / f"mp3_file{i}.mp3").touch()

        for ext in [".txt", ".jpg", ".png", ".pdf"]:
            (tower_treasure__flat_mp3.path / f"non_mp3_file{ext}").touch()

        assert hash_dir(TEST_DIRS.inbox, only_file_exts=[".mp3"]) != baseline_inbox_hash
        assert (
            hash_dir(old_mill__multidisc_mp3.path, only_file_exts=[".mp3"])
            != baseline_mill_hash
        )
        assert (
            hash_dir(tower_treasure__flat_mp3.path, only_file_exts=[".mp3"])
            == baseline_tower_hash
        )
    finally:
        # remove all the extra files
        for f in [
            *old_mill__multidisc_mp3.path.rglob("*"),
            *tower_treasure__flat_mp3.path.rglob("*"),
        ]:
            if f.is_file() and (
                f.suffix in [".txt", ".jpg", ".png", ".pdf"] or f.stat().st_size == 0
            ):
                f.unlink()


def test_find_cover_art_file(the_sunlit_man__flat_mp3: Audiobook):
    from src.lib.fs_utils import find_cover_art_file

    cover_art = find_cover_art_file(the_sunlit_man__flat_mp3.path)
    assert cover_art
    assert cover_art.name == "folder.jpg"
    assert cover_art.stat().st_size == pytest.approx(394 * 1000, rel=0.1)


@pytest.mark.parametrize(
    "size, expect_size, is_valid",
    [
        (0, 0, False),
        (1, 631, False),
        (100, 784, False),
        (1000, 1326, False),
        (10000, 8014, False),
        (13000, 1024 * 10, True),
        (100000, 70565, True),
    ],
)
def test_find_cover_art_file_ignores_too_small_files(
    size: int, expect_size: int, is_valid: bool, tmp_path: Path
):

    w = h = int(size**0.5)

    def rand_pixel():
        return (0, 0, 0) if bool(random.getrandbits(1)) else (255, 255, 255)

    if w == 0:
        # create an empty file
        (tmp_path / "cover.jpg").touch()
    else:
        img = Image.new("RGB", (w, h))
        for x in range(w):
            for y in range(h):
                img.putpixel((x, y), rand_pixel())

        img.save(tmp_path / "cover.jpg")

    assert (tmp_path / "cover.jpg").stat().st_size == pytest.approx(
        expect_size, rel=0.1
    )

    assert bool(find_cover_art_file(tmp_path)) == is_valid
