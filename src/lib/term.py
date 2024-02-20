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

DEFAULT_COLOR = 0
GREY_COLOR = Tinta().inspect(name="grey")
DARK_GREY_COLOR = Tinta().inspect(name="dark_grey")
LIGHT_GREY_COLOR = Tinta().inspect(name="light_grey")
AQUA_COLOR = Tinta().inspect(name="aqua")
GREEN_COLOR = Tinta().inspect(name="green")
BLUE_COLOR = Tinta().inspect(name="blue")
PURPLE_COLOR = Tinta().inspect(name="purple")
AMBER_COLOR = Tinta().inspect(name="amber")
ORANGE_COLOR = Tinta().inspect(name="orange")
ORANGE_HIGHLIGHT_COLOR = Tinta().inspect(name="orange_accent")
RED_COLOR = Tinta().inspect(name="red")
RED_HIGHLIGHT_COLOR = Tinta().inspect(name="red_accent")
PINK_COLOR = Tinta().inspect(name="pink")


def line_is_empty(line: str) -> bool:
    # Check if the line is entirely whitespace
    return not line or all(c in " \t" for c in line)


def line_starts_with_newline(line):
    # Check if the line starts with a newline
    return line.startswith("\n")


def line_ends_with_newline(line):
    # Check if the line ends with a newline
    return line.endswith("\n")


def strip_leading_newlines(string):
    # Takes a string and strips leading newlines
    return re.sub(r"^\n*", "", string)


def strip_trailing_newlines(string):
    # Takes a string and strips trailing newlines
    return re.sub(r"\n*$", "", string)


def ensure_trailing_newline(string):
    # Takes a string and ensures it ends with a newline
    return re.sub(r"\n*$", "\n", string)


def ensure_leading_newline(string):
    # Takes a string and ensures it starts with a newline
    return re.sub(r"^\n*", "\n", string)


def trim_newlines(string):
    # Takes a string and strips leading and trailing newlines
    return re.sub(r"^\n*|\n*$", "", string)


def trim_single_spaces(string):
    if string.startswith(" "):
        string = string[1:]  # Remove one space from the start
    if string.endswith(" "):
        string = string[:-1]  # Remove one space from the end
    return string


def smart_print(
    text: Any = "",
    color: int = DEFAULT_COLOR,
    highlight_color: int | None = None,
    end: str = "\n",
):

    text = str(text)

    if highlight_color is None:
        highlight_color = color

    global LAST_LINE_WAS_EMPTY, LAST_LINE_ENDS_WITH_NEWLINE, LAST_LINE_WAS_ALERT, THIS_LINE_IS_ALERT, THIS_LINE_IS_EMPTY
    THIS_LINE_IS_EMPTY = line_is_empty(text)

    this_line_starts_with_newline = line_starts_with_newline(text)
    this_line_ends_with_newline = line_ends_with_newline(text)

    if LAST_LINE_WAS_EMPTY and THIS_LINE_IS_EMPTY:
        return

    if LAST_LINE_WAS_ALERT and THIS_LINE_IS_ALERT:
        text = ensure_trailing_newline(trim_newlines(text))
        LAST_LINE_WAS_EMPTY = False
        LAST_LINE_ENDS_WITH_NEWLINE = True
        LAST_LINE_WAS_ALERT = True
        THIS_LINE_IS_ALERT = False
    elif not LAST_LINE_WAS_ALERT and THIS_LINE_IS_ALERT:
        if not LAST_LINE_WAS_EMPTY and not LAST_LINE_ENDS_WITH_NEWLINE:
            text = ensure_trailing_newline(ensure_leading_newline(text))
        THIS_LINE_IS_ALERT = False
        LAST_LINE_WAS_EMPTY = False
        LAST_LINE_WAS_ALERT = True
        LAST_LINE_ENDS_WITH_NEWLINE = True
    else:
        if LAST_LINE_WAS_ALERT:
            text = ensure_leading_newline(text)
        elif LAST_LINE_WAS_EMPTY or LAST_LINE_ENDS_WITH_NEWLINE:
            text = strip_leading_newlines(text)
        LAST_LINE_WAS_EMPTY = THIS_LINE_IS_EMPTY
        LAST_LINE_ENDS_WITH_NEWLINE = this_line_ends_with_newline
        LAST_LINE_WAS_ALERT = False
        THIS_LINE_IS_ALERT = False

    t = Tinta()

    if highlight_color != color:
        parts = re.split(r"(\{\{.*?\}\})", text)
        # if trim at most one leading and trailing space from each part
        parts = [trim_single_spaces(p) for p in parts]
        for part in parts:
            if part.startswith("{{") and part.endswith("}}"):
                t.tint(highlight_color, part[2:-2])
            else:
                t.tint(color, part)
    else:
        t.tint(color, text)

    t.print(end=end)


def nl(num_newlines=1):
    global LAST_LINE_WAS_EMPTY
    global LAST_LINE_ENDS_WITH_NEWLINE
    global LAST_LINE_WAS_ALERT

    if LAST_LINE_WAS_EMPTY:
        num_newlines -= 1

    LAST_LINE_ENDS_WITH_NEWLINE = True
    LAST_LINE_WAS_EMPTY = True
    LAST_LINE_WAS_ALERT = False

    smart_print("\n" * num_newlines, end="")


def print_grey(*args: Any, highlight_color: int | None = LIGHT_GREY_COLOR):
    smart_print(" ".join(args), color=GREY_COLOR, highlight_color=highlight_color)


def print_dark_grey(*args: Any, highlight_color: int | None = GREY_COLOR):
    smart_print(" ".join(args), color=DARK_GREY_COLOR, highlight_color=highlight_color)


def print_light_grey(*args: Any, highlight_color: int | None = LIGHT_GREY_COLOR + 2):
    smart_print(" ".join(args), color=LIGHT_GREY_COLOR, highlight_color=highlight_color)


def print_aqua(*args: Any, highlight_color: int | None = None):
    smart_print(" ".join(args), color=AQUA_COLOR, highlight_color=highlight_color)


def print_green(*args: Any, highlight_color: int | None = None):
    smart_print(" ".join(args), color=GREEN_COLOR, highlight_color=highlight_color)


def print_blue(*args: Any, highlight_color: int | None = None):
    smart_print(" ".join(args), color=BLUE_COLOR, highlight_color=highlight_color)


def print_purple(*args: Any, highlight_color: int | None = None):
    smart_print(" ".join(args), color=PURPLE_COLOR, highlight_color=highlight_color)


def print_amber(*args: Any, highlight_color: int | None = None):
    smart_print(" ".join(args), color=AMBER_COLOR, highlight_color=highlight_color)


def print_orange(*args: Any, highlight_color: int | None = ORANGE_HIGHLIGHT_COLOR):
    smart_print(" ".join(args), color=ORANGE_COLOR, highlight_color=highlight_color)


def print_red(*args: Any, highlight_color: int | None = RED_HIGHLIGHT_COLOR):
    smart_print(" ".join(args), color=RED_COLOR, highlight_color=highlight_color)


def print_pink(*args: Any, highlight_color: int | None = None):
    smart_print(" ".join(args), color=PINK_COLOR, highlight_color=highlight_color)


def print_list(*args: Any, highlight_color: int | None = None):
    smart_print(
        "- " + " ".join(args), color=GREY_COLOR, highlight_color=highlight_color
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
    _print_alert(RED_COLOR, RED_HIGHLIGHT_COLOR, " ".join(args))


def print_warning(*args: Any):
    _print_alert(ORANGE_COLOR, ORANGE_HIGHLIGHT_COLOR, " ".join(args))


def print_notice(*args: Any):
    _print_alert(LIGHT_GREY_COLOR, DEFAULT_COLOR, " ".join(args))


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
    _known_file_types = ["mp3", "m4b", "m4a", "wma"]
    _is_known_file_type = any(arg in _known_file_types for arg in args)
    _line = args[1] if len(args) > 1 else args[0]

    if _is_known_file_type:
        if "mp3" in args:
            tinted_mp3(_line)
        elif "m4b" in args:
            tinted_m4b(_line)
        elif "m4a" in args:
            tint_aqua(_line)
        elif "wma" in args:
            Tinta().tint(AMBER_COLOR, _line).to_str()
    else:
        Tinta().tint(DEFAULT_COLOR, _line).to_str()


def divider():
    global LAST_LINE_WAS_ALERT, LAST_LINE_ENDS_WITH_NEWLINE, LAST_LINE_WAS_EMPTY
    if LAST_LINE_WAS_ALERT:
        if not LAST_LINE_ENDS_WITH_NEWLINE:
            smart_print("\n")
            LAST_LINE_ENDS_WITH_NEWLINE = True
        if not LAST_LINE_WAS_EMPTY:
            smart_print("\n")
            LAST_LINE_WAS_EMPTY = True
    print_dark_grey("-" * 80)


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

    length = 0
    output = ""

    for part in path.parts:
        if part == "":
            continue
        length += len(part) + 1
        if length > limit:
            output = output.rstrip("/")
            output += "\n" + " " * indent + "/" + part
            length = len(part) + 1
        else:
            output += "/" + part

    return output
