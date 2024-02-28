import re
import shutil

from src.lib.audiobook import Audiobook
from src.lib.logger import log_results
from src.tests.conftest import FIXTURES_ROOT, TESTS_TMP_ROOT


def test_load_existing_log(tower_treasure__flat_mp3: Audiobook):
    # make a working copy of the log file in TESTS_ROOT

    def check(full_line: str):
        with open(test_log, "r") as f:
            lines = f.readlines()
            last_line = lines[-1]

        # check that the last line of the log is the expected result
        assert last_line.startswith("20")
        assert re.match(full_line, last_line)

    try:
        orig_log = FIXTURES_ROOT / "auto-m4b.log"
        test_log = TESTS_TMP_ROOT / "auto-m4b.log"
        test_log.unlink(missing_ok=True)
        shutil.copy2(orig_log, test_log)

        check(
            r"2023-11-09 22:49:46-0800   SUCCESS   Say What You Mean A Mindful Approach to Nonviolent Communication by Or     64 kb/s      44.1 kHz   .mp3    12 files   303M   11h:00m:11s   01:40"
        )

        log_results(tower_treasure__flat_mp3, "success", "02m:43s", test_log)
        assert test_log.exists()
        check(
            r"^.*?-0800  SUCCESS  tower_treasure__flat_mp3                                                  64 kb/s     22.1 kHz   .mp3    5 files  22 MB   0h:46m:54s  01:40"
        )

    finally:
        # clean up
        test_log.unlink(missing_ok=True)
