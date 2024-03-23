import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.lib.misc import get_git_root

GIT_ROOT = get_git_root()
SRC_ROOT = Path(__file__).parent.parent
TESTS_ROOT = Path(__file__).parent
TESTS_TMP_ROOT = TESTS_ROOT / "tmp"
FIXTURES_ROOT = TESTS_ROOT / "fixtures"


@dataclass
class TEST_DIRS:

    inbox = TESTS_TMP_ROOT / "inbox"
    converted = TESTS_TMP_ROOT / "converted"
    archive = TESTS_TMP_ROOT / "archive"
    fix = TESTS_TMP_ROOT / "fix"
    backup = TESTS_TMP_ROOT / "backup"
    working = TESTS_TMP_ROOT / "working"


from src.tests.helpers.pytest_fixtures import *
