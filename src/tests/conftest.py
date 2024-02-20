import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values

sys.path.append(str(Path(__file__).parent.parent))


def get_git_root():
    return Path(
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"])
        .strip()
        .decode("utf-8")
    )


GIT_ROOT = get_git_root()
SRC_ROOT = Path(__file__).parent.parent
TESTS_ROOT = Path(__file__).parent
TESTS_TMP_ROOT = TESTS_ROOT / "tmp"
FIXTURES_ROOT = TESTS_ROOT / "fixtures"


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

    for k, v in dotenv_values(GIT_ROOT / ".env.test").items():
        if v:
            p = Path(v).expanduser()
            if not p.is_absolute():
                p = GIT_ROOT / p
            os.environ[k] = str(p)
            if Path(v).exists() and k != "INBOX_FOLDER":
                shutil.rmtree(v)
            p.mkdir(parents=True, exist_ok=True)


def load_test_fixture(name: str):
    if inbox := os.getenv("INBOX_FOLDER"):
        src = TESTS_ROOT / "fixtures" / name
        dst = Path(inbox) / name
        dst.mkdir(parents=True, exist_ok=True)

        for f in src.glob("**/*"):
            dst_f = dst / f.relative_to(src)
            if f.is_file() and not dst_f.exists():
                shutil.copy(f, dst_f)


@pytest.fixture(scope="function")
def tower_treasure__flat_mp3():
    load_test_fixture("tower_treasure__flat_mp3")


@pytest.fixture(scope="function")
def tower_treasure__multidisc_mp3():
    load_test_fixture("tower_treasure__multidisc_mp3")


@pytest.fixture(scope="function")
def tower_treasure__nested_mp3():
    load_test_fixture("tower_treasure__nested_mp3")


@pytest.fixture(scope="function")
def tower_treasure__all():
    load_test_fixture("tower_treasure__flat_mp3")
    load_test_fixture("tower_treasure__multidisc_mp3")
    load_test_fixture("tower_treasure__nested_mp3")


def purge_tmp():
    for folder in [
        "INBOX_FOLDER",
        "CONVERTED_FOLDER",
        "ARCHIVE_FOLDER",
        "FIX_FOLDER",
        "BACKUP_FOLDER",
        "BUILD_FOLDER",
        "MERGE_FOLDER",
        "TRASH_FOLDER",
    ]:
        if folder := os.getenv(folder):
            shutil.rmtree(folder, ignore_errors=True)


@pytest.fixture(scope="function", autouse=False)
def cleanup():
    yield
    purge_tmp()


@pytest.fixture(scope="function", autouse=False)
def mock_inbox(setup, cleanup):
    purge_tmp()
    """Populate INBOX_FOLDER with mocked sample audiobooks."""
    if env := os.getenv("INBOX_FOLDER"):
        inbox = Path(env)
        inbox.mkdir(parents=True, exist_ok=True)

        # make 4 sample audiobooks using nealy empty txt files (~5kb) as pretend mp3 files.
        for i in range(1, 5):
            book = inbox / f"test_book_{i}"
            book.mkdir(parents=True, exist_ok=True)
            for j in range(1, 4):
                with open(book / f"test_book_{i} - part_{j}.mp3", "w") as f:
                    f.write("a" * 1024 * 5)

        # make a book with a single nested folder
        nested = inbox / "test_book_nested" / "inner_dir"
        nested.mkdir(parents=True, exist_ok=True)
        for i in range(1, 4):
            with open(nested / f"test_book_nested - part_{i}.mp3", "w") as f:
                f.write("a" * 1024 * 5)

        # make a multi-disc book
        multi_disc = inbox / "test_book_multi_disc"
        multi_disc.mkdir(parents=True, exist_ok=True)
        for d in range(1, 5):
            disc = multi_disc / f"Disc {d} of 4"
            disc.mkdir(parents=True, exist_ok=True)
            for i in range(1, 3):
                with open(disc / f"test_book_multi_disc - part_{i}.mp3", "w") as f:
                    f.write("a" * 1024 * 5)

        # make a multi-series directory
        multi_series = inbox / "test_book_multi_series"
        multi_series.mkdir(parents=True, exist_ok=True)
        for s in ["A", "B", "C"]:
            series = multi_series / f"Series {s}"
            series.mkdir(parents=True, exist_ok=True)
            for i in range(1, 3):
                with open(series / f"test_book_multi_series - part_{i}.mp3", "w") as f:
                    f.write("a" * 1024 * 5)

        # make 2 top-level mp3 files
        for t in ["a", "b"]:
            with open(inbox / f"test_book_standalone_file_{t}.mp3", "w") as f:
                f.write("a" * 1024 * 5)

        yield inbox
        # remove everything in the inbox that starts with `test_book_`
        for f in inbox.glob("test_book_*"):
            shutil.rmtree(f, ignore_errors=True)
