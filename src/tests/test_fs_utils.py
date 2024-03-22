import random
import shutil
import time
from pathlib import Path

import pytest
from PIL import Image

from src.lib.audiobook import Audiobook
from src.lib.fs_utils import (
    find_cover_art_file,
    find_first_audio_file,
    find_next_audio_file,
)
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


def test_last_updated_at(
    old_mill__multidisc_mp3: Audiobook, capfd: pytest.CaptureFixture[str]
):
    from src.lib.fs_utils import last_updated_at

    inbox_last_updated = last_updated_at(TEST_INBOX)
    book_last_updated = last_updated_at(old_mill__multidisc_mp3.path)

    # move a file in multi-disc book to its root
    for f in old_mill__multidisc_mp3.path.rglob("*"):
        if f.is_file() and f.suffix == ".mp3":
            f.rename(old_mill__multidisc_mp3.path / f.name)
            f.touch()
            break

    assert last_updated_at(TEST_INBOX) > inbox_last_updated
    assert last_updated_at(old_mill__multidisc_mp3.path) > book_last_updated


def test_hash_dir(
    old_mill__multidisc_mp3: Audiobook,
    tower_treasure__flat_mp3: Audiobook,
):
    from src.lib.fs_utils import hash_dir

    baseline_inbox_hash = hash_dir(TEST_INBOX)
    baseline_mill_hash = hash_dir(old_mill__multidisc_mp3.path)
    baseline_tower_hash = hash_dir(tower_treasure__flat_mp3.path)

    # move a file in multi-disc book to its root
    for f in old_mill__multidisc_mp3.path.rglob("*"):
        if f.is_file() and f.suffix == ".mp3":
            f.rename(old_mill__multidisc_mp3.path / f.name)
            f.touch()
            break

    assert hash_dir(TEST_INBOX) != baseline_inbox_hash
    assert hash_dir(old_mill__multidisc_mp3.path) != baseline_mill_hash
    assert hash_dir(tower_treasure__flat_mp3.path) == baseline_tower_hash


def test_hash_dir_ignores_log_files(
    old_mill__multidisc_mp3: Audiobook,
    tower_treasure__flat_mp3: Audiobook,
):
    from src.lib.fs_utils import hash_dir

    baseline_inbox_hash = hash_dir(TEST_INBOX, only_file_exts=[".mp3"])
    baseline_mill_hash = hash_dir(old_mill__multidisc_mp3.path, only_file_exts=[".mp3"])
    baseline_tower_hash = hash_dir(
        tower_treasure__flat_mp3.path, only_file_exts=[".mp3"]
    )

    # create a bunch of log files
    for d in [old_mill__multidisc_mp3.path, tower_treasure__flat_mp3.path]:
        (d / "test-m4b-tool.log").touch()

    assert hash_dir(TEST_INBOX, only_file_exts=[".mp3"]) == baseline_inbox_hash
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
        baseline_inbox_hash = hash_dir(TEST_INBOX, only_file_exts=[".mp3"])
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

        assert hash_dir(TEST_INBOX, only_file_exts=[".mp3"]) != baseline_inbox_hash
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
