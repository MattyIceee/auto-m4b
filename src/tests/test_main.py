from pytest import CaptureFixture

from src.auto_m4b import app
from src.lib.audiobook import Audiobook


def test_flat_mp3_1(tower_treasure__flat_mp3: Audiobook):

    app(max_loops=1, no_fix=True, test=True)
    assert True


def test_flat_mp3_2(house_on_the_cliff__flat_mp3: Audiobook):

    app(max_loops=1, no_fix=True, test=True)
    assert True


def test_bad_bitrate_mp3(the_crusades_through_arab_eyes__flat_mp3: Audiobook):

    app(max_loops=1, no_fix=True, test=True)
    assert True


def test_roman_numeral_mp3(roman_numeral__mp3: Audiobook, capfd: CaptureFixture[str]):

    app(max_loops=1, no_fix=True, test=True)
    msg = "Error: Some of this book's files appear to be named with roman numerals"
    stdout, _ = capfd.readouterr()
    assert msg in stdout


def test_all_flat_mp3s(
    tower_treasure__flat_mp3: Audiobook, house_on_the_cliff__flat_mp3: Audiobook
):

    app(max_loops=1, no_fix=True, test=True)
    assert True
