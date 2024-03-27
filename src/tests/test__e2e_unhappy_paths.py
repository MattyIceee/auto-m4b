import asyncio
import concurrent
import concurrent.futures
import functools
import os
import shutil
import time
from collections.abc import Callable, Coroutine
from copy import deepcopy
from typing import Any

import pytest
from pytest import CaptureFixture

from src.auto_m4b import app
from src.lib.audiobook import Audiobook
from src.lib.inbox_state import InboxState
from src.lib.strings import en
from src.tests.conftest import TEST_DIRS
from src.tests.helpers.pytest_utils import testutils

ORDER = 1


@pytest.mark.slow
class test_unhappy_paths:

    @pytest.fixture(scope="function", autouse=True)
    def setup(self, reset_inbox_state):
        yield

    @pytest.mark.order(ORDER)
    def test_nonstandard_bitrates__mp3(
        self,
        bitrate_nonstandard__mp3: Audiobook,
        the_crusades_through_arab_eyes__flat_mp3: Audiobook,
        capfd: CaptureFixture[str],
    ):

        testutils.set_match_filter("^(bitrate_nonstandard|the_crusades)")
        app(max_loops=1, no_fix=True, test=True)
        assert testutils.assert_only_processed_books(
            capfd,
            bitrate_nonstandard__mp3,
            the_crusades_through_arab_eyes__flat_mp3,
            found=(2, 1),
            converted=2,
        )
        assert bitrate_nonstandard__mp3.converted_dir.exists()
        assert the_crusades_through_arab_eyes__flat_mp3.converted_dir.exists()

    ORDER += 1

    @pytest.mark.order(ORDER)
    def test_roman_numerals_and_failed_books_only_print_once(
        self, roman_numeral__mp3: Audiobook, capfd: CaptureFixture[str]
    ):

        app(max_loops=3, no_fix=True, test=True)
        # assert the message only appears once
        assert capfd.readouterr().out.count(en.ROMAN_ERR) == 1

    ORDER += 1

    @pytest.mark.order(ORDER)
    def test_match_name_has_no_matches(
        self, tower_treasure__flat_mp3: Audiobook, capfd: CaptureFixture[str]
    ):

        testutils.set_match_filter("test-do-not-match")
        app(max_loops=4, no_fix=True, test=True)
        assert capfd.readouterr().out.count("but none match") == 1

    ORDER += 1

    @pytest.mark.order(ORDER)
    def test_skip_known_failed_books(
        self,
        roman_numeral__mp3: Audiobook,
        tower_treasure__flat_mp3: Audiobook,
        capfd: CaptureFixture[str],
    ):
        inbox = InboxState()

        testutils.set_match_filter("^(Roman|tower)")
        app(max_loops=2, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        # assert out.count("2 books in the inbox") == 1
        # assert out.count("Converted tower_treasure__flat_mp3") == 1

        assert testutils.assert_only_processed_books(
            out,
            tower_treasure__flat_mp3,
            found=(2, 1),
            converted=1,
        )
        assert out.count("named with roman numerals") == 1

        testutils.fail_book(roman_numeral__mp3, from_now=30)
        # inbox.flush_global_hash()
        inbox.reset()
        time.sleep(1)
        app(max_loops=4, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)

        assert testutils.assert_only_processed_books(
            out,
            tower_treasure__flat_mp3,
            found=(2, 1),
            converted=1,
        )
        # assert out.count("2 books in the inbox") == 1
        assert out.count("named with roman numerals") == 0
        assert out.count("skipping 1 that previously failed") == 1
        # assert out.count("Converted tower_treasure__flat_mp3") == 1

    ORDER += 1

    @pytest.mark.order(ORDER)
    def test_ignore_failed_books_if_unchanged(
        self,
        roman_numeral__mp3: Audiobook,
        tower_treasure__flat_mp3: Audiobook,
        house_on_the_cliff__flat_mp3: Audiobook,
        capfd: CaptureFixture[str],
    ):

        from src.lib.config import cfg

        inbox = InboxState()

        testutils.set_match_filter("^(Roman|tower)")
        app(max_loops=1, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count("2 books in the inbox") == 1
        assert out.count("named with roman numerals") == 1
        testutils.fail_book("Roman Numeral Book", from_now=30)
        TEST_DIRS.inbox.touch()
        testutils.set_match_filter("^(Roman|tower|house)")
        # time.sleep(2)
        inbox.flush_global_hash()
        app(max_loops=3, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count("skipping 1 that previously failed") == 1
        (TEST_DIRS.inbox / "Roman Numeral Book").touch()
        TEST_DIRS.inbox.touch()
        cfg.DEBUG = True
        app(max_loops=2, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count("Skipping this loop, inbox hash is the same") > 0

    ORDER += 1

    async def run_app_for__failed_books_skip_when_new_books_added(self):
        prev_sleep = os.environ.get("SLEEPTIME")
        testutils.set_sleeptime(2)
        testutils.print("Starting app...")
        testutils.set_match_filter("chums")
        app(max_loops=4, no_fix=True, test=False)
        testutils.print("Finished app")
        if prev_sleep:
            testutils.set_sleeptime(prev_sleep)

    def add_books__failed_books_skip_when_new_books_added(
        self, *books: Audiobook, append: str = "", rstrip: str = ""
    ):
        time.sleep(3)
        testutils.set_match_filter("^(chums|tower)")
        for book in books:
            testutils.rename_files(book, append=append, rstrip=rstrip)
        (TEST_DIRS.inbox / "missing_chums__mixed_mp3").touch()
        # time.sleep(1)

    @pytest.mark.asyncio
    async def test_failed_books_skip_when_new_books_added(
        self,
        missing_chums__mixed_mp3: Audiobook,
        tower_treasure__flat_mp3: Audiobook,
        # house_on_the_cliff__flat_mp3: Audiobook,
        capfd: CaptureFixture[str],
    ):

        app_task = asyncio.create_task(
            self.run_app_for__failed_books_skip_when_new_books_added()
        )

        rename1 = functools.partial(
            self.add_books__failed_books_skip_when_new_books_added,
            tower_treasure__flat_mp3,
            # house_on_the_cliff__flat_mp3,
            append="-new1",
            rstrip=r"-new\d",
        )

        rename2 = functools.partial(
            self.add_books__failed_books_skip_when_new_books_added,
            tower_treasure__flat_mp3,
            # house_on_the_cliff__flat_mp3,
            append="-new2",
            rstrip=r"-new\d",
        )

        with concurrent.futures.ThreadPoolExecutor() as executor:
            await asyncio.get_running_loop().run_in_executor(executor, rename1)
            await asyncio.get_running_loop().run_in_executor(executor, rename2)

        await app_task
        # assert converted_dir.exists()
        # assert testutils.get_stdout(capfd).count("trying again") == 1
        # shutil.rmtree(inbox_dir, ignore_errors=True)

    ORDER += 1

    async def run_app_for__retries_failed_books_when_changed(self):
        prev_sleep = os.environ.get("SLEEPTIME")
        testutils.set_sleeptime(2)
        testutils.print("Starting app...")
        app(max_loops=4, no_fix=True, test=True)
        testutils.print("Finished app")
        if prev_sleep:
            testutils.set_sleeptime(prev_sleep)

    @pytest.mark.order(ORDER)
    @pytest.mark.asyncio
    async def test_retries_failed_books_when_changed(
        self, old_mill__multidisc_mp3: Audiobook, capfd: CaptureFixture[str]
    ):
        testutils.disable_autoflatten()
        inbox_dir = old_mill__multidisc_mp3.inbox_dir
        converted_dir = old_mill__multidisc_mp3.converted_dir
        shutil.rmtree(converted_dir, ignore_errors=True)

        app_task = asyncio.create_task(
            self.run_app_for__retries_failed_books_when_changed()
        )

        with concurrent.futures.ThreadPoolExecutor() as executor:
            await asyncio.get_running_loop().run_in_executor(
                executor, testutils.flatten_book, old_mill__multidisc_mp3, 5
            )

        await app_task
        assert converted_dir.exists()
        assert testutils.get_stdout(capfd).count("trying again") == 1
        shutil.rmtree(inbox_dir, ignore_errors=True)

    ORDER += 1

    @pytest.mark.order(ORDER)
    def test_header_only_prints_when_there_are_books_to_process(
        self, tower_treasure__flat_mp3: Audiobook, capfd: CaptureFixture[str]
    ):
        testutils.set_match_filter("test-do-not-match")
        app(max_loops=10, no_fix=True, test=True)

        msg = "auto-m4b • "
        assert capfd.readouterr().out.count(msg) == 1

    ORDER += 1

    @pytest.mark.order(ORDER)
    def test_app_waits_while_inbox_updates_then_processes(
        self,
        tower_treasure__flat_mp3: Audiobook,
        mock_inbox_being_copied_to: Callable[[int], Coroutine[Any, Any, None]],
        capfd: CaptureFixture[str],
    ):

        async def wrapper():
            asyncio.create_task(mock_inbox_being_copied_to(5))

        time.sleep(1)
        asyncio.run(wrapper())
        app(max_loops=1, no_fix=True, test=True)
        book_msg = "Skipping this book, it was recently"
        stdout, _ = capfd.readouterr()
        assert stdout.count(en.INBOX_RECENTLY_MODIFIED) == 1
        assert stdout.count(book_msg) == 0

    ORDER += 1

    @pytest.mark.order(ORDER)
    def test_secret_project_series__nested_flat_mixed(
        self,
        secret_project_series__nested_flat_mixed: Audiobook,
        capfd: CaptureFixture[str],
    ):

        app(max_loops=1, no_fix=True, test=True)
        romans_msg = (
            "Error: Some of this book's files appear to be named with roman numerals"
        )
        stdout, _ = capfd.readouterr()
        assert romans_msg not in stdout
        assert en.MULTI_ERR in stdout

    ORDER += 1

    @pytest.mark.order(ORDER)
    def test_long_filename__mp3(self, conspiracy_theories__flat_mp3: Audiobook):
        inbox = InboxState()

        conspiracy_theories__flat_mp3_copy = deepcopy(conspiracy_theories__flat_mp3)
        (TEST_DIRS.converted / "auto-m4b.log").unlink(
            missing_ok=True
        )  # remove the log file to force a conversion
        testutils.set_match_filter("Conspiracies")
        app(max_loops=1, no_fix=True, test=True)
        assert conspiracy_theories__flat_mp3.converted_dir.exists()
        # do the conversion again to test the log file
        inbox.flush_global_hash()
        shutil.rmtree(conspiracy_theories__flat_mp3.converted_dir, ignore_errors=True)
        TEST_DIRS.inbox.touch()
        time.sleep(1)

        app(max_loops=2, no_fix=True, test=True)
        assert conspiracy_theories__flat_mp3_copy.converted_dir.exists()

    ORDER += 1

    @pytest.mark.order(ORDER)
    def test_multi_disc_fails(
        self,
        old_mill__multidisc_mp3: Audiobook,
        capfd: CaptureFixture[str],
    ):

        testutils.disable_autoflatten()
        shutil.rmtree(old_mill__multidisc_mp3.converted_dir, ignore_errors=True)
        time.sleep(2)
        app(max_loops=2, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count(en.MULTI_ERR) == 1
        assert not old_mill__multidisc_mp3.converted_dir.exists()

    ORDER += 1

    @pytest.mark.order(ORDER)
    def test_inbox_doesnt_update_if_book_fails(
        self,
        old_mill__multidisc_mp3: Audiobook,
        capfd: CaptureFixture[str],
    ):
        testutils.disable_autoflatten()
        testutils.enable_debug()
        time.sleep(2)
        app(max_loops=1, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count("inbox hash is the same") == 0
        assert out.count(en.DONE_CONVERTING) == 1
        assert out.count(en.MULTI_ERR) == 1
        assert out.count(en.INBOX_RECENTLY_MODIFIED) == 0

        time.sleep(1)
        app(max_loops=1, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count("inbox hash is the same") == 1
        assert out.count(en.DONE_CONVERTING) == 0
        assert out.count(en.MULTI_ERR) == 0
        assert out.count(en.INBOX_RECENTLY_MODIFIED) == 0

    ORDER += 1

    @pytest.mark.order(ORDER)
    def test_debug_prints_dont_repeat_when_inbox_is_empty(
        self,
        capfd: CaptureFixture[str],
    ):
        inbox_hidden = TEST_DIRS.inbox.parent / "inbox-hidden"

        # hide inbox
        if not inbox_hidden.exists():
            TEST_DIRS.inbox.rename(inbox_hidden)
        elif list(TEST_DIRS.inbox.glob("*")):
            pytest.fail(
                "Inbox is not empty and inbox-hidden exists, cannot run this test. Please empty the inbox or delete inbox-hidden"
            )

        try:
            app(max_loops=5, no_fix=True, test=True)
            out = testutils.get_stdout(capfd)
            assert out.count("No audio files found") == 1
        finally:
            # unhide inbox
            inbox_hidden.rename(TEST_DIRS.inbox)
