import re
import shutil

import pytest
from pytest import CaptureFixture

from src.auto_m4b import app
from src.lib.audiobook import Audiobook
from src.lib.config import OnComplete
from src.lib.fs_utils import find_book_dirs_for_series, find_book_dirs_in_inbox
from src.lib.inbox_state import InboxState
from src.lib.misc import re_group
from src.tests.helpers.pytest_utils import testutils


@pytest.mark.slow
class test_happy_paths:

    @pytest.fixture(scope="function", autouse=True)
    def setup(self, reset_inbox_state):
        yield

    book_fixure = [("book_fixture")]

    @pytest.fixture(scope="function", params=book_fixure)
    def book(self, request: pytest.FixtureRequest):
        return request.getfixturevalue(request.param)

    @pytest.mark.parametrize(
        "book, capfd",
        [
            ("tower_treasure__flat_mp3", "capfd"),
            ("house_on_the_cliff__flat_mp3", "capfd"),
        ],
        indirect=["book", "capfd"],
    )
    def test_basic_book_mp3(self, book: Audiobook, capfd: CaptureFixture[str]):
        app(max_loops=1, no_fix=True, test=True)
        assert testutils.assert_only_processed_books(
            capfd, book, found=(1, 1), converted=1
        )
        assert book.converted_dir.exists()

    def test_match_filter_multiple_mp3s(
        self,
        tower_treasure__flat_mp3: Audiobook,
        house_on_the_cliff__flat_mp3: Audiobook,
        capfd: CaptureFixture[str],
    ):

        testutils.set_match_filter("^(tower|house)")
        app(max_loops=1, no_fix=True, test=True)
        assert tower_treasure__flat_mp3.converted_dir.exists()
        assert house_on_the_cliff__flat_mp3.converted_dir.exists()
        out = testutils.get_stdout(capfd)
        assert testutils.assert_only_processed_books(
            out,
            tower_treasure__flat_mp3,
            house_on_the_cliff__flat_mp3,
            found=(2, 1),
            converted=2,
        )
        inbox = InboxState()
        found = int(re_group(re.search(r"Found (\d+) book", out), 1))
        ignoring = int(re_group(re.search(r"\(ignoring (\d+)\)", out), 1))
        assert found == len(inbox.matched_books)
        assert ignoring == len(inbox.filtered_books)
        assert (
            found + ignoring == len(inbox.book_dirs) == len(find_book_dirs_in_inbox())
        )

    def test_autoflatten_multidisc_mp3(
        self,
        old_mill__multidisc_mp3: Audiobook,
        enable_autoflatten,
        capfd: CaptureFixture[str],
    ):

        app(max_loops=1, no_fix=True, test=True)
        assert testutils.assert_only_processed_books(
            capfd, old_mill__multidisc_mp3, found=(1, 1), converted=1
        )
        assert old_mill__multidisc_mp3.converted_dir.exists()

    def test_convert_multi_book_series_mp3(
        self,
        chanur_series__multi_book_series_mp3: Audiobook,
        enable_convert_series,
        capfd: CaptureFixture[str],
    ):

        app(max_loops=1, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        child_books = list(
            map(
                Audiobook,
                find_book_dirs_for_series(
                    chanur_series__multi_book_series_mp3.inbox_dir
                ),
            )
        )
        assert testutils.assert_only_processed_books(
            out, *child_books, found=(5, 1), converted=5
        )
        assert out.count("Book Series •••••")
        assert chanur_series__multi_book_series_mp3.converted_dir.exists()
        for book in child_books:
            assert book.converted_dir.exists()

    @pytest.mark.parametrize(
        "partial_flatten_backup_dirs",
        [
            ([]),
            (["J.R.R. Tolkien - The Hobbit - Disc 1"]),
            (
                [
                    "J.R.R. Tolkien - The Hobbit - Disc 1",
                    "J.R.R. Tolkien - The Hobbit - Disc 2",
                ]
            ),
            (
                [
                    "J.R.R. Tolkien - The Hobbit - Disc 1",
                    "J.R.R. Tolkien - The Hobbit - Disc 2",
                    "J.R.R. Tolkien - The Hobbit - Disc 3",
                    "J.R.R. Tolkien - The Hobbit - Disc 4",
                    "J.R.R. Tolkien - The Hobbit - Disc 5",
                ]
            ),
        ],
    )
    def test_backups_are_ok_when_flattening_multidisc_books(
        self,
        partial_flatten_backup_dirs: list[str],
        the_hobbit__multidisc_mp3: Audiobook,
        enable_autoflatten,
        enable_backups,
        capfd: CaptureFixture[str],
    ):

        # make a backup of the_hobbit__multidisc_mp3 before running the app
        shutil.rmtree(the_hobbit__multidisc_mp3.backup_dir, ignore_errors=True)
        the_hobbit__multidisc_mp3.backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            the_hobbit__multidisc_mp3.inbox_dir,
            the_hobbit__multidisc_mp3.backup_dir,
            dirs_exist_ok=True,
        )

        if partial_flatten_backup_dirs:
            for d in partial_flatten_backup_dirs:
                for f in (the_hobbit__multidisc_mp3.backup_dir / d).iterdir():
                    f.rename(the_hobbit__multidisc_mp3.backup_dir / f.name)
                shutil.rmtree(the_hobbit__multidisc_mp3.backup_dir / d)

        app(max_loops=1, no_fix=True, test=True)
        assert testutils.assert_only_processed_books(
            capfd, the_hobbit__multidisc_mp3, found=(1, 1), converted=1
        )
        assert the_hobbit__multidisc_mp3.converted_dir.exists()

    @pytest.mark.parametrize(
        "on_complete, backup",
        [
            ("test_do_nothing", False),
            ("move", False),
            ("delete", False),
            ("delete", True),
        ],
    )
    def test_original_handled_on_complete(
        self, on_complete: OnComplete, backup: bool, tower_treasure__flat_mp3: Audiobook
    ):
        shutil.rmtree(tower_treasure__flat_mp3.archive_dir, ignore_errors=True)
        with testutils.set_on_complete(on_complete):
            with testutils.set_backups(backup):
                app(max_loops=1, no_fix=True, test=True)

                assert tower_treasure__flat_mp3.converted_dir.exists()
                match on_complete:
                    case "test_do_nothing":
                        assert tower_treasure__flat_mp3.inbox_dir.exists()
                        assert not tower_treasure__flat_mp3.archive_dir.exists()
                    case "move":
                        assert not tower_treasure__flat_mp3.inbox_dir.exists()
                        assert tower_treasure__flat_mp3.archive_dir.exists()
                    case "delete":
                        if backup:
                            assert not tower_treasure__flat_mp3.inbox_dir.exists()
                        else:
                            assert tower_treasure__flat_mp3.inbox_dir.exists()
                        assert not tower_treasure__flat_mp3.archive_dir.exists()
