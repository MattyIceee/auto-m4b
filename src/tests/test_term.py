from pathlib import Path

import pytest

from src.lib.term import (
    count_empty_leading_lines,
    count_empty_trailing_lines,
    fmt_linebreak_path,
)


@pytest.mark.parametrize(
    "path, limit, indent, expected",
    [
        (Path("/"), None, None, "/"),
        (Path("/home"), None, None, "/home"),
        (Path("home"), None, None, "home"),
        (Path("home"), 4, 1, "home"),
        (Path("/home/user/Downloads"), 10, None, "/home/user/\nDownloads"),
        (Path("/home/user/Downloads"), 10, 0, "/home/user/\nDownloads"),
        (Path("/home/user/Downloads"), 10, 1, "/home/user/\n Downloads"),
        (Path("/home/user/Downloads"), 10, 5, "/home/user/\n     Downloads"),
        (
            Path(
                "/home/user/Downloads/this_is_a_really_long_filename_that_should_be_broken_up"
            ),
            20,
            1,
            "/home/user/Downloads/\n this_is_a_really_long_filename_that_should_be_broken_up",
        ),
        (
            Path(
                "/private/var/folders/18/vqpntnpj0sj5b5yb0s1m2_gc0000gn/T/auto-m4b/merge/tower_treasure__flat_mp3"
            ),
            40,
            1,
            "/private/var/folders/18/\n vqpntnpj0sj5b5yb0s1m2_gc0000gn/T/\n auto-m4b/merge/tower_treasure__flat_mp3",
        ),
    ],
)
def test_fmt_linebreak_path(path: Path, limit: int, indent: int, expected: str):
    if limit == None:
        limit = 120
    if indent == None:
        indent = 0
    test = fmt_linebreak_path(path, limit, indent)
    print(path, "\n       ↓", f"\n{test}")
    assert test == expected


@pytest.mark.parametrize(
    "line, empty_lines",
    [
        ("", 0),
        ("\n", 1),
        ("\n\n", 2),
        (" ", 1),
        ("  ", 1),
        ("a", 0),
        ("a\n", 0),
        ("a\n\n", 0),
        ("\na", 1),
        ("\n\na", 2),
        ("\n  \n", 2),
        ("\n  \n  a", 2),
        ("a\nb", 0),
        ("\na\nb\n", 1),
        ("  \na\nb\n \n", 1),
    ],
)
def test_count_empty_leading_lines(line: str, empty_lines: int):
    assert count_empty_leading_lines(line) == empty_lines


@pytest.mark.parametrize(
    "line, empty_lines",
    [
        ("", 0),
        ("\n", 1),
        ("\n\n", 2),
        (" ", 1),
        ("  ", 1),
        ("a", 0),
        ("a\n", 0),
        ("a\n\n", 1),
        ("a\n ", 1),
        ("a\n\n ", 2),
        ("\na", 0),
        ("\n\na", 0),
        ("a\nb", 0),
        ("\na\nb\n", 0),
        ("\na\nb\n ", 1),
        ("\n  \n", 2),
        ("  \na\nb\n \n", 1),
        ("  \na\nb\n \n ", 2),
    ],
)
def test_count_empty_trailing_lines(line: str, empty_lines: int):
    assert count_empty_trailing_lines(line) == empty_lines
