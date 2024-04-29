from dataclasses import dataclass

from src.lib.misc import get_git_root, isorted

GIT_ROOT = get_git_root()
SRC_ROOT = GIT_ROOT / "src"
TESTS_ROOT = SRC_ROOT / "tests"
TESTS_TMP_ROOT = TESTS_ROOT / "tmp"
FIXTURES_ROOT = TESTS_ROOT / "fixtures"


@dataclass
class TEST_DIRS:

    inbox = TESTS_TMP_ROOT / "inbox"
    converted = TESTS_TMP_ROOT / "converted"
    archive = TESTS_TMP_ROOT / "archive"
    fix = TESTS_TMP_ROOT / "fix"
    backup = TESTS_TMP_ROOT / "backup"
    working = TESTS_TMP_ROOT / "working"
    fixtures = FIXTURES_ROOT


multi_book_series_dir = TEST_DIRS.inbox / "mock_book_multi_book_series"


@dataclass
class MOCKED:

    flat_dir1 = TEST_DIRS.inbox / "mock_book_1"
    flat_dir2 = TEST_DIRS.inbox / "mock_book_2"
    flat_dir3 = TEST_DIRS.inbox / "mock_book_3"
    flat_dir4 = TEST_DIRS.inbox / "mock_book_4"
    flat_dirs = [flat_dir1, flat_dir2, flat_dir3, flat_dir4]

    mixed_dir = TEST_DIRS.inbox / "mock_book_mixed"

    flat_nested_dir = TEST_DIRS.inbox / "mock_book_flat_nested"
    series_books = [
        multi_book_series_dir / "Dawn - Book 1",
        multi_book_series_dir / "Dusk - Book 3",
        multi_book_series_dir / "High Noon - Book 2",
    ]
    multi_book_series_dir = multi_book_series_dir
    multi_disc_dir = TEST_DIRS.inbox / "mock_book_multi_disc"
    multi_disc_dir_with_extras = (
        TEST_DIRS.inbox / "mock_book_multi_disc_dir_with_extras"
    )
    multi_part_dir = TEST_DIRS.inbox / "mock_book_multi_part"
    multi_nested_dir = TEST_DIRS.inbox / "mock_book_multi_nested"

    single_dir_mp3 = TEST_DIRS.inbox / "mock_book_single_mp3"
    single_nested_dir_mp3 = TEST_DIRS.inbox / "mock_book_single_nested_mp3"
    single_dir_m4b = TEST_DIRS.inbox / "mock_book_single_m4b"

    multi_dirs = [
        flat_nested_dir,
        multi_book_series_dir,
        multi_disc_dir,
        multi_disc_dir_with_extras,
        multi_nested_dir,
        multi_part_dir,
    ]
    single_dirs = [single_dir_mp3, single_nested_dir_mp3, single_dir_m4b]
    series_dirs = [multi_book_series_dir, *series_books]

    all_dirs_no_series = isorted(flat_dirs + [mixed_dir] + multi_dirs + single_dirs)

    all_dirs = isorted(
        flat_dirs + [mixed_dir] + multi_dirs + series_dirs[1:] + single_dirs
    )

    all_book_dirs = [d for d in all_dirs if not d == multi_book_series_dir]

    standalone_mp3_1 = TEST_DIRS.inbox / "mock_book_standalone_file_a.mp3"
    standalone_mp3_2 = TEST_DIRS.inbox / "mock_book_standalone_file_b.mp3"
    standalone_m4b = TEST_DIRS.inbox / "mock_book_standalone_file.m4b"

    standalone_files = [
        standalone_m4b,
        standalone_mp3_1,
        standalone_mp3_2,
    ]

    empty = TEST_DIRS.inbox / "mock_book_empty"

    all_ = all_dirs + single_dirs
