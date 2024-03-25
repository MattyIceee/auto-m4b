import shutil

import pytest
from pytest import CaptureFixture

from src.auto_m4b import app
from src.lib.audiobook import Audiobook
from src.tests.helpers.pytest_utils import testutils


def get_output(capfd: CaptureFixture[str]) -> str:
    return testutils.strip_ansi_codes(capfd.readouterr().out)


@pytest.mark.slow
class test_happy_paths:

    def test_tower_treasure__flat_mp3(self, tower_treasure__flat_mp3: Audiobook):

        app(max_loops=1, no_fix=True, test=True)
        assert tower_treasure__flat_mp3.converted_dir.exists()

    def test_autoflatten_old_mill__multidisc_mp3(
        self, old_mill__multidisc_mp3: Audiobook
    ):

        testutils.enable_autoflatten()
        app(max_loops=1, no_fix=True, test=True)
        assert old_mill__multidisc_mp3.converted_dir.exists()

        testutils.disable_autoflatten()

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
    ):

        testutils.enable_autoflatten()
        testutils.enable_backups()
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
        assert the_hobbit__multidisc_mp3.converted_dir.exists()

        testutils.disable_autoflatten()
        testutils.disable_backups()

    def test_house_on_the_cliff__flat_mp3(
        self, house_on_the_cliff__flat_mp3: Audiobook
    ):

        app(max_loops=1, no_fix=True, test=True)
        assert house_on_the_cliff__flat_mp3.converted_dir.exists()

    def test_hardy_boys__flat_mp3s(
        self,
        flush_hashes_fixture,
        tower_treasure__flat_mp3: Audiobook,
        house_on_the_cliff__flat_mp3: Audiobook,
    ):

        testutils.set_match_name("^(tower|house)")
        app(max_loops=1, no_fix=True, test=True)
        assert tower_treasure__flat_mp3.converted_dir.exists()
        assert house_on_the_cliff__flat_mp3.converted_dir.exists()
