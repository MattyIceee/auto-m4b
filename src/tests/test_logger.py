import re
from pathlib import Path

import pytest

from src.lib.audiobook import Audiobook
from src.lib.logger import log_results

FIRST_LINE = r"2023-10-21 22:37:37-0700\s{2,}SUCCESS\s{2,}Stephen Hawking - A Brief History of Time\s{2,}67 kb/s\s{2,}44.1 kHz\s{2,}\.mp3\s{2,}4 files\s{2,}80M\s{2,}-\s{2,}0:35"


def check(test_log: Path, expect_last_lines: list[str]):
    global FIRST_LINE
    with open(test_log, "r") as f:
        lines = f.readlines()
        header_line = lines[0]
        blank_line = True if lines[1].strip() == "" else False
        first_line = lines[2] if blank_line else lines[1]
        last_lines = lines[-len(expect_last_lines) :]

        assert list(map(str.strip, header_line.split())) == [
            "Date",
            "Result",
            "Original",
            "Folder",
            "Bitrate",
            "Sample",
            "Rate",
            "Type",
            "Files",
            "Size",
            "Duration",
            "Time",
        ]

        assert re.match(FIRST_LINE, first_line)

        # check that the last line of the log is the expected result
        for last_line, expect_last_line in zip(last_lines, expect_last_lines):
            assert last_line.startswith("20")
            assert (
                True
                if re.match(expect_last_line, last_line)
                else pytest.fail(f"\nExpected: {expect_last_line}\nGot: {last_line}")
            )


def check_ground_truth(test_log: Path):
    check(
        test_log,
        [
            r"2023-11-09 22:49:46-0800   SUCCESS   Say What You Mean A Mindful Approach to Nonviolent Communication by Or     64 kb/s      44.1 kHz   \.mp3    12 files   303M   11h:00m:11s   01:40"
        ],
    )


def test_load_existing_log(tower_treasure__flat_mp3: Audiobook, global_test_log: Path):
    check_ground_truth(global_test_log)

    log_results(tower_treasure__flat_mp3, "success", "02m:43s", global_test_log)
    assert global_test_log.exists()
    check(
        global_test_log,
        [
            r"^.*?-0800  SUCCESS  tower_treasure__flat_mp3                                                  64 kb/s     22.1 kHz   .mp3    5 files  22 MB   0h:46m:54s  02:43"
        ],
    )


def test_repeat_success_writes_to_log(
    tower_treasure__flat_mp3: Audiobook, global_test_log: Path
):
    check_ground_truth(global_test_log)

    log_results(tower_treasure__flat_mp3, "success", "02m:43s", global_test_log)
    assert global_test_log.exists()
    check(
        global_test_log,
        [
            r"^.*?-0800  SUCCESS  tower_treasure__flat_mp3                                                  64 kb/s     22.1 kHz   .mp3    5 files  22 MB   0h:46m:54s  02:43"
        ],
    )

    log_results(tower_treasure__flat_mp3, "success", "02m:43s", global_test_log)
    assert global_test_log.exists()
    check(
        global_test_log,
        [
            r"^.*?-0800  SUCCESS  tower_treasure__flat_mp3                                                  64 kb/s     22.1 kHz   .mp3    5 files  22 MB   0h:46m:54s  02:43"
        ],
    )


def test_repeat_failed_writes_to_log(
    tower_treasure__flat_mp3: Audiobook, global_test_log: Path
):
    check_ground_truth(global_test_log)

    orig_duration = tower_treasure__flat_mp3.duration
    orig_size = tower_treasure__flat_mp3.size
    tower_treasure__flat_mp3.__dict__["duration"] = lambda *args, **kwargs: ""
    tower_treasure__flat_mp3.__dict__["size"] = lambda *args, **kwargs: "1.25 GB"
    log_results(tower_treasure__flat_mp3, "failed", "", global_test_log)
    assert global_test_log.exists()
    check(
        global_test_log,
        [
            r"^.*?-0800  FAILED   tower_treasure__flat_mp3                                                  64 kb/s     22.1 kHz   .mp3    5 files  1.25 GB            -"
        ],
    )

    tower_treasure__flat_mp3.__dict__["duration"] = orig_duration
    tower_treasure__flat_mp3.__dict__["size"] = orig_size
    log_results(tower_treasure__flat_mp3, "success", "02m:43s", global_test_log)
    assert global_test_log.exists()
    check(
        global_test_log,
        [
            r"^.*?-0800  FAILED   tower_treasure__flat_mp3                                                  64 kb/s     22.1 kHz   .mp3    5 files  1.25 GB            -      -",
            r"^.*?-0800  SUCCESS  tower_treasure__flat_mp3                                                  64 kb/s     22.1 kHz   .mp3    5 files    22 MB   0h:46m:54s  02:43",
        ],
    )
