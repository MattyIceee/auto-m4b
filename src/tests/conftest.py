import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent))

from src.lib.audiobook import Audiobook
from src.lib.misc import get_git_root, load_env

GIT_ROOT = get_git_root()
SRC_ROOT = Path(__file__).parent.parent
TESTS_ROOT = Path(__file__).parent
TESTS_TMP_ROOT = TESTS_ROOT / "tmp"
FIXTURES_ROOT = TESTS_ROOT / "fixtures"

TEST_INBOX = TESTS_TMP_ROOT / "inbox"
TEST_CONVERTED = TESTS_TMP_ROOT / "converted"
TEST_ARCHIVE = TESTS_TMP_ROOT / "archive"
TEST_FIX = TESTS_TMP_ROOT / "fix"
TEST_BACKUP = TESTS_TMP_ROOT / "backup"
TEST_WORKING = TESTS_TMP_ROOT / "working"


@pytest.fixture(autouse=True, scope="session")
def setup():
    # self.inbox_dir = Path(os.getenv("INBOX_FOLDER", "/media/Downloads/#done/#books/#convert/inbox/"))
    # self.converted_dir = Path(os.getenv("CONVERTED_FOLDER", "/media/Books/Audiobooks/_Updated plex copies/"))
    # self.archive_dir = Path(os.getenv("ARCHIVE_FOLDER", "/media/Downloads/#done/#books/#convert/processed/"))
    # self.fix_dir = Path(os.getenv("FIX_FOLDER", "/media/Downloads/#done/#books/#convert/fix/"))
    # self.backup_dir = Path(os.getenv("BACKUP_FOLDER", "/media/Downloads/#done/#books/#convert/backup/"))
    # self.build_dir = Path(os.getenv("BUILD_FOLDER", "/tmp/auto-m4b/build/"))
    # self.merge_dir = Path(os.getenv("MERGE_FOLDER", "/tmp/auto-m4b/merge/"))
    # self.trash_dir = Path(os.getenv("TRASH_FOLDER", "/tmp/auto-m4b/delete/"))
    # self.is_running_pid_file = Path("/tmp/auto-m4b/running")

    # set all ENV vars to __file__/tmp/{dirname}

    os.environ["TEST"] = "Y"
    os.environ["SLEEPTIME"] = "0.1"

    load_env(TESTS_ROOT / ".env.test", clean_working_dirs=True)


def load_test_fixture(name: str):
    src = FIXTURES_ROOT / name
    if not src.exists():
        raise FileNotFoundError(
            f"Fixture {name} not found. Does it exist in {FIXTURES_ROOT}?"
        )
    dst = TEST_INBOX / name
    dst.mkdir(parents=True, exist_ok=True)

    for f in src.glob("**/*"):
        dst_f = dst / f.relative_to(src)
        if f.is_file() and not dst_f.exists():
            shutil.copy(f, dst_f)


@pytest.fixture(scope="function")
def tower_treasure__flat_mp3():
    load_test_fixture("tower_treasure__flat_mp3")
    return Audiobook(TEST_INBOX / "tower_treasure__flat_mp3")


@pytest.fixture(scope="function")
def tower_treasure__multidisc_mp3():
    load_test_fixture("tower_treasure__multidisc_mp3")
    return Audiobook(TEST_INBOX / "tower_treasure__multidisc_mp3")


@pytest.fixture(scope="function")
def tower_treasure__nested_mp3():
    load_test_fixture("tower_treasure__nested_mp3")
    return Audiobook(TEST_INBOX / "tower_treasure__nested_mp3")


@pytest.fixture(scope="function")
def tower_treasure__all():
    load_test_fixture("tower_treasure__flat_mp3")
    load_test_fixture("tower_treasure__multidisc_mp3")
    load_test_fixture("tower_treasure__nested_mp3")


def purge_all():
    for folder in [
        "INBOX_FOLDER",
        "CONVERTED_FOLDER",
        "ARCHIVE_FOLDER",
        "FIX_FOLDER",
        "BACKUP_FOLDER",
        "WORKING_FOLDER",
        "BUILD_FOLDER",
        "MERGE_FOLDER",
        "TRASH_FOLDER",
    ]:
        if folder := os.getenv(folder):
            shutil.rmtree(folder, ignore_errors=True)


@pytest.fixture(scope="function", autouse=False)
def cleanup():
    yield
    purge_all()


@pytest.fixture(scope="function", autouse=False)
def mock_inbox(setup):
    """Populate INBOX_FOLDER with mocked sample audiobooks."""

    TEST_INBOX.mkdir(parents=True, exist_ok=True)

    # make 4 sample audiobooks using nealy empty txt files (~5kb) as pretend mp3 files.
    for i in range(1, 5):
        book = TEST_INBOX / f"mock_book_{i}"
        book.mkdir(parents=True, exist_ok=True)
        for j in range(1, 4):
            with open(book / f"mock_book_{i} - part_{j}.mp3", "w") as f:
                f.write("a" * 1024 * 5)

    # make a book with a single nested folder
    nested = TEST_INBOX / "mock_book_nested" / "inner_dir"
    nested.mkdir(parents=True, exist_ok=True)
    for i in range(1, 4):
        with open(nested / f"mock_book_nested - part_{i}.mp3", "w") as f:
            f.write("a" * 1024 * 5)

    # make a multi-disc book
    multi_disc = TEST_INBOX / "mock_book_multi_disc"
    multi_disc.mkdir(parents=True, exist_ok=True)
    for d in range(1, 5):
        disc = multi_disc / f"Disc {d} of 4"
        disc.mkdir(parents=True, exist_ok=True)
        for i in range(1, 3):
            with open(disc / f"mock_book_multi_disc - part_{i}.mp3", "w") as f:
                f.write("a" * 1024 * 5)

    # make a multi-series directory
    multi_series = TEST_INBOX / "mock_book_multi_series"
    multi_series.mkdir(parents=True, exist_ok=True)
    for s in ["A", "B", "C"]:
        series = multi_series / f"Series {s}"
        series.mkdir(parents=True, exist_ok=True)
        for i in range(1, 3):
            with open(series / f"mock_book_multi_series - part_{i}.mp3", "w") as f:
                f.write("a" * 1024 * 5)

    # make 2 top-level mp3 files
    for t in ["a", "b"]:
        with open(TEST_INBOX / f"mock_book_standalone_file_{t}.mp3", "w") as f:
            f.write("a" * 1024 * 5)

    yield TEST_INBOX
    # remove everything in the inbox that starts with `mock_book_`
    for f in TEST_INBOX.glob("mock_book_*"):
        shutil.rmtree(f, ignore_errors=True)
