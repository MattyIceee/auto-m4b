import random
import re
import shutil
import time
from pathlib import Path

import pytest
from PIL import Image

from src.lib.audiobook import Audiobook
from src.lib.fs_utils import (
    filter_ignored,
    find_book_audio_files,
    find_cover_art_file,
    find_first_audio_file,
    find_next_audio_file,
)
from src.lib.misc import isorted, re_group
from src.lib.typing import BookStructure
from src.tests.conftest import TEST_DIRS
from src.tests.helpers.pytest_dirs import MOCKED


@pytest.mark.parametrize(
    "path, mindepth, maxdepth, expected",
    [
        # fmt: off
        (TEST_DIRS.inbox, None, None, MOCKED.all_dirs_no_series),
        (TEST_DIRS.inbox, 0, None, MOCKED.all_dirs_no_series),
        (TEST_DIRS.inbox, None, 0, []),
        (TEST_DIRS.inbox, 0, 0, []),
        (TEST_DIRS.inbox, 0, 1, MOCKED.flat_dirs + [MOCKED.mixed_dir] + [MOCKED.single_dir_m4b, MOCKED.single_dir_mp3]),
        (TEST_DIRS.inbox, 1, 1, MOCKED.flat_dirs + [MOCKED.mixed_dir] + [MOCKED.single_dir_mp3, MOCKED.single_dir_m4b]),
        (TEST_DIRS.inbox, 1, 2, MOCKED.all_dirs_no_series),
        (TEST_DIRS.inbox, 2, 2, [MOCKED.mixed_dir] + MOCKED.multi_dirs + [MOCKED.single_nested_dir_mp3]),
        # fmt: on
    ],
)
def test_find_base_dirs_with_audio_files(
    path: Path,
    mindepth: int,
    maxdepth: int,
    expected: list[Path],
    mock_inbox,
    setup_teardown,
    enable_convert_series,
):
    from src.lib.fs_utils import find_base_dirs_with_audio_files

    assert find_base_dirs_with_audio_files(path, mindepth, maxdepth) == isorted(
        expected
    )


@pytest.mark.parametrize(
    "expected_structure, path",
    [
        *[("flat", d) for d in MOCKED.flat_dirs],
        ("flat_nested", MOCKED.flat_nested_dir),
        ("multi_book_series", MOCKED.multi_book_series_dir),
        ("multi_disc", MOCKED.multi_disc_dir),
        ("multi_part", MOCKED.multi_part_dir),
        ("multi_nested", MOCKED.multi_nested_dir),
        ("multi_mixed", MOCKED.mixed_dir),
        ("standalone", MOCKED.standalone_mp3_1),
        ("standalone", MOCKED.standalone_m4b),
        ("single", MOCKED.single_dir_mp3),
        ("empty", TEST_DIRS.inbox / "empty_dir"),
    ],
)
def test_find_book_audio_files(
    expected_structure: BookStructure,
    path: Path,
    mock_inbox,
    setup_teardown,
):
    structure, _paths = find_book_audio_files(path)

    assert structure == expected_structure


@pytest.mark.parametrize(
    "name, kwargs, expected",
    [
        ("include_parents", {"exclude_series_parents": False}, MOCKED.all_dirs),
        ("exclude_parents", {"exclude_series_parents": True}, MOCKED.all_book_dirs),
        ("default", {"only_series_parents": False}, MOCKED.all_dirs),
        ("only_parents", {"only_series_parents": True}, [MOCKED.multi_book_series_dir]),
    ],
)
def test_find_book_dirs_in_inbox(
    name, kwargs, expected, mock_inbox, setup_teardown, enable_convert_series
):
    from src.lib.fs_utils import find_book_dirs_in_inbox

    assert find_book_dirs_in_inbox(**kwargs) == expected


def test_find_book_dirs_in_inbox_empty_if_series_off(
    mock_inbox, setup_teardown, disable_convert_series
):
    from src.lib.fs_utils import find_book_dirs_in_inbox

    assert find_book_dirs_in_inbox(only_series_parents=True) == []


def test_find_standalone_books_in_inbox(
    mock_inbox, setup_teardown, enable_convert_series
):
    from src.lib.fs_utils import find_standalone_books_in_inbox

    assert find_standalone_books_in_inbox() == MOCKED.standalone_files


@pytest.mark.usefixtures("the_hobbit__multidisc_mp3")
@pytest.mark.parametrize(
    "test_path, predicted, expected",
    [
        (
            MOCKED.multi_book_series_dir,
            [
                "mock_book_series - ch. 1.mp3",
                "mock_book_series - ch. 2.mp3",
                "mock_book_series - ch. 1.mp3",
                "mock_book_series - ch. 2.mp3",
                "mock_book_series - ch. 3.mp3",
                "mock_book_series - ch. 4.mp3",
                "mock_book_series - ch. 1.mp3",
                "mock_book_series - ch. 2.mp3",
                "mock_book_series - ch. 3.mp3",
            ],
            [
                "mock_book_series - ch. 1.mp3",
                "mock_book_series - ch. 2.mp3",
                "mock_book_series - ch. 3.mp3",
                "mock_book_series - ch. 4.mp3",
            ],
        ),
        (
            MOCKED.multi_disc_dir,
            [
                "mock_book_multi_disc1 - ch_1.mp3",
                "mock_book_multi_disc1 - ch_2.mp3",
                "mock_book_multi_disc2 - ch_3.mp3",
                "mock_book_multi_disc2 - ch_4.mp3",
                "mock_book_multi_disc3 - ch_5.mp3",
                "mock_book_multi_disc3 - ch_6.mp3",
                "mock_book_multi_disc4 - ch_7.mp3",
                "mock_book_multi_disc4 - ch_8.mp3",
            ],
            [
                "mock_book_multi_disc1 - ch_1.mp3",
                "mock_book_multi_disc1 - ch_2.mp3",
                "mock_book_multi_disc2 - ch_3.mp3",
                "mock_book_multi_disc2 - ch_4.mp3",
                "mock_book_multi_disc3 - ch_5.mp3",
                "mock_book_multi_disc3 - ch_6.mp3",
                "mock_book_multi_disc4 - ch_7.mp3",
                "mock_book_multi_disc4 - ch_8.mp3",
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


hobbitses = [
    "cover.jpg",
    "J.R.R. Tolkien - The Hobbit [Full Cast] - Disc 01 - 01 - Mr Bilbo Baggins.mp3",
    "J.R.R. Tolkien - The Hobbit [Full Cast] - Disc 01 - 12 - Elrond Interprets the Map.mp3",
    "J.R.R. Tolkien - The Hobbit [Full Cast] - Disc 02 - 02 - The battle against the goblins.mp3",
    "J.R.R. Tolkien - The Hobbit [Full Cast] - Disc 02 - 07 - The edge of the Land Beyond.mp3",
    "J.R.R. Tolkien - The Hobbit [Full Cast] - Disc 03 - 01 - Straying from the Path.mp3",
    "J.R.R. Tolkien - The Hobbit [Full Cast] - Disc 03 - 06 - The Gates of Lake-town.mp3",
    "J.R.R. Tolkien - The Hobbit [Full Cast] - Disc 04 - 04 - The besiegers' terms.mp3",
    "J.R.R. Tolkien - The Hobbit [Full Cast] - Disc 04 - 06 - Thorin's rage.mp3",
    "J.R.R. Tolkien - The Hobbit [Full Cast] - Disc 04 - 10 - The return journey begins.mp3",
    "J.R.R. Tolkien - The Hobbit [Full Cast] - Disc 05 - 01 - Opening and Bilbo's Theme.mp3",
    "J.R.R. Tolkien - The Hobbit [Full Cast] - Disc 05 - 02 - Elves' Dances.mp3",
    "J.R.R. Tolkien - The Hobbit [Full Cast] - Disc 05 - 03 - Bilbo's Lullaby.mp3",
]


@pytest.mark.parametrize(
    "test_path, predicted, expected",
    [
        (
            TEST_DIRS.inbox / "the_hobbit__multidisc_mp3",
            hobbitses,
            hobbitses,
        ),
    ],
)
def test_flatten_multidisc_book(
    test_path: Path,
    expected: list[str],
    predicted: list[str],
    the_hobbit__multidisc_mp3,
):
    from src.lib.fs_utils import flatten_files_in_dir

    before_files = [f.name for f in flatten_files_in_dir(test_path, preview=True)]

    flatten_files_in_dir(test_path, on_conflict="skip")

    after_files = list(
        isorted([f.name for f in filter_ignored(test_path.iterdir()) if f.is_file()])
    )
    assert before_files == predicted
    assert after_files == expected

    # reset the files
    # put each file if it matches `Disc 0(?P<disc_number>\d)` into a dir (make if needed) J.R.R. Tolkien - The Hobbit - Disc <disc_number>
    for f in test_path.iterdir():
        if f.is_file() and "Disc" in f.name:
            disc_number = re_group(
                re.search(r"Disc 0(?P<disc_number>\d)", f.name), "disc_number"
            )
            disc_dir = test_path / f"J.R.R. Tolkien - The Hobbit - Disc {disc_number}"
            disc_dir.mkdir(exist_ok=True)
            f.rename(disc_dir / f.name)


@pytest.mark.parametrize(
    "test_files, expected",
    [
        (MOCKED.multi_book_series_dir, True),
        (MOCKED.multi_disc_dir, False),
        (MOCKED.multi_disc_dir_with_extras, False),
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


def test_find_recently_modified_files_and_dirs():
    from src.lib.config import cfg
    from src.lib.fs_utils import find_recently_modified_files_and_dirs

    (TEST_DIRS.inbox / "recently_modified_file.mp3").unlink(missing_ok=True)
    time.sleep(1)
    assert find_recently_modified_files_and_dirs(TEST_DIRS.inbox, 0.5) == []

    # create a file
    time.sleep(0.5)
    (TEST_DIRS.inbox / "recently_modified_file.mp3").touch()
    recents = find_recently_modified_files_and_dirs(
        TEST_DIRS.inbox, 5, only_file_exts=cfg.AUDIO_EXTS
    )
    assert recents[0][0] == TEST_DIRS.inbox / "recently_modified_file.mp3"
    # remove the file
    (TEST_DIRS.inbox / "recently_modified_file.mp3").unlink()


def test_was_recently_modified():
    from src.lib.fs_utils import was_recently_modified

    nested_dir = TEST_DIRS.inbox / "test_was_recently_modified"
    shutil.rmtree(nested_dir, ignore_errors=True)
    nested_dir.mkdir(parents=True, exist_ok=True)

    time.sleep(1)
    (nested_dir / "recently_modified_file.mp3").unlink(missing_ok=True)
    assert not was_recently_modified(TEST_DIRS.inbox, 1)

    # create a file
    (nested_dir / "recently_modified_file.mp3").touch()
    assert was_recently_modified(TEST_DIRS.inbox, 1)
    # remove the file
    (nested_dir / "recently_modified_file.mp3").unlink()


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
    from src.lib.fs_utils import hash_path

    baseline_inbox_hash = hash_path(TEST_DIRS.inbox)
    baseline_mill_hash = hash_path(old_mill__multidisc_mp3.path)
    baseline_tower_hash = hash_path(tower_treasure__flat_mp3.path)

    # move a file in multi-disc book to its root
    for f in old_mill__multidisc_mp3.path.rglob("*"):
        if f.is_file() and f.suffix == ".mp3":
            f.rename(old_mill__multidisc_mp3.path / f.name)
            f.touch()
            break

    assert hash_path(TEST_DIRS.inbox) != baseline_inbox_hash
    assert hash_path(old_mill__multidisc_mp3.path) != baseline_mill_hash
    assert hash_path(tower_treasure__flat_mp3.path) == baseline_tower_hash


def test_hash_dir_ignores_log_files(
    old_mill__multidisc_mp3: Audiobook,
    tower_treasure__flat_mp3: Audiobook,
):
    from src.lib.fs_utils import hash_path

    baseline_inbox_hash = hash_path(TEST_DIRS.inbox, only_file_exts=[".mp3"])
    baseline_mill_hash = hash_path(
        old_mill__multidisc_mp3.path, only_file_exts=[".mp3"]
    )
    baseline_tower_hash = hash_path(
        tower_treasure__flat_mp3.path, only_file_exts=[".mp3"]
    )

    # create a bunch of log files
    for d in [old_mill__multidisc_mp3.path, tower_treasure__flat_mp3.path]:
        (d / "test-auto-m4b.log").touch()

    assert hash_path(TEST_DIRS.inbox, only_file_exts=[".mp3"]) == baseline_inbox_hash
    assert (
        hash_path(old_mill__multidisc_mp3.path, only_file_exts=[".mp3"])
        == baseline_mill_hash
    )
    assert (
        hash_path(tower_treasure__flat_mp3.path, only_file_exts=[".mp3"])
        == baseline_tower_hash
    )

    # remove the log files
    for d in [old_mill__multidisc_mp3.path, tower_treasure__flat_mp3.path]:
        (d / "test-auto-m4b.log").unlink()


def test_hash_dir_respects_only_file_exts(
    old_mill__multidisc_mp3: Audiobook,
    tower_treasure__flat_mp3: Audiobook,
):
    from src.lib.fs_utils import hash_path

    try:
        baseline_inbox_hash = hash_path(TEST_DIRS.inbox, only_file_exts=[".mp3"])
        baseline_mill_hash = hash_path(
            old_mill__multidisc_mp3.path, only_file_exts=[".mp3"]
        )
        baseline_tower_hash = hash_path(
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

        assert (
            hash_path(TEST_DIRS.inbox, only_file_exts=[".mp3"]) != baseline_inbox_hash
        )
        assert (
            hash_path(old_mill__multidisc_mp3.path, only_file_exts=[".mp3"])
            != baseline_mill_hash
        )
        assert (
            hash_path(tower_treasure__flat_mp3.path, only_file_exts=[".mp3"])
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
        (9400, 7167, False),
        (10000, 8014, True),
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
