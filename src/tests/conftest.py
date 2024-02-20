import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent))
# get git root
import subprocess

from dotenv import dotenv_values


def get_git_root():
    return Path(
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"])
        .strip()
        .decode("utf-8")
    )


GIT_ROOT = get_git_root()
SRC_ROOT = Path(__file__).parent.parent
TESTS_ROOT = Path(__file__).parent


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


@pytest.fixture(scope="function")
def use_arcade_catastrophe__multipart_mp3s():
    # copy TESTS_ROOT/fixtures/arcade_catastrophe__multipart_mp3s to INBOX_FOLDER
    if inbox := os.getenv("INBOX_FOLDER"):
        src = TESTS_ROOT / "fixtures" / "arcade_catastrophe__multipart_mp3s"
        dst = Path(inbox) / "arcade_catastrophe__multipart_mp3s"
        dst.mkdir(parents=True, exist_ok=True)

        for f in src.glob("**/*"):
            dst_f = dst / f.relative_to(src)
            if f.is_file() and not dst_f.exists():
                shutil.copy(f, dst_f)


@pytest.fixture(scope="function", autouse=False)
def cleanup():
    yield
    # remove all files from INBOX_FOLDER, CONVERTED_FOLDER, ARCHIVE_FOLDER, FIX_FOLDER, BACKUP_FOLDER, BUILD_FOLDER, MERGE_FOLDER, TRASH_FOLDER
    for folder in [
        # "INBOX_FOLDER",
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
