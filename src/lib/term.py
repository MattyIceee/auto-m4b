import import_debug

from src.lib.misc import re_group

import_debug.bug.push("src/lib/term.py")
import re
from pathlib import Path
from typing import Any

from tinta import Tinta

Tinta.load_colors("src/colors.ini")

THIS_LINE_IS_EMPTY = False
THIS_LINE_IS_ALERT = False
LAST_LINE_WAS_EMPTY = False
LAST_LINE_WAS_ALERT = False
LAST_LINE_ENDS_WITH_NEWLINE = False
PRINT_LOG: list[tuple[str, str]] = []

DEFAULT_COLOR = 0
GREY_COLOR = Tinta().inspect(name="grey")
DARK_GREY_COLOR = Tinta().inspect(name="dark_grey")
LIGHT_GREY_COLOR = Tinta().inspect(name="light_grey")
AQUA_COLOR = Tinta().inspect(name="aqua")
GREEN_COLOR = Tinta().inspect(name="green")
BLUE_COLOR = Tinta().inspect(name="blue")
PURPLE_COLOR = Tinta().inspect(name="purple")
AMBER_COLOR = Tinta().inspect(name="amber")
AMBER_HIGHLIGHT_COLOR = Tinta().inspect(name="amber_accent")
ORANGE_COLOR = Tinta().inspect(name="orange")
ORANGE_HIGHLIGHT_COLOR = Tinta().inspect(name="orange_accent")
RED_COLOR = Tinta().inspect(name="red")
RED_HIGHLIGHT_COLOR = Tinta().inspect(name="red_accent")
PINK_COLOR = Tinta().inspect(name="pink")


def ansi_strip(string: str) -> str:
    # Strip ANSI escape codes from a string
    return re.sub(r"\x1b\[[0-9;]*[mGK]", "", string)


def multiline_is_empty(multiline: str) -> bool:
    # Check if the multiline string is entirely whitespace
    def is_empty(line: str):
        return not line or all(c in " \t\n" for c in ansi_strip(line))

    return not multiline or all(is_empty(line) for line in multiline.split("\n"))


def count_empty_leading_lines(multiline: str) -> int:
    """Count the number of empty lines at the start of a multiline string.
    If the string is entirely empty or is None, the result will be 0.
    """
    if not multiline:
        return 0
    lines = multiline.splitlines()
    count = 0
    for line in lines:
        if multiline_is_empty(line):
            count += 1
        else:
            break
    return count


def count_empty_trailing_lines(multiline: str) -> int:
    """Count the number of empty lines at the end of a multiline string.
    If the string is entirely empty or is None, the result will be 0. Note
    that a string ending with a newline character will not be considered,
    as there is no content after the newline.
    """
    if not multiline:
        return 0
    lines = multiline.splitlines(keepends=True)
    count = 0
    for line in reversed(lines):
        if multiline_is_empty(line):
            count += 1
        else:
            break
    return count


def get_prev_text_and_end() -> tuple[str, str]:
    global PRINT_LOG
    return PRINT_LOG[-1] if PRINT_LOG else ("", "")


def get_prev_line() -> str:
    prev_text, prev_end = get_prev_text_and_end()
    return f"{prev_text}{prev_end}"


def was_prev_line_empty() -> bool:
    return count_empty_trailing_lines(get_prev_line()) > 0


def was_prev_line_alert() -> bool:
    prev_text, _ = get_prev_text_and_end()
    return " *** " in prev_text


def did_prev_start_with_newline() -> bool:
    return does_line_have_leading_newline(get_prev_line())


def did_prev_end_with_newline() -> bool:
    return does_line_have_trailing_newline(get_prev_line())


def does_line_have_leading_newline(line: Any) -> bool:
    # Check if the line starts with a newline
    if line is None:
        return False
    return str(line).startswith("\n")


def does_line_have_trailing_newline(line: Any) -> bool:
    # Check if the line ends with a newline
    if line is None:
        return False
    return str(line).endswith("\n")


# def strip_leading_newlines(string):
#     # Takes a string and strips leading newlines
#     return re.sub(r"^\n*", "", string)


# def strip_trailing_newlines(string):
#     # Takes a string and strips trailing newlines
#     return re.sub(r"\n*$", "", string)


def ensure_trailing_newline(s: str) -> str:
    # Takes a string and ensures it ends with a newline
    return re.sub(r"\n*$", "\n", s)


def ensure_leading_newline(s: str) -> str:
    # Takes a string and ensures it starts with a newline
    return re.sub(r"^\n*", "\n", s)


def trim_newlines(s: str) -> str:
    # Takes a string and strips leading and trailing newlines
    return re.sub(r"^\n*|\n*$", "", s)


def trim_leading_newlines(s: str) -> str:
    # Takes a string and strips leading newlines
    return re.sub(r"^\n*", "", s)


def trim_trailing_newlines(s: str) -> str:
    # Takes a string and strips trailing newlines
    return re.sub(r"\n*$", "", s)


def smart_print(
    text: Any = "",
    color: int = DEFAULT_COLOR,
    highlight_color: int | None = None,
    end: str = "\n",
):
    text = str(text)
    # line = f"{text}{end}"

    if highlight_color is None:
        highlight_color = color

    line_is_alert = " *** " in text
    line_is_indented = text.startswith(" " * 5)
    # line_starts_with_newline = does_line_have_leading_newline(line)
    # line_ends_with_newline = does_line_have_trailing_newline(line)
    # line_is_empty = multiline_is_empty(line)
    # line_num_trailing_empty_lines = count_empty_trailing_lines(line)

    # prev_started_with_newline = did_prev_start_with_newline()
    # prev_ended_with_newline = did_prev_end_with_newline()
    prev_was_alert = was_prev_line_alert()
    prev_line_was_empty = was_prev_line_empty()

    if line_is_alert:
        end = "\n"
        if prev_was_alert:
            text = trim_newlines(text)
        elif not prev_line_was_empty:
            text = ensure_leading_newline(text)

        text = ensure_trailing_newline(text)
    elif prev_was_alert:
        if line_is_indented:
            if prev_line_was_empty:
                Tinta.up()
            text = trim_newlines(text)
        elif not prev_line_was_empty:
            text = ensure_leading_newline(text)
        else:
            text = trim_leading_newlines(text)
    elif prev_line_was_empty:
        text = trim_leading_newlines(text)

    t = Tinta()

    if highlight_color != color:
        parts = [p for p in re.split(r"(\s?{{.*?}}\s?)", text) if p]
        for part in parts:
            if re.search(r"\s?{{.*}}\s?", part):
                # remove the leading and trailing braces from the part, including any leading or trailing spaces
                part = re.sub(r"^\s?{{\s?|\s?}}\s?$", "", part)
                t.tint(highlight_color, part)
            else:
                t.tint(color, part)
    else:
        t.tint(color, text)

    PRINT_LOG.append((t.to_str(plaintext=True), end))

    t.print(end=end)


def nl(num_newlines=1):
    if was_prev_line_empty():
        num_newlines -= 1
    smart_print("\n" * num_newlines, end="")


def print_grey(*args: Any, highlight_color: int | None = LIGHT_GREY_COLOR):
    smart_print(
        " ".join(map(str, args)), color=GREY_COLOR, highlight_color=highlight_color
    )


def print_dark_grey(*args: Any, highlight_color: int | None = GREY_COLOR):
    smart_print(
        " ".join(map(str, args)), color=DARK_GREY_COLOR, highlight_color=highlight_color
    )


def print_light_grey(*args: Any, highlight_color: int | None = GREY_COLOR):
    smart_print(
        " ".join(map(str, args)),
        color=LIGHT_GREY_COLOR,
        highlight_color=highlight_color,
    )


def print_aqua(*args: Any, highlight_color: int | None = None):
    smart_print(
        " ".join(map(str, args)), color=AQUA_COLOR, highlight_color=highlight_color
    )


def print_green(*args: Any, highlight_color: int | None = None):
    smart_print(
        " ".join(map(str, args)), color=GREEN_COLOR, highlight_color=highlight_color
    )


def print_blue(*args: Any, highlight_color: int | None = None):
    smart_print(
        " ".join(map(str, args)), color=BLUE_COLOR, highlight_color=highlight_color
    )


def print_purple(*args: Any, highlight_color: int | None = None):
    smart_print(
        " ".join(map(str, args)), color=PURPLE_COLOR, highlight_color=highlight_color
    )


def print_amber(*args: Any, highlight_color: int | None = None):
    smart_print(
        " ".join(map(str, args)), color=AMBER_COLOR, highlight_color=highlight_color
    )


def print_orange(*args: Any, highlight_color: int | None = ORANGE_HIGHLIGHT_COLOR):
    smart_print(
        " ".join(map(str, args)), color=ORANGE_COLOR, highlight_color=highlight_color
    )


def print_red(*args: Any, highlight_color: int | None = RED_HIGHLIGHT_COLOR):
    smart_print(
        " ".join(map(str, args)), color=RED_COLOR, highlight_color=highlight_color
    )


def print_pink(*args: Any, highlight_color: int | None = None):
    smart_print(
        " ".join(map(str, args)), color=PINK_COLOR, highlight_color=highlight_color
    )


def print_debug(*args: Any, highlight_color: int | None = AMBER_HIGHLIGHT_COLOR):
    from src.lib.config import cfg

    if not cfg.DEBUG:
        return
    smart_print(
        "[DEBUG] " + " ".join(map(str, args)),
        color=AMBER_COLOR,
        highlight_color=highlight_color,
    )


def print_list(*args: Any, highlight_color: int | None = None):
    smart_print(
        "- " + " ".join(map(str, args)),
        color=GREY_COLOR,
        highlight_color=highlight_color,
    )


def _print_alert(color: int, highlight_color: int, line: str):
    global LAST_LINE_WAS_ALERT, THIS_LINE_IS_ALERT
    THIS_LINE_IS_ALERT = True
    line = trim_newlines(line)

    line = " *** " + line

    smart_print(line, color=color, highlight_color=highlight_color)
    LAST_LINE_WAS_ALERT = True
    THIS_LINE_IS_ALERT = False


def print_error(*args: Any):
    _print_alert(RED_COLOR, RED_HIGHLIGHT_COLOR, " ".join(map(str, args)))


def print_warning(*args: Any):
    _print_alert(ORANGE_COLOR, ORANGE_HIGHLIGHT_COLOR, " ".join(map(str, args)))


def print_notice(*args: Any):
    _print_alert(LIGHT_GREY_COLOR, DEFAULT_COLOR, " ".join(map(str, args)))


PATH_COLOR = PURPLE_COLOR


def tint_path(*args: Any):
    return Tinta().tint(PURPLE_COLOR, *args).to_str()


def tint_aqua(*args: Any):
    return Tinta().tint(AQUA_COLOR, *args).to_str()


def tint_amber(*args: Any):
    return Tinta().tint(AMBER_COLOR, *args).to_str()


def tint_light_grey(*args: Any):
    return Tinta().tint(LIGHT_GREY_COLOR, *args).to_str()


def tint_warning(*args: Any):
    return Tinta().tint(ORANGE_COLOR, *args).to_str()


def tint_warning_accent(*args: Any):
    return Tinta().tint(ORANGE_HIGHLIGHT_COLOR, *args).to_str()


def tint_error(*args: Any):
    return Tinta().tint(RED_COLOR, *args).to_str()


def tint_error_accent(*args: Any):
    return Tinta().tint(RED_HIGHLIGHT_COLOR, *args).to_str()


def tinted_mp3(*args: Any):
    if not args:
        return Tinta().tint(PINK_COLOR, "mp3").to_str()
    else:
        return Tinta().tint(PINK_COLOR, *args).to_str()


def tinted_m4b(*args):
    if not args:
        return Tinta().aqua("m4b").to_str()
    else:
        return Tinta().aqua(*args).to_str()


def tinted_file(*args):
    s = " ".join(args)
    if found := re_group(re.search(r"\b(mp3|m4b|m4a|wma)\b", s, re.I)):
        match found:
            case "mp3":
                return tinted_mp3(s)
            case "m4b":
                return tinted_m4b(s)
            case "m4a":
                return tint_aqua(s)
            case "wma":
                return Tinta().tint(AMBER_COLOR, s).to_str()
    return s


def divider(lead: str = "", color: int = DARK_GREY_COLOR, width: int = 90):
    smart_print(lead + ("-" * width), color=color)


def fmt_linebreak_path(path: Path, limit: int = 120, indent: int = 0) -> str:
    """Split a path string into multiple lines if it exceeds the limit. Returns a string.
    Args:
        path (str): The path to split
        limit (int, optional): The maximum length of each line. Defaults to 120.
        indent (int, optional): The number of spaces to indent each line. Defaults to 0.

    Example:
        ```
        split_path("/path/to/some/file.mp3", 20, 4)
        # Output:
        # /path
        #     /to
        #     /some
        #     /file.mp3
        ```"""

    output = ""

    if len(path.parts) < 2:
        return str(path)

    path_matrix: list[list[str]] = [[]]

    for part in path.parts:
        if part == "":
            continue
        curr_idx = len(path_matrix) - 1
        curr_row = path_matrix[curr_idx]
        curr_row_len = len(str(Path(*(curr_row)))) if curr_row else 0

        if curr_row_len + len(part) + 1 > limit:
            path_matrix.append([part])
        else:
            curr_row.append(part)

    if not path_matrix:
        return str(path)

    first_row = path_matrix[0]
    has_multiple_rows = len(path_matrix) > 1
    output = str(Path(*first_row))
    if has_multiple_rows:
        output += "/"
        for i, row in enumerate(path_matrix[1:]):
            output += "\n" + (" " * indent) + str(Path(*row))
            if i < len(path_matrix) - 2:
                output += "/"

    return output


import_debug.bug.pop("src/lib/term.py")
