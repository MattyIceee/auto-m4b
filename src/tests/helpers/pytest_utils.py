import os
import re
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pytest import CaptureFixture
from tinta import Tinta

from src.lib.audiobook import Audiobook
from src.lib.config import cfg, OnComplete
from src.lib.formatters import human_elapsed_time
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
        rel_time = human_elapsed_time(-from_now)
        cls.print(
            f"Adding '{book}' to failed list, setting last modified to {rel_time}"
        )
        InboxState().set_failed(book, "Test", last_updated_at)

    @classmethod
    def unfail_book(cls, book: Audiobook | str, delay: int = 0):
        time.sleep(delay)
        cls.print(f"Removing '{book}' from failed list (if present)")
        InboxState().set_ok(book)

    @classmethod
    def set_match_filter(cls, match_name: str | None, delay: int = 0):
        time.sleep(delay)
        cls.print(f"Setting MATCH_NAME to {match_name}")
        InboxState().set_match_filter(match_name)

    @classmethod
    @contextmanager
    def set_sleep_time(cls, sleep_time: int | str, delay: int = 0):
        time.sleep(delay)
        orig_sleep_time = cfg.SLEEP_TIME
        cls.print(f"Setting SLEEP_TIME to {sleep_time}")
        os.environ["SLEEP_TIME"] = str(sleep_time)
        cfg.SLEEP_TIME = float(sleep_time)
        yield
        cfg.SLEEP_TIME = orig_sleep_time
        os.environ["SLEEP_TIME"] = str(orig_sleep_time)

    @classmethod
    @contextmanager
    def set_wait_time(cls, wait_time: int | str, delay: int = 0):
        time.sleep(delay)
        orig_wait_time = cfg.WAIT_TIME
        cls.print(f"Setting WAIT_TIME to {wait_time}")
        os.environ["WAIT_TIME"] = str(wait_time)
        cfg.WAIT_TIME = float(wait_time)
        yield
        cfg.WAIT_TIME = orig_wait_time
        os.environ["WAIT_TIME"] = str(orig_wait_time)

    @classmethod
    @contextmanager
    def set_on_complete(cls, on_complete: OnComplete, delay: int = 0):
        time.sleep(delay)
        orig_on_complete = cfg.ON_COMPLETE
        cls.print(f"Setting ON_COMPLETE to {on_complete}")
        os.environ["ON_COMPLETE"] = on_complete
        cfg.ON_COMPLETE = on_complete
        yield
        cfg.ON_COMPLETE = orig_on_complete
        os.environ["ON_COMPLETE"] = orig_on_complete

    @classmethod
    @contextmanager
    def set_backups(cls, enabled: bool, delay: int = 0):
        time.sleep(delay)
        orig_backups = cfg.BACKUP
        cls.print(f"Setting BACKUP to {enabled}")
        os.environ["BACKUP"] = "Y" if enabled else "N"
        cfg.BACKUP = enabled
        yield
        cfg.BACKUP = orig_backups
        os.environ["BACKUP"] = "Y" if orig_backups else "N"

    @classmethod
    def force_inbox_hash_change(cls, *, delay: int = 0, age: float = 0.5):
        time.sleep(delay)
        cls.print(f"Forcing hash change for inbox")
        str_age = f"-{age}s" if age > 0 else f"+{abs(age)}s"

        new_hash = (
            f"forcing-change {str_age}",
            time.time() - age,
        )
        inbox = InboxState()
        inbox._hashes.insert(0, new_hash)
        inbox._last_run = new_hash

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
    def enable_convert_series(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Enabling convert series")
        os.environ["CONVERT_SERIES"] = "Y"
        cfg.CONVERT_SERIES = True

    @classmethod
    def disable_convert_series(cls, delay: int = 0):
        time.sleep(delay)
        cls.print("Disabling convert series")
        os.environ["CONVERT_SERIES"] = "N"
        cfg.CONVERT_SERIES = False

    @classmethod
    def enable_backups(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Enabling backups")
        os.environ["BACKUP"] = "Y"
        cfg.BACKUP = True

    @classmethod
    def disable_backups(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Disabling backups")
        os.environ["BACKUP"] = "N"
        cfg.BACKUP = False

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
                [
                    "".join("".join(p.split("\n")).split())
                    for p in re.findall(
                        rf"Source: {TEST_DIRS.inbox}/(?P<book_key>\w.*\n?(?!- Output:).*)",
                        s,
                    )
                ]
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
        did_process_all = all([book.key in processed for book in books])
        ok = did_process_all and len(processed) == len(books)
        books_list = (
            "\n - " + "\n - ".join([book.key for book in books]) if books else ""
        )
        processed_list = "\n - " + "\n - ".join(processed) if processed else ""
        assert (
            ok
        ), f"Expected {len(books)} to be converted: {books_list}\n\nGot {len(processed)}: {processed_list}"
        if found is not None:
            try:
                assert out.count(f"Found {found[0]} book") == found[1]
            except AssertionError:
                # cls.print(out)
                actual = re.findall(r"Found (\d+) books?", out)
                expected = " × ".join(map(str, list(found)))
                raise AssertionError(
                    f"Found books count mismatch - should be {expected}, got {len(actual)} - {actual}"
                )
        if converted is not None:
            try:
                assert out.count("Converted") == converted
            except AssertionError:
                # cls.print(out)
                actual = re.findall(r"Converted.*(?<!\\n)", out)
                raise AssertionError(
                    f"'Converted' print count mismatch - should be {converted}, got {len(actual)} - {actual}"
                )

        return ok
