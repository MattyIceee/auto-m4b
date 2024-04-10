import os
import re
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pytest import CaptureFixture
from tinta import Tinta

from src.lib.audiobook import Audiobook
from src.lib.config import cfg, OnComplete
from src.lib.formatters import human_elapsed_time, listify
from src.lib.fs_utils import flatten_files_in_dir, inbox_last_updated_at
from src.lib.inbox_state import InboxState
from src.lib.misc import re_group
from src.lib.typing import ENV_DIRS
from src.tests.conftest import TEST_DIRS

cfg.PID_FILE.unlink(missing_ok=True)


class testutils:

    class check_output(BaseModel):
        found_books_eq: int | None = None
        found_books_gt: int | None = None
        # found_books_gte: int | None = None
        # found_books_lt: int | None = None
        # found_books_lte: int | None = None
        ignored_books_eq: int | None = None
        ignored_books_gt: int | None = None
        retried_books_eq: int | None = None
        retried_books_gt: int | None = None
        # skipped_books_gte: int | None = None
        # skipped_books_lt: int | None = None
        # skipped_books_lte: int | None = None
        skipped_failed_eq: int | None = None
        skipped_failed_gt: int | None = None

        converted_eq: int | None = None
        converted_gt: int | None = None
        # converted_gte: int | None = None
        # converted_lt: int | None = None
        # converted_lte: int | None = None

        def found_books_result(self):
            return ", ".join(
                [
                    f"to have found{self.get_comparator(k)} {v} book(s)"
                    for k, v in self.model_dump().items()
                    if k.startswith("found") and v is not None
                ]
            )

        def failed_books_result(self):
            return ", ".join(
                [
                    f"to have skipped{self.get_comparator(k)} {v} failed book(s)"
                    for k, v in self.model_dump().items()
                    if k.startswith("skipped") and v is not None
                ]
            )

        def ignored_books_result(self):
            return ", ".join(
                [
                    f"to have ignored{self.get_comparator(k)} {v} book(s)"
                    for k, v in self.model_dump().items()
                    if k.startswith("ignored") and v is not None
                ]
            )

        def retried_books_result(self):
            return ", ".join(
                [
                    f"to have retried{self.get_comparator(k)} {v} failed book(s)"
                    for k, v in self.model_dump().items()
                    if k.startswith("retried") and v is not None
                ]
            )


        def converted_books_result(self):
            return ", ".join(
                [
                    f"to have converted{self.get_comparator(k)} {v} book(s)"
                    for k, v in self.model_dump().items()
                    if k.startswith("converted") and v is not None
                ]
            )

        def get_comparator(self, k: str):
            return (
                k.split("_")[-1].replace("eq", "")
                # .replace("gte", ">=")
                .replace("gt", " >")
                # .replace("lte", "<=")
                # .replace("lt", "<")
            )

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
    def set_wait_time(cls, wait_time: float | str, delay: float = 0):
        time.sleep(delay)
        orig_wait_time = cfg.WAIT_TIME
        cls.print(f"Setting WAIT_TIME to {wait_time}")
        # os.environ["WAIT_TIME"] = str(wait_time)
        cfg.WAIT_TIME = float(wait_time)
        yield
        cfg.WAIT_TIME = orig_wait_time
        # os.environ["WAIT_TIME"] = str(orig_wait_time)

    @classmethod
    @contextmanager
    def set_on_complete(cls, on_complete: OnComplete, delay: float = 0):
        time.sleep(delay)
        orig_on_complete = cfg.ON_COMPLETE
        cls.print(f"Setting ON_COMPLETE to {on_complete}")
        # os.environ["ON_COMPLETE"] = on_complete
        cfg.ON_COMPLETE = on_complete
        yield
        cfg.ON_COMPLETE = orig_on_complete
        # os.environ["ON_COMPLETE"] = orig_on_complete

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
        inbox._last_run_end = new_hash

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
        cfg.set_env_var("FLATTEN_MULTI_DISC_BOOKS", True)

    @classmethod
    def disable_autoflatten(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Disabling autoflatten")
        cfg.set_env_var("FLATTEN_MULTI_DISC_BOOKS", False)

    @classmethod
    def enable_convert_series(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Enabling convert series")
        cfg.set_env_var("CONVERT_SERIES", True)

    @classmethod
    def disable_convert_series(cls, delay: int = 0):
        time.sleep(delay)
        cls.print("Disabling convert series")
        cfg.set_env_var("CONVERT_SERIES", False)

    @classmethod
    def enable_backups(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Enabling backups")
        cfg.set_env_var("BACKUP", True)

    @classmethod
    def disable_backups(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Disabling backups")
        cfg.set_env_var("BACKUP", False)

    @classmethod
    def enable_debug(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Enabling debug")
        cfg.set_env_var("DEBUG", True)

    @classmethod
    def disable_debug(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Disabling debug")
        cfg.set_env_var("DEBUG", False)

    @classmethod
    def enable_archiving(cls, delay: int = 0):

        time.sleep(delay)
        cls.print("Enabling archiving")
        cfg.set_env_var("ON_COMPLETE", "archive")

    @classmethod
    def disable_archiving(cls, delay: int = 0):
        time.sleep(delay)
        cls.print("Disabling archiving")
        cfg.set_env_var("ON_COMPLETE", "test_do_nothing")

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
    def get_all_processed_books(
        cls, s: str, *, root_dir: Path = TEST_DIRS.inbox
    ) -> list[str]:
        lines = s.split("\n")
        books = []
        for i, line in enumerate(lines):
            if line.startswith("- Source: "):
                src = re_group(
                    re.search(rf"- Source: {root_dir}/(?P<book_key>.*$)", line),
                    "book_key",
                )
                if not lines[i + 1].startswith("- Output: "):
                    src = f"{src}{lines[i + 1].strip()}"
                books.append(src)
        return books

    @classmethod
    def assert_processed_books(
        cls,
        out: str | CaptureFixture[str],
        *books: Audiobook,
        check: list[check_output] | None = None,
        # converted: list[converted_books] | None = None,
        # ignoring: list[ignoring_books] | None = None,
    ) -> bool:

        if isinstance(out, CaptureFixture):
            out = cls.get_stdout(out)

        processed = cls.get_all_processed_books(out)
        did_process_all = all([book.key in processed for book in books])
        ok = did_process_all and len(processed) == len(books)
        books_list = f"\n{listify([book.key for book in books])}" if books else ""
        processed_list = f"\n{listify(processed)}" if processed else ""
        outs = out.split("CATS")[:-1] if "CATS" in out else [out]
        assert (
            ok
        ), f"Expected {len(books)} to be converted: {books_list}\n\nGot {len(processed)}: {processed_list}"

        def assert_found(i: int, ch: testutils.check_output, out_run: str = out):
            if all(
                f is None
                for f in [
                    ch.found_books_eq,
                    ch.found_books_gt,
                    # ch.found_books_gte,
                    # ch.found_books_lt,
                    # ch.found_books_lte,
                ]
            ):
                return
            all_founds = re.findall(r"(Found \d+.*? books?.*?)(?=\n)", out)
            all_found_counts = [
                int(
                    re_group(
                        re.search(r"Found (\d+) books?(?!.+but none\b)", x),
                        1,
                        default=0,
                    )
                )
                for x in all_founds
            ]
            this_found = all_found_counts[i]
            expected = ch.found_books_result()

            zero_ok = any(
                (
                    ch.found_books_eq == 0,
                    # ch.found_books_gte == 0,
                    # ch.found_books_lt is not None,
                    # ch.found_books_lte is not None,
                )
            )
            if zero_ok:
                assert (
                    this_found == 0
                ), f"Expected no books to be found, got {this_found}"
            elif this_found == 0:
                assert this_found > 0, f"Expected {expected}, but found none"
            else:
                try:
                    if ch.found_books_eq is not None:
                        assert this_found == ch.found_books_eq
                    else:
                        if ch.found_books_gt is not None:
                            assert this_found > ch.found_books_gt
                        # elif ch.found_books_gte is not None:
                        #     assert this_found >= ch.found_books_gte
                        # if ch.found_books_lt is not None:
                        #     assert this_found < ch.found_books_lt
                        # elif ch.found_books_lte is not None:
                        #     assert this_found <= ch.found_books_lte
                except AssertionError:
                    raise AssertionError(f"Expected {expected}, got {this_found}")
            if any(
                (
                    ch.found_books_eq is not None,
                    ch.found_books_gt,
                    # ch.found_books_gte,
                    # ch.found_books_lt is not None,
                    # ch.found_books_lte is not None,
                )
            ):
                assert len(outs) == len(
                    all_founds
                ), f"Expected {len(
                    outs
                )} 'found books' prints in output, got {len(all_founds)}"

        def assert_failed(i: int, ch: testutils.check_output, out_run: str = out):
            if all(
                c is None
                for c in [
                    ch.skipped_failed_eq,
                    ch.skipped_failed_gt,
                    # ch.failed_books_gte,
                    # ch.failed_books_lt,
                    # ch.failed_books_lte,
                ]
            ):
                return

            all_failed = len(re.findall(r"(\d+) that previously failed", out))
            this_failed = int(re_group(re.search(r"(\d+) that previously failed", out_run), 1, default=0))
            try:
                if ch.skipped_failed_eq is not None:
                    assert this_failed == ch.skipped_failed_eq
                else:
                    if ch.skipped_failed_gt is not None:
                        assert this_failed > ch.skipped_failed_gt
                    # elif ch.failed_books_gte is not None:
                    #     assert this_failed >= ch.failed_books_gte
                    # if ch.failed_books_lt is not None:
                    #     assert this_failed < ch.failed_books_lt
                    # elif ch.failed_books_lte is not None:
                    #     assert this_failed <= ch.failed_books_lte
            except AssertionError:
                # cls.print(out_run)
                expected = ch.failed_books_result()
                # actual = testutils.check_output(converted_eq=int(all_founds[i])).books_eq
                raise AssertionError(
                    f"Run {i + 1} - expected {expected} to have failed, got {this_failed} (total failed: {all_failed})"
                )


        def assert_ignored(i: int, ch: testutils.check_output, out_run: str = out):
            if all(
                c is None
                for c in [
                    ch.ignored_books_eq,
                    ch.ignored_books_gt,
                    # ch.ignored_books_gte,
                    # ch.ignored_books_lt,
                    # ch.ignored_books_lte,
                ]
            ):
                return

            all_ignored = len(re.findall(r"ignoring (\d+)", out))
            this_ignored = int(re_group(re.search(r"ignoring (\d+)", out_run), 1, default=0))
            try:
                if ch.ignored_books_eq is not None:
                    assert this_ignored == ch.ignored_books_eq
                else:
                    if ch.ignored_books_gt is not None:
                        assert this_ignored > ch.ignored_books_gt
                    # elif ch.ignored_books_gte is not None:
                    #     assert this_ignored >= ch.ignored_books_gte
                    # if ch.ignored_books_lt is not None:
                    #     assert this_ignored < ch.ignored_books_lt
                    # elif ch.ignored_books_lte is not None:
                    #     assert this_ignored <= ch.ignored_books_lte
            except AssertionError:
                # cls.print(out_run)
                expected = ch.ignored_books_result()
                # actual = testutils.check_output(converted_eq=int(all_founds[i])).books_eq
                raise AssertionError(
                    f"Run {i + 1} - expected {expected} to be ignored, got {this_ignored} (total ignored: {all_ignored})"
                )

        def assert_retried(
            i: int, t: int, ch: testutils.check_output, out_run: str = out
        ):
            if all(
                c is None
                for c in [
                    ch.retried_books_eq,
                    ch.retried_books_gt,
                    # ch.retried_books_gte,
                    # ch.retried_books_lt,
                    # ch.retried_books_lte,
                ]
            ):
                return

            all_retried = len(re.findall(r"trying again", out))
            this_retried = len(re.findall(r"trying again", out_run))
            try:
                if ch.retried_books_eq is not None:
                    assert this_retried == ch.retried_books_eq
                else:
                    if ch.retried_books_gt is not None:
                        assert this_retried > ch.retried_books_gt
                    # elif ch.retried_gte is not None:
                    #     assert this_retried >= ch.retried_gte
                    # if ch.retried_lt is not None:
                    #     assert this_retried < ch.retried_lt
                    # elif ch.retried_lte is not None:
                    #     assert this_retried <= ch.retried_lte
            except AssertionError:
                # cls.print(out_run)
                expected = ch.retried_books_result()
                # actual = testutils.check_output(retried_eq=int(all_founds[i])).books_eq
                raise AssertionError(
                    f"Run {i + 1} of {t} - expected {expected} to retry, got {this_retried} (total retried: {all_retried})"
                )

        def assert_converted(
            i: int, t: int, ch: testutils.check_output, out_run: str = out
        ):
            if all(
                c is None
                for c in [
                    ch.converted_eq,
                    ch.converted_gt,
                    # ch.converted_gte,
                    # ch.converted_lt,
                    # ch.converted_lte,
                ]
            ):
                return

            all_converted = len(re.findall(r"Converted .* 🐾✨🥞", out))
            this_converted = len(re.findall(r"Converted .* 🐾✨🥞", out_run))
            try:
                if ch.converted_eq is not None:
                    assert this_converted == ch.converted_eq
                else:
                    if ch.converted_gt is not None:
                        assert this_converted > ch.converted_gt
                    # elif ch.converted_gte is not None:
                    #     assert this_converted >= ch.converted_gte
                    # if ch.converted_lt is not None:
                    #     assert this_converted < ch.converted_lt
                    # elif ch.converted_lte is not None:
                    #     assert this_converted <= ch.converted_lte
            except AssertionError:
                # cls.print(out_run)
                expected = ch.converted_books_result()
                # actual = testutils.check_output(converted_eq=int(all_founds[i])).books_eq
                raise AssertionError(
                    f"Run {i + 1} of {t} - expected {expected} to be converted, got {this_converted} (total converted: {all_converted})"
                )



        if check:
            for i, (ch, o) in enumerate(zip(check, outs)):
                assert_found(i, ch, o)
                assert_failed(i, ch, o)
                assert_ignored(i, ch, o)
                assert_retried(i, len(outs), ch, o)
                assert_converted(i, len(outs), ch, o)

        return ok

    @classmethod
    def assert_converted_book_and_collateral_exist(cls, book: Audiobook, quality: str):
        assert book.converted_dir.exists()
        m4b = book.converted_dir / f"{book.path.name}.m4b"
        assert m4b.exists()
        assert m4b.stat().st_size > 0
        log = book.converted_dir / f"auto-m4b.{book.path.name}.log"
        assert log.exists()
        assert log.stat().st_size > 0
        desc = book.converted_dir / f"{book.path.name} [{quality}].txt"
        assert desc.exists()
        assert desc.stat().st_size > 0
        return True
