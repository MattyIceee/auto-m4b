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
