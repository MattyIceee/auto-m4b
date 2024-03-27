import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from pytest import CaptureFixture
from tinta import Tinta

from src.lib.audiobook import Audiobook
from src.lib.config import cfg
from src.lib.fs_utils import flatten_files_in_dir, inbox_last_updated_at
from src.lib.inbox_state import InboxState
from src.lib.typing import ENV_DIRS
from src.tests.conftest import TEST_DIRS


class testutils:

    @classmethod
    def print(cls, *s: Any):
        Tinta().tint(213, *s).print()

    @classmethod
    def purge_all(cls):
        for folder in ENV_DIRS:
            if folder := os.getenv(folder):
                shutil.rmtree(folder, ignore_errors=True)

    @classmethod
    def flatten_book(cls, book: Audiobook, delay: int = 0):

        time.sleep(delay)
        cls.print(f"About to flatten book {book}")
        cls.print(f"Inbox last updated at {inbox_last_updated_at()}")
        flatten_files_in_dir(book.inbox_dir)
        cls.print(f"Fixed '{book}'")
        cls.print(f"Inbox last updated at {inbox_last_updated_at()}")

    @classmethod
    def fail_book(cls, book: Audiobook | str, delay: int = 0, *, from_now: float = 0):

        time.sleep(delay)
        last_updated_at = time.time() + from_now
        lm_string = "now" if from_now == 0 else f"{from_now}s from now"
        cls.print(
            f"Adding '{book}' to failed list, setting last modified to {lm_string}"
        )
        current_failed_books = json.loads(os.environ.get("FAILED_BOOKS", "{}"))
        k = book.basename if isinstance(book, Audiobook) else book
        current_failed_books.update({k: str(last_updated_at)})
        os.environ["FAILED_BOOKS"] = json.dumps(current_failed_books)
        InboxState()._sync_env_failed_books({k: last_updated_at})

    @classmethod
    def unfail_book(cls, book: Audiobook | str, delay: int = 0):

        time.sleep(delay)
        cls.print(f"Removing '{book}' from failed list (if present)")
        current_failed_books = json.loads(os.environ.get("FAILED_BOOKS", "{}"))
        k = book.basename if isinstance(book, Audiobook) else book
        current_failed_books.pop(k, None)
        os.environ["FAILED_BOOKS"] = json.dumps(current_failed_books)
        inbox = InboxState()
        orig_failed_books = inbox.failed_books.copy()
        inbox._sync_env_failed_books(current_failed_books)
        if orig_failed_books != inbox.failed_books:
            cls.print(f"Removed '{book}' from failed list")
        else:
            cls.print(f"'{book}' not in failed list")

    @classmethod
    def set_match_filter(cls, match_name: str | None, delay: int = 0):

        time.sleep(delay)
        cls.print(f"Setting MATCH_NAME to {match_name}")
        InboxState().set_match_filter(match_name)

    @classmethod
    def set_sleeptime(cls, sleeptime: int | str, delay: int = 0):

        time.sleep(delay)
        cls.print(f"Setting SLEEPTIME to {sleeptime}")
        os.environ["SLEEPTIME"] = str(sleeptime)
        cfg.SLEEPTIME = float(sleeptime)

    @classmethod
    def rename_files(
        cls,
        book: Audiobook,
        *,
        prepend: str = "",
        append: str = "",
        lstrip: str = "",
        rstrip: str = "",
        delay: int = 0,
    ):

        time.sleep(delay)
        msg = f"Renaming files for {book}"
        if prepend:
            msg += f", prepending '{prepend}'"
        if append:
            msg += f", appending '{append}'"
        if lstrip:
            msg += f", left stripping '{lstrip}'"
        if rstrip:
            msg += f", right stripping '{rstrip}'"
        cls.print(msg)
        for f in book.inbox_dir.glob("*"):
            if not f.suffix in cfg.AUDIO_EXTS:
                continue
            stripped = re.sub(rf"^{lstrip}|{rstrip}$", "", f.stem)
            new_name = f"{prepend}{stripped}{append}{f.suffix}"
            f.rename(f.with_name(new_name))

    @classmethod
    def enable_autoflatten(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Enabling autoflatten")
        os.environ["FLATTEN_MULTI_DISC_BOOKS"] = "Y"
        cfg.FLATTEN_MULTI_DISC_BOOKS = True

    @classmethod
    def disable_autoflatten(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Disabling autoflatten")
        os.environ["FLATTEN_MULTI_DISC_BOOKS"] = "N"
        cfg.FLATTEN_MULTI_DISC_BOOKS = False

    @classmethod
    def enable_backups(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Enabling backups")
        os.environ["MAKE_BACKUP"] = "Y"
        cfg.MAKE_BACKUP = True

    @classmethod
    def disable_backups(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Disabling backups")
        os.environ["MAKE_BACKUP"] = "N"
        cfg.MAKE_BACKUP = False

    @classmethod
    def enable_debug(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Enabling debug")
        os.environ["DEBUG"] = "Y"
        cfg.DEBUG = True

    @classmethod
    def disable_debug(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Disabling debug")
        os.environ["DEBUG"] = "N"
        cfg.DEBUG = False

    @classmethod
    def make_mock_file(cls, path: Path, size: int = 1024 * 5):
        if not path.is_absolute():
            path = TEST_DIRS.inbox / path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write("a" * size)

    @classmethod
    def rm(cls, p: Path):
        (
            shutil.rmtree(p, ignore_errors=True)
            if p.is_dir()
            else p.unlink(missing_ok=True)
        )

    @classmethod
    def strip_ansi_codes(cls, s: str) -> str:
        return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", s)

    @classmethod
    def get_stdout(cls, capfd: CaptureFixture[str]) -> str:
        return cls.strip_ansi_codes(capfd.readouterr().out)

    @classmethod
    def make_tmp_files(cls, tmp_path: Path, file_rel_paths: list[str]):
        """Creates a tmp list of files from a tmp_path, and returns the parent directory of the files"""
        d = (tmp_path / file_rel_paths[0]).parent
        d.mkdir(parents=True, exist_ok=True)
        for file in file_rel_paths:
            (tmp_path / file).touch()

        return d

    @classmethod
    def get_all_processed_books(cls, s: str) -> list[str]:
        return list(
            set(
                re.findall(
                    rf"Source folder: {TEST_DIRS.inbox}/(?P<book_name>\w.*)(?!=\\n)", s
                )
            )
        )

    @classmethod
    def assert_only_processed_books(
        cls,
        out: str | CaptureFixture[str],
        *books: Audiobook,
        found: tuple[int, int] | None = None,
        converted: int | None = None,
    ) -> bool:

        if isinstance(out, CaptureFixture):
            out = cls.get_stdout(out)

        processed = cls.get_all_processed_books(out)
        did_process_all = all([book.basename in processed for book in books])
        ok = did_process_all and len(processed) == len(books)
        assert (
            ok
        ), f"Expected ({len(books)}) {books} to be processed, but got ({len(processed)}) {processed}"
        if found is not None:
            try:
                assert out.count(f"Found {found[0]} book") == found[1]
            except AssertionError:
                cls.print(out)
                actual = re.findall(r"Found (\d+) books?", out)
                expected = " × ".join(map(str, list(found)))
                raise AssertionError(
                    f"Found books count mismatch - should be {expected}, got {len(actual)} - {actual}"
                )
        if converted is not None:
            try:
                assert out.count("Converted") == converted
            except AssertionError:
                cls.print(out)
                actual = re.findall(r"Converted.*(?<!\\n)", out)
                raise AssertionError(
                    f"'Converted' print count mismatch - should be {converted}, got {len(actual)} - {actual}"
                )

        return ok
