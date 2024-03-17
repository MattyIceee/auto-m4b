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
from src.tests.conftest import TEST_CONVERTED


def test_tower_treasure__flat_mp3(tower_treasure__flat_mp3: Audiobook):

    app(max_loops=1, no_fix=True, test=True)
    assert tower_treasure__flat_mp3.converted_dir.exists()


def test_house_on_the_cliff__flat_mp3(house_on_the_cliff__flat_mp3: Audiobook):

    app(max_loops=1, no_fix=True, test=True)
    assert house_on_the_cliff__flat_mp3.converted_dir.exists()


def test_bad_bitrate__mp3(the_crusades_through_arab_eyes__flat_mp3: Audiobook):

    app(max_loops=1, no_fix=True, test=True)
    assert the_crusades_through_arab_eyes__flat_mp3.converted_dir.exists()


def test_roman_numerals__mp3(roman_numeral__mp3: Audiobook, capfd: CaptureFixture[str]):

    app(max_loops=1, no_fix=True, test=True)
    msg = "Error: Some of this book's files appear to be named with roman numerals"
    stdout, _ = capfd.readouterr()
    assert msg in stdout


def test_failed_book_displays_only_once(
    roman_numeral__mp3: Audiobook, capfd: CaptureFixture[str]
):

    app(max_loops=3, no_fix=True, test=True)
    msg = "Error: Some of this book's files appear to be named with roman numerals"
    stdout, _ = capfd.readouterr()
    # the message should only appear once
    assert stdout.count(msg) == 1


def test_header_only_prints_when_there_are_books_to_process(
    tower_treasure__flat_mp3: Audiobook, capfd: CaptureFixture[str]
):

    os.environ["MATCH_NAME"] = "test-do-not-match"
    app(max_loops=10, no_fix=True, test=True)

    msg = "auto-m4b • "
    stdout, _ = capfd.readouterr()
    # the message should only appear once
    assert stdout.count(msg) == 1


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
    time.sleep(2)

    app(max_loops=2, no_fix=True, test=True)
    assert conspiracy_theories__flat_mp3_copy.converted_dir.exists()


def test_hardy_boys__flat_mp3s(
    tower_treasure__flat_mp3: Audiobook, house_on_the_cliff__flat_mp3: Audiobook
):

    app(max_loops=1, no_fix=True, test=True)
    assert tower_treasure__flat_mp3.converted_dir.exists()
    assert house_on_the_cliff__flat_mp3.converted_dir.exists()
