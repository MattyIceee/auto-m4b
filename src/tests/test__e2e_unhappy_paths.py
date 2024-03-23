import asyncio
import concurrent
import concurrent.futures
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
from src.lib.run import flush_inbox_hash
from src.tests.conftest import TEST_DIRS
from src.tests.helpers.pytest_utils import testutils


async def run_app_for__failed_books_retry_when_fixed():
    prev_sleep = os.environ.get("SLEEPTIME")
    os.environ["SLEEPTIME"] = "2"
    testutils.print("Starting app...")
    app(max_loops=4, no_fix=True, test=True)
    testutils.print("Finished app")
    if prev_sleep:
        os.environ["SLEEPTIME"] = prev_sleep


@pytest.mark.slow
class test_unhappy_paths:

    @pytest.mark.order(1)
    def test_bad_bitrate__mp3(
        self, the_crusades_through_arab_eyes__flat_mp3: Audiobook
    ):

        app(max_loops=1, no_fix=True, test=True)
        assert the_crusades_through_arab_eyes__flat_mp3.converted_dir.exists()

    @pytest.mark.order(2)
    def test_roman_numerals_and_failed_books_only_print_once(
        self, roman_numeral__mp3: Audiobook, capfd: CaptureFixture[str]
    ):

        app(max_loops=3, no_fix=True, test=True)
        msg = "Error: Some of this book's files appear to be named with roman numerals"
        # assert the message only appears once
        assert capfd.readouterr().out.count(msg) == 1

    @pytest.mark.order(3)
    def test_match_name_has_no_matches(
        self, tower_treasure__flat_mp3: Audiobook, capfd: CaptureFixture[str]
    ):

        testutils.set_match_name("test-do-not-match")
        app(max_loops=4, no_fix=True, test=True)
        assert capfd.readouterr().out.count("but none match") == 1

    @pytest.mark.order(4)
    def test_failed_books_show_as_skipped(
        self,
        roman_numeral__mp3: Audiobook,
        tower_treasure__flat_mp3: Audiobook,
        capfd: CaptureFixture[str],
    ):

        testutils.set_match_name("^(Roman|tower)")
        app(max_loops=2, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count("2 books in the inbox") == 1
        assert out.count("named with roman numerals") == 1
        assert out.count("Converted tower_treasure__flat_mp3") == 1
        testutils.fail_book(roman_numeral__mp3, from_now=30)
        flush_inbox_hash()
        time.sleep(2)
        app(max_loops=4, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count("2 books in the inbox") == 1
        assert out.count("named with roman numerals") == 0
        assert out.count("skipping 1 that previously failed") == 1
        assert out.count("Converted tower_treasure__flat_mp3") == 1

    @pytest.mark.order(5)
    def test_failed_books_skip_if_unchanged(
        self,
        roman_numeral__mp3: Audiobook,
        tower_treasure__flat_mp3: Audiobook,
        house_on_the_cliff__flat_mp3: Audiobook,
        capfd: CaptureFixture[str],
    ):

        from src.lib.config import cfg
        from src.lib.run import flush_inbox_hash

        testutils.set_match_name("^(Roman|tower)")
        app(max_loops=1, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count("2 books in the inbox") == 1
        assert out.count("named with roman numerals") == 1
        testutils.fail_book("Roman Numeral Book", from_now=30)
        TEST_DIRS.inbox.touch()
        testutils.set_match_name("^(Roman|tower|house)")
        # time.sleep(2)
        flush_inbox_hash()
        app(max_loops=3, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count("skipping 1 that previously failed") == 1
        (TEST_DIRS.inbox / "Roman Numeral Book").touch()
        TEST_DIRS.inbox.touch()
        cfg.DEBUG = True
        app(max_loops=2, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count("Skipping this loop, inbox hash is the same") == 2

    @pytest.mark.order(6)
    @pytest.mark.asyncio
    async def test_failed_books_retry_when_fixed(
        self, old_mill__multidisc_mp3: Audiobook, capfd: CaptureFixture[str]
    ):
        inbox_dir = old_mill__multidisc_mp3.inbox_dir
        converted_dir = old_mill__multidisc_mp3.converted_dir
        shutil.rmtree(converted_dir, ignore_errors=True)

        app_task = asyncio.create_task(run_app_for__failed_books_retry_when_fixed())

        with concurrent.futures.ThreadPoolExecutor() as executor:
            await asyncio.get_running_loop().run_in_executor(
                executor, testutils.flatten_book, old_mill__multidisc_mp3, 5
            )

        await app_task
        assert converted_dir.exists()
        assert testutils.get_stdout(capfd).count("trying again") == 1
        shutil.rmtree(inbox_dir, ignore_errors=True)

    @pytest.mark.order(7)
    def test_header_only_prints_when_there_are_books_to_process(
        self, tower_treasure__flat_mp3: Audiobook, capfd: CaptureFixture[str]
    ):
        testutils.set_match_name("test-do-not-match")
        app(max_loops=10, no_fix=True, test=True)

        msg = "auto-m4b • "
        assert capfd.readouterr().out.count(msg) == 1

    @pytest.mark.order(8)
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
        inbox_msg = "recently modified, waiting"
        book_msg = "Skipping this book, it was recently"
        stdout, _ = capfd.readouterr()
        assert stdout.count(inbox_msg) == 1
        assert stdout.count(book_msg) == 0

    @pytest.mark.order(9)
    def test_secret_project_series__nested_flat_mixed(
        self,
        secret_project_series__nested_flat_mixed: Audiobook,
        capfd: CaptureFixture[str],
    ):

        app(max_loops=1, no_fix=True, test=True)
        romans_msg = (
            "Error: Some of this book's files appear to be named with roman numerals"
        )
        nested_msg = "This book contains multiple folders with audio files"
        stdout, _ = capfd.readouterr()
        assert romans_msg not in stdout
        assert nested_msg in stdout

    @pytest.mark.order(10)
    def test_long_filename__mp3(self, conspiracy_theories__flat_mp3: Audiobook):
        conspiracy_theories__flat_mp3_copy = deepcopy(conspiracy_theories__flat_mp3)
        (TEST_DIRS.converted / "auto-m4b.log").unlink(
            missing_ok=True
        )  # remove the log file to force a conversion
        testutils.set_match_name("Conspiracies")
        app(max_loops=1, no_fix=True, test=True)
        assert conspiracy_theories__flat_mp3.converted_dir.exists()
        # do the conversion again to test the log file
        flush_inbox_hash()
        shutil.rmtree(conspiracy_theories__flat_mp3.converted_dir, ignore_errors=True)
        TEST_DIRS.inbox.touch()
        time.sleep(1)

        app(max_loops=2, no_fix=True, test=True)
        assert conspiracy_theories__flat_mp3_copy.converted_dir.exists()

    @pytest.mark.order(11)
    def test_multi_disc_fails(
        self,
        old_mill__multidisc_mp3: Audiobook,
        capfd: CaptureFixture[str],
    ):

        shutil.rmtree(old_mill__multidisc_mp3.converted_dir, ignore_errors=True)
        time.sleep(2)
        app(max_loops=2, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count("multi-disc") == 1

    @pytest.mark.order(12)
    def test_inbox_doesnt_update_if_book_fails(
        self,
        old_mill__multidisc_mp3: Audiobook,
        capfd: CaptureFixture[str],
    ):
        wait_msg = "The inbox folder was recently modified, waiting"
        time.sleep(2)
        app(max_loops=1, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count(wait_msg) == 0
        assert out.count("multi-disc") == 1
        assert out.count("inbox hash is the same") == 0
        time.sleep(1)
        app(max_loops=1, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert out.count("inbox hash is the same") == 1
        assert out.count("multi-disc") == 0
        assert out.count(wait_msg) == 0
