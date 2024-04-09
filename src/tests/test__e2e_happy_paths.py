import re
import shutil

import pytest
from pytest import CaptureFixture

from src.auto_m4b import app
from src.lib.audiobook import Audiobook
from src.lib.config import OnComplete
from src.lib.fs_utils import find_book_dirs_in_inbox
from src.lib.inbox_state import InboxState
from src.lib.misc import re_group
from src.tests.helpers.pytest_utils import testutils


@pytest.mark.slow
class test_happy_paths:

    @pytest.fixture(scope="function", autouse=True)
    def setup(self, reset_inbox_state):
        yield

    @pytest.mark.parametrize(
        "indirect_fixture, capfd",
        [
            ("tower_treasure__flat_mp3", "capfd"),
            ("house_on_the_cliff__flat_mp3", "capfd"),
        ],
        indirect=["indirect_fixture", "capfd"],
    )
    def test_basic_book_mp3(
        self, indirect_fixture: Audiobook, capfd: CaptureFixture[str]
    ):
        book = indirect_fixture
        quality = f"{book.bitrate_friendly} @ {book.samplerate_friendly}".replace(
            "kb/s", "kbps"
        )
        app(max_loops=1, no_fix=True, test=True)
        assert testutils.assert_only_processed_books(
            capfd,
            book,
            found=[testutils.found_books(books=1, prints=1)],
            converted=[testutils.converted_books(books=1, prints=1)],
        )
        assert testutils.assert_converted_book_and_collateral_exist(book, quality)

    def test_backup_book_mp3(
        self, tiny__flat_mp3: Audiobook, capfd: CaptureFixture[str], enable_backups
    ):
        app(max_loops=1, no_fix=True, test=True)
        out = testutils.get_stdout(capfd)
        assert "Making a backup copy" in out
        assert testutils.assert_only_processed_books(
            out,
            tiny__flat_mp3,
            found=[testutils.found_books(books=1, prints=1)],
            converted=[testutils.converted_books(books=1)],
        )
        assert tiny__flat_mp3.converted_dir.exists()

    def test_match_filter_multiple_mp3s(
        self,
        tower_treasure__flat_mp3: Audiobook,
        house_on_the_cliff__flat_mp3: Audiobook,
        capfd: CaptureFixture[str],
        enable_archiving,
    ):

        testutils.set_match_filter("^(tower|house)")
        inbox = InboxState()
        inbox_dirs = inbox.book_dirs
        inbox.scan()
        matched_books = len(inbox.matched_books)
        filtered_books = len(inbox.filtered_books)
        inbox.destroy()
        app(max_loops=1, no_fix=True, test=True)
        assert tower_treasure__flat_mp3.converted_dir.exists()
        assert house_on_the_cliff__flat_mp3.converted_dir.exists()
        out = testutils.get_stdout(capfd)
        assert testutils.assert_only_processed_books(
            out,
            tower_treasure__flat_mp3,
            house_on_the_cliff__flat_mp3,
            found=[testutils.found_books(books=2, prints=1)],
            converted=[testutils.converted_books(books=2)],
            ignoring=[testutils.ignoring_books(min_books=1, prints=1)],
        )
        found = int(re_group(re.search(r"Found (\d+) book", out), 1))
        ignoring = int(re_group(re.search(r"\(ignoring (\d+)\)", out), 1))
        converted = len(testutils.get_all_processed_books(out))
        assert found == matched_books
        assert ignoring == filtered_books
        assert (
            found + ignoring
            == len(inbox_dirs)
            == len(find_book_dirs_in_inbox()) + converted
        )
        # With archiving enabled, the inbox should have 2 fewer books.
        # If archiving is disabled, the inbox should have the same number of books. ````gfv/.jh

    def test_autoflatten_multidisc_mp3(
        self,
        old_mill__multidisc_mp3: Audiobook,
        enable_autoflatten,
        capfd: CaptureFixture[str],
    ):

        app(max_loops=1, no_fix=True, test=True)
        assert testutils.assert_only_processed_books(
            capfd,
            old_mill__multidisc_mp3,
            found=[testutils.found_books(books=1, prints=1)],
            converted=[testutils.converted_books(books=1)],
        )
        assert old_mill__multidisc_mp3.converted_dir.exists()

    @pytest.mark.parametrize("backups_enabled", [False, True])
    def test_convert_book_series_mp3(
        self,
        Chanur_Series: list[Audiobook],
        enable_convert_series,
        capfd: CaptureFixture[str],
        backups_enabled,
    ):
        with testutils.set_backups(backups_enabled):
            qualities = [
                f"{b.bitrate_friendly} @ {b.samplerate_friendly}".replace(
                    "kb/s", "kbps"
                )
                for b in Chanur_Series
            ]
            app(max_loops=1, no_fix=True, test=True)
            out = testutils.get_stdout(capfd)
            series = Chanur_Series[0]
            child_books = Chanur_Series[1:]
            assert len(child_books) == 5
            for book, quality in zip(child_books, qualities):
                testutils.assert_converted_book_and_collateral_exist(book, quality)
            assert testutils.assert_only_processed_books(
                out,
                *child_books,
                found=[testutils.found_books(books=5, prints=1)],
                converted=[testutils.converted_books(books=5)],
            )
            assert out.count("Book Series •••••")
            assert series.converted_dir.exists()
            for book in child_books:
                assert book.converted_dir.exists()

    def test_book_series_handles_series_collateral(
        self,
        Chanur_Series: list[Audiobook],
        enable_convert_series,
        enable_archiving,
    ):

        app(max_loops=1, no_fix=True, test=True)
        series = Chanur_Series[0]
        assert series.converted_dir.exists()
        for pic in [
            "414fL6J.png",
            "i367gyc.png",
            "KiaprKx.png",
            "mhHDEdX.png",
            "xEZNYAN.png",
        ]:
            assert (series.converted_dir / pic).exists()
        assert not series.inbox_dir.exists()
        assert series.archive_dir.exists()

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
            capfd,
            the_hobbit__multidisc_mp3,
            found=[testutils.found_books(books=1, prints=1)],
            converted=[testutils.converted_books(books=1)],
        )
        assert the_hobbit__multidisc_mp3.converted_dir.exists()

    @pytest.mark.parametrize(
        "on_complete, backup",
        [
            ("test_do_nothing", False),
            ("archive", False),
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
                    case "archive":
                        assert not tower_treasure__flat_mp3.inbox_dir.exists()
                        assert tower_treasure__flat_mp3.archive_dir.exists()
                    case "delete":
                        if backup:
                            assert not tower_treasure__flat_mp3.inbox_dir.exists()
                        else:
                            assert tower_treasure__flat_mp3.inbox_dir.exists()
                        assert not tower_treasure__flat_mp3.archive_dir.exists()
