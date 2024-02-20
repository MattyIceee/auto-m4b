import re
from pathlib import Path
from typing import cast, TypeVar

T = TypeVar("T", bound=str | Path)


def rm_audio_ext(path: T) -> T:
    # Removes audio file extensions from a string or Path

    if isinstance(path, str):
        return cast(
            T,
            path.replace(".mp3", "")
            .replace(".m4a", "")
            .replace(".m4b", "")
            .replace(".wma", ""),
        )
    else:
        return cast(T, Path(path).with_suffix(""))


def rm_ext(path: str | Path) -> str:
    return Path(path).stem


def get_ext(path: str) -> str:
    return Path(path).suffix


def escape_special_chars(string: str) -> str:
    return re.sub(r"[\[\]\(\)*?|&]", r"\\\g<0>", string)


def fix_smart_quotes(_string: str) -> str:
    # takes a string and replaces smart quotes with regular quotes
    trans = str.maketrans("‘’‚‛′′“”„‟″″", "''''''\"\"\"\"\"\"")
    return _string.translate(trans)


def human_elapsed_time(elapsedtime: int) -> str:
    # make friendly elapsed time as HHh:MMm:SSs but don't show hours if 0
    # e.g. 00m:52s, 12m:52s, 1h:12m:52s

    hours, remainder = divmod(elapsedtime, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}h:{minutes:02}m:{seconds:02}s"
    else:
        return f"{minutes:02}m:{seconds:02}s"


def count_numbers_in_string(s: str) -> int:
    return len(re.findall(r"\d", s))


def re_group(
    match: re.Match[str] | None,
    group: int | str = 0,
    /,
    default: str = "",
) -> str:
    # returns the first match of pattern in string or default if no match
    return match.group(group) if match else default


def compare_trim(a: str, b: str) -> bool:
    return " ".join(a.split()) == " ".join(b.split())
