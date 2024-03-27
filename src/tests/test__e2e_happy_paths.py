import shutil

import pytest
from pytest import CaptureFixture

from src.auto_m4b import app
from src.lib.audiobook import Audiobook
from src.tests.helpers.pytest_utils import testutils


@pytest.mark.slow
class test_happy_paths:

    @pytest.fixture(scope="function", autouse=True)
    def setup(self, reset_inbox_state):
        yield

    def test_tower_treasure__flat_mp3(
        self, tower_treasure__flat_mp3: Audiobook, capfd: CaptureFixture[str]
    ):

        app(max_loops=1, no_fix=True, test=True)
        assert testutils.assert_only_processed_books(
            capfd, tower_treasure__flat_mp3, found=(1, 1), converted=1
        )
        assert tower_treasure__flat_mp3.converted_dir.exists()

    def test_house_on_the_cliff__flat_mp3(
        self, house_on_the_cliff__flat_mp3: Audiobook, capfd: CaptureFixture[str]
    ):

        app(max_loops=1, no_fix=True, test=True)
        assert testutils.assert_only_processed_books(
            capfd, house_on_the_cliff__flat_mp3, found=(1, 1), converted=1
        )
        assert house_on_the_cliff__flat_mp3.converted_dir.exists()

    def test_hardy_boys__flat_mp3s(
        self,
        tower_treasure__flat_mp3: Audiobook,
        house_on_the_cliff__flat_mp3: Audiobook,
        capfd: CaptureFixture[str],
    ):

        testutils.set_match_filter("^(tower|house)")
        app(max_loops=1, no_fix=True, test=True)
        assert tower_treasure__flat_mp3.converted_dir.exists()
        assert house_on_the_cliff__flat_mp3.converted_dir.exists()
        assert testutils.assert_only_processed_books(
            capfd,
            tower_treasure__flat_mp3,
            house_on_the_cliff__flat_mp3,
            found=(2, 1),
            converted=2,
        )

    def test_autoflatten_old_mill__multidisc_mp3(
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
        assert testutils.assert_only_processed_books(capfd, the_hobbit__multidisc_mp3)
        assert the_hobbit__multidisc_mp3.converted_dir.exists()
