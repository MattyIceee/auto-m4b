from pytest import CaptureFixture

from src.auto_m4b import app
from src.lib.audiobook import Audiobook
from src.lib.formatters import listify
from src.lib.strings import en
from src.tests.helpers.pytest_utils import testutils


def test_flatten_and_no_convert(
    tiny__flat_mp3: Audiobook,
    enable_autoflatten,
    disable_convert_series,
    reset_inbox_state,
    capfd: CaptureFixture[str],
):
    app(max_loops=1, no_fix=True, test=True)

    out = testutils.get_stdout(capfd)

    assert "Found 1 book" in out
    assert (
        f"[Beta] features are enabled:\n{listify([en.FEATURE_FLATTEN_MULTI_DISC_BOOKS])}"
        in out
    )
    assert not en.FEATURE_CONVERT_SERIES in out


def test_flatten_and_convert(
    tiny__flat_mp3: Audiobook,
    enable_autoflatten,
    enable_convert_series,
    reset_inbox_state,
    capfd: CaptureFixture[str],
):
    app(max_loops=1, no_fix=True, test=True)

    out = testutils.get_stdout(capfd)

    assert "Found 1 book" in out
    assert (
        f"[Beta] features are enabled:\n{listify([en.FEATURE_FLATTEN_MULTI_DISC_BOOKS, en.FEATURE_CONVERT_SERIES])}"
        in out
    )


def test_no_flatten_and_convert(
    tiny__flat_mp3: Audiobook,
    disable_autoflatten,
    enable_convert_series,
    reset_inbox_state,
    capfd: CaptureFixture[str],
):
    app(max_loops=1, no_fix=True, test=True)

    out = testutils.get_stdout(capfd)

    assert "Found 1 book" in out
    assert (
        f"[Beta] features are enabled:\n{listify([en.FEATURE_CONVERT_SERIES])}" in out
    )
    assert not en.FEATURE_FLATTEN_MULTI_DISC_BOOKS in out


def test_no_flatten_or_convert(
    tiny__flat_mp3: Audiobook,
    disable_autoflatten,
    disable_convert_series,
    reset_inbox_state,
    capfd: CaptureFixture[str],
):
    app(max_loops=1, no_fix=True, test=True)

    out = testutils.get_stdout(capfd)

    assert "Found 1 book" in out
    assert not "[Beta]" in out
    assert not en.FEATURE_CONVERT_SERIES in out
    assert not en.FEATURE_FLATTEN_MULTI_DISC_BOOKS in out
