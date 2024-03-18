import asyncio
import os
import shutil
import time
from collections.abc import Callable, Coroutine
from copy import deepcopy
from typing import Any

from pytest import CaptureFixture

from src.auto_m4b import app
from src.lib.audiobook import Audiobook
from src.tests.conftest import strip_ansi_codes, TEST_CONVERTED, TEST_INBOX


def get_output(capfd: CaptureFixture[str]) -> str:
    return strip_ansi_codes(capfd.readouterr().out)


def test_tower_treasure__flat_mp3(tower_treasure__flat_mp3: Audiobook):

    app(max_loops=1, no_fix=True, test=True)
    assert tower_treasure__flat_mp3.converted_dir.exists()


def test_house_on_the_cliff__flat_mp3(house_on_the_cliff__flat_mp3: Audiobook):

    app(max_loops=1, no_fix=True, test=True)
    assert house_on_the_cliff__flat_mp3.converted_dir.exists()


def test_bad_bitrate__mp3(the_crusades_through_arab_eyes__flat_mp3: Audiobook):

    app(max_loops=1, no_fix=True, test=True)
    assert the_crusades_through_arab_eyes__flat_mp3.converted_dir.exists()


def test_roman_numerals_and_failed_books_only_print_once(
    roman_numeral__mp3: Audiobook, capfd: CaptureFixture[str]
):

    app(max_loops=3, no_fix=True, test=True)
    msg = "Error: Some of this book's files appear to be named with roman numerals"
    # assert the message only appears once
    assert capfd.readouterr().out.count(msg) == 1


def test_match_name_has_no_matches(
    tower_treasure__flat_mp3: Audiobook, capfd: CaptureFixture[str]
):

    os.environ["MATCH_NAME"] = "test-do-not-match"
    app(max_loops=4, no_fix=True, test=True)
    assert capfd.readouterr().out.count("but none match") == 1


def test_failed_books_show_as_skipped(
    roman_numeral__mp3: Audiobook,
    tower_treasure__flat_mp3: Audiobook,
    capfd: CaptureFixture[str],
):

    os.environ["MATCH_NAME"] = "^(Roman|tower)"
    app(max_loops=2, no_fix=True, test=True)
    out = get_output(capfd)
    assert out.count("2 books in the inbox") == 1
    assert out.count("named with roman numerals") == 1
    assert out.count("Converted tower_treasure__flat_mp3") == 1
    os.environ["FAILED_BOOKS"] = '{"Roman Numeral Book": %s}' % str(time.time() + 30)
    TEST_INBOX.touch()
    app(max_loops=4, no_fix=True, test=True)
    out = get_output(capfd)
    assert out.count("1 book in the inbox") == 1
    assert out.count("named with roman numerals") == 0
    assert out.count("skipping 1 that previously failed") == 1
    assert out.count("Converted tower_treasure__flat_mp3") == 1


def test_failed_books_retry_if_touched(
    roman_numeral__mp3: Audiobook,
    tower_treasure__flat_mp3: Audiobook,
    capfd: CaptureFixture[str],
):

    os.environ["MATCH_NAME"] = "^(Roman|tower)"
    app(max_loops=2, no_fix=True, test=True)
    out = get_output(capfd)
    assert out.count("2 books in the inbox") == 1
    assert out.count("named with roman numerals") == 1
    os.environ["FAILED_BOOKS"] = '{"Roman Numeral Book": %s}' % str(time.time() + 30)
    TEST_INBOX.touch()
    app(max_loops=4, no_fix=True, test=True)
    out = get_output(capfd)
    assert out.count("skipping 1 that previously failed") == 1
    (TEST_INBOX / "Roman Numeral Book").touch()
    TEST_INBOX.touch()
    app(max_loops=6, no_fix=True, test=True)
    out = get_output(capfd)
    assert out.count("named with roman numerals") == 1


def test_failed_books_retry_when_fixed(
    tower_treasure__multidisc_mp3: Audiobook,
    capfd: CaptureFixture[str],
):

    shutil.rmtree(tower_treasure__multidisc_mp3.converted_dir, ignore_errors=True)
    # remove all mp3 files in the root dir of tower_treasure__multidisc_mp3 (no nested dirs)
    for f in tower_treasure__multidisc_mp3.inbox_dir.iterdir():
        if f.is_file() and f.suffix == ".mp3":
            f.unlink()
    app(max_loops=2, no_fix=True, test=True)
    out = get_output(capfd)
    assert out.count("multi-disc") == 1
    os.environ["FAILED_BOOKS"] = '{"tower_treasure__multidisc_mp3": %s}' % str(
        time.time() + 30
    )
    app(max_loops=4, no_fix=True, test=True)
    out = get_output(capfd)
    assert out.count("multi-disc") == 0
    last_touched = tower_treasure__multidisc_mp3.inbox_dir.stat().st_mtime
    # find all audio files in tower_treasure__multidisc_mp3.inbox_dir and move them to the root of it

    async def async_app():
        os.environ["FAILED_BOOKS"] = '{"tower_treasure__multidisc_mp3": %s}' % str(
            time.time() + 30
        )
        app(max_loops=10, no_fix=True, test=True)

    async def wrapper():
        task = asyncio.create_task(async_app())
        await asyncio.sleep(1)
        # when task is done, assert converted dir exists
        await task

        # assert tower_treasure__multidisc_mp3.converted_dir.exists()

    asyncio.run(wrapper())

    for f in tower_treasure__multidisc_mp3.inbox_dir.rglob("*"):
        if f.is_file():
            f.rename(tower_treasure__multidisc_mp3.inbox_dir / f.name)

    assert tower_treasure__multidisc_mp3.inbox_dir.stat().st_mtime > last_touched
    shutil.rmtree(tower_treasure__multidisc_mp3.inbox_dir, ignore_errors=True)


def test_header_only_prints_when_there_are_books_to_process(
    tower_treasure__flat_mp3: Audiobook, capfd: CaptureFixture[str]
):

    os.environ["MATCH_NAME"] = "test-do-not-match"
    app(max_loops=10, no_fix=True, test=True)

    msg = "auto-m4b • "
    # the message should only appear once
    assert capfd.readouterr().out.count(msg) == 1


def test_app_waits_while_inbox_updates_then_processes(
    tower_treasure__flat_mp3: Audiobook,
    mock_inbox_being_copied_to: Callable[[int], Coroutine[Any, Any, None]],
    capfd: CaptureFixture[str],
):

    async def wrapper():
        asyncio.create_task(mock_inbox_being_copied_to(5))

    time.sleep(1)
    asyncio.run(wrapper())
    app(max_loops=1, no_fix=True, test=True)
    # time.sleep(1)
    inbox_msg = "recently modified, waiting"
    book_msg = "Skipping this book, it was recently"
    stdout, _ = capfd.readouterr()
    # the message should only appear once
    assert stdout.count(inbox_msg) == 1
    assert stdout.count(book_msg) == 0


def test_secret_project_series__nested_flat_mixed(
    secret_project_series__nested_flat_mixed: Audiobook, capfd: CaptureFixture[str]
):

    app(max_loops=1, no_fix=True, test=True)
    romans_msg = (
        "Error: Some of this book's files appear to be named with roman numerals"
    )
    nested_msg = "This book contains multiple folders with audio files"
    stdout, _ = capfd.readouterr()
    assert romans_msg not in stdout
    assert nested_msg in stdout


def test_long_filename__mp3(conspiracy_theories__flat_mp3: Audiobook):
    conspiracy_theories__flat_mp3_copy = deepcopy(conspiracy_theories__flat_mp3)
    (TEST_CONVERTED / "auto-m4b.log").unlink(
        missing_ok=True
    )  # remove the log file to force a conversion
    os.environ["MATCH_NAME"] = "Conspiracies"
    app(max_loops=1, no_fix=True, test=True)
    assert conspiracy_theories__flat_mp3.converted_dir.exists()
    # do the conversion again to test the log file
    shutil.rmtree(conspiracy_theories__flat_mp3.converted_dir, ignore_errors=True)
    TEST_INBOX.touch()
    time.sleep(1)

    app(max_loops=2, no_fix=True, test=True)
    assert conspiracy_theories__flat_mp3_copy.converted_dir.exists()


def test_hardy_boys__flat_mp3s(
    tower_treasure__flat_mp3: Audiobook, house_on_the_cliff__flat_mp3: Audiobook
):

    os.environ["MATCH_NAME"] = "^(tower|house)"
    app(max_loops=1, no_fix=True, test=True)
    assert tower_treasure__flat_mp3.converted_dir.exists()
    assert house_on_the_cliff__flat_mp3.converted_dir.exists()
