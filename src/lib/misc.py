import os
import shutil
import subprocess
from collections.abc import Iterable

import import_debug
from dotenv import dotenv_values

import_debug.bug.push("src/lib/misc.py")
import re
from pathlib import Path
from typing import Any, cast, TypeVar

BOOK_ASCII = """
        .--.                    .---.
 ___.---|__|            .-.     |~~~|
|   |===|--|_           |_|   __|~~~|--.
| A |===|  |'\\     .----!~|  |__|   |--|
| U |   |PY|.'\\    |====| |--|--| M |  |
| D |   |  |\\.'\\   |CATS| |__|  | 4 |  |
| I |   |  | \\  \\  |====| |==|  | B |  |
| O |   |__|  \\.'\\ |    |_|__|--|   |__|
|   |===|--|   \\.'\\|====|~|--|  |~~~|--|
^---^---'--^    `-'`----^-^--^--^---'--'"""


def get_git_root():
    return Path(
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"])
        .strip()
        .decode("utf-8")
    )


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


def get_numbers_in_string(s: str) -> str:
    """Returns a list of numbers found in a string, in order they are found."""
    return "".join(re.findall(r"\d", s))


def re_group(
    match: re.Match[str] | None,
    group: int | str = 0,
    *,
    default: str = "",
) -> str:
    # returns the first match of pattern in string or default if no match
    found = match.group(group) if match else None
    return found if found is not None else default


def compare_trim(a: str, b: str) -> bool:
    return " ".join(a.split()) == " ".join(b.split())


def is_boolish(v: Any) -> bool:
    return str(v).lower() in ["true", "false", "y", "n", "yes", "no"]


def parse_bool(v: Any) -> bool:
    """Parses a string value to a boolean value."""
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("true", "1", "t", "y", "yes")


def load_env(
    env_file: str | Path, clean_working_dirs: bool = False
) -> dict[str, str | None]:
    from src.lib.config import WORKING_DIRS

    env_file = Path(env_file)

    def is_maybe_path(v: Any) -> bool:
        v = str(v)
        return v and Path(v).exists() or "." in v or "/" in v or "\\" in v or "~" in v

    env_vars: dict[str, str | None] = {}

    for k, v in dotenv_values(env_file).items():
        if not v:
            continue
        if is_boolish(v):
            os.environ[k] = "Y" if parse_bool(v) else "N"
        elif is_maybe_path(v):
            v = str(v)
            p = Path(v).expanduser()
            if not p.is_absolute():
                p = get_git_root() / p
            os.environ[k] = str(p)
            if Path(v).exists() and k in WORKING_DIRS and clean_working_dirs:
                shutil.rmtree(v)
            p.mkdir(parents=True, exist_ok=True)
        else:
            os.environ[k] = str(v)
        env_vars[k] = os.environ[k]

    return env_vars


import_debug.bug.pop("src/lib/misc.py")


def dockerize_volume(
    path: str | Path,
    root_dir: Path | None = None,
) -> Path:
    """Takes the incoming path and replaces root_dir in path with /mnt if cfg.use_docker is True"""
    from src.lib.config import cfg

    if not root_dir:
        root_dir = cfg.working_dir

    if cfg.USE_DOCKER:
        return Path("/mnt") / Path(path).relative_to(root_dir)
    else:
        return Path(path)


def sanitize(v):
    if isinstance(v, (int, float, bool, str, type(None))):
        return v
    elif isinstance(v, Iterable):
        return [sanitize(_v) for _v in v]
    elif isinstance(v, dict):
        return {k: sanitize(_v) for k, _v in v.items()}
    return str(v)


def to_json(obj: dict[str, Any]) -> str:
    """Converts an object to a JSON string."""
    import json

    return json.dumps(
        {k: sanitize(v) for k, v in obj.items()}, indent=4, sort_keys=True
    )
