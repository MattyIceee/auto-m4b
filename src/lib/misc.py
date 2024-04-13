import asyncio
import functools
import os
import re
import subprocess
from collections.abc import Generator, Iterable
from pathlib import Path, PosixPath
from typing import Any, cast, TypeVar

from dotenv import dotenv_values

from src.lib.typing import DirName, ENV_DIRS


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


def get_numbers_in_string(s: str) -> str:
    """Returns a list of numbers found in a string, in order they are found."""
    return "".join(re.findall(r"\d", s))


G = TypeVar("G")


def re_group(
    match: re.Match[str] | None,
    group: int | str = 0,
    *,
    default: G = "",
) -> G:
    # returns the first match of pattern in string or default if no match
    found = match.group(group) if match else None
    return cast(G, found) if found is not None else default


def isorted(
    iterable: Iterable[T] | Generator[T, None, None], reverse: bool = False
) -> list[T]:
    return sorted(iterable, key=lambda x: str(x).lower(), reverse=reverse)


def compare_trim(a: str, b: str) -> bool:
    return " ".join(a.split()) == " ".join(b.split())


def try_get_stat_mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def is_boolish(v: Any) -> bool:
    return str(v).lower() in ["true", "false", "y", "n", "yes", "no"]


def parse_bool(v: Any) -> bool:
    """Parses a string value to a boolean value."""
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("true", "1", "t", "y", "yes")


def is_floatish(v: Any) -> bool:
    try:
        float(v)
        return True
    except ValueError:
        return False
    except TypeError:
        return False


def parse_float(v: Any) -> float:
    return float(v) if is_floatish(v) else v


def is_intish(v: Any) -> bool:
    try:
        int(v)
        return True
    except ValueError:
        return False
    except TypeError:
        return False


def parse_int(v: Any) -> int:
    return int(v) if is_intish(v) else v


def is_noneish(v: Any) -> bool:
    return v is None or str(v).lower() in ("none", "null", "nil", "n/a")


def parse_none(v: Any) -> None:
    return None if is_noneish(v) else v


def is_maybe_path(v: Any) -> bool:
    checks = [type(v) in [Path, PosixPath], re.match(r"^\.{0,2}/", str(v))]
    return any(checks)


def pathify(k: str, v: Any) -> Path | None:
    # from src.lib.config import WORKING_DIRS

    if not k.endswith("_FOLDER") or not is_maybe_path(v):
        return None
    p = Path(str(v)).expanduser()
    if not p.is_absolute():
        p = get_git_root() / p
    os.environ[k] = str(p)
    # if p.exists() and k in WORKING_DIRS and clean_working_dirs:
    #     shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)
    return p


def set_typed_env_var(
    k: str,
    v: Any,
    dict_to_update: dict[str, Any] | None = None,
):

    if not dict_to_update:
        dict_to_update = {}

    if not v:
        os.environ.pop(k, None)
        dict_to_update[k] = None
    if is_boolish(v):
        os.environ[k] = "Y" if parse_bool(v) else "N"
        dict_to_update[k] = parse_bool(v)
    elif is_maybe_path(v) and (p := pathify(k, v)):
        os.environ[k] = str(v)
        dict_to_update[k] = p
    else:
        os.environ[k] = str(v)
        dict_to_update[k] = os.environ[k]

    return dict_to_update


def load_env(
    env_file: str | Path, clean_working_dirs: bool = False
) -> dict[str, Any | None]:

    env_file = Path(env_file)
    env_vars: dict[str, Any] = {}
    for k, v in dotenv_values(env_file).items():
        set_typed_env_var(k, v, env_vars)

    return env_vars


def dockerize_volume(
    path: str | Path,
    rel_to: Path | None = None,
) -> Path:
    """Takes the incoming path and replaces root_dir in path with /mnt if cfg.use_docker is True"""
    from src.lib.config import cfg

    if not rel_to:
        rel_to = cfg.working_dir

    if cfg.USE_DOCKER:
        return Path("/mnt") / Path(path).relative_to(rel_to)
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


def sh(s: str, n: int = 8) -> str:
    return s[-n:]


def get_dir_name_from_path(p: Path) -> DirName | None:

    def get_env(k: str) -> str:
        return os.getenv(k, "")

    known_dirs = zip(map(Path, map(get_env, ENV_DIRS)), ENV_DIRS)
    for k, d in known_dirs:
        if k in p.parents:
            return cast(DirName, d.lower().replace("_folder", ""))


def get_or_create_event_loop():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError as e:
        if str(e).startswith("There is no current event loop in thread"):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        else:
            raise e
    return loop


C = TypeVar("C")


def singleton(class_: type[C]) -> type[C]:
    class class_w(class_):
        _instance = None

        @functools.wraps(class_.__new__)
        def __new__(cls, *args, **kwargs):
            if class_w._instance is None:
                class_w._instance = super(class_w, cls).__new__(cls, *args, **kwargs)
                class_w._instance._sealed = False
                name = f"{class_.__name__}[singleton]"
                class_w.__name__ = name
                class_w._instance.__name__ = name
                qualname = f"{class_.__qualname__}[singleton]"
                class_w.__qualname__ = qualname
                class_w._instance.__qualname__ = qualname
            return class_w._instance

        @functools.wraps(class_.__init__)
        def __init__(self, *args, **kwargs):
            if self._sealed:
                return
            super(class_w, self).__init__(*args, **kwargs)
            self._sealed = True

        @classmethod
        def destroy(cls):
            cls._instance = None

    return cast(type[C], class_w)


FIX_FFPROBE_COUNTER = 0


def fix_ffprobe():
    global FIX_FFPROBE_COUNTER
    from src.lib.term import print_warning

    fix_cmd = "pip uninstall ffmpeg-python -y && pip install ffmpeg-python==0.2.0 --force-reinstall -y"

    try:
        from ffmpeg import Error, probe

        FIX_FFPROBE_COUNTER += 1
    except ImportError:
        if FIX_FFPROBE_COUNTER == 0:
            print_warning(
                "ffmpeg's ffprobe is not installed or not working. Attempting to fix..."
            )

        os.system(fix_cmd)
        if FIX_FFPROBE_COUNTER < 3:
            FIX_FFPROBE_COUNTER += 1
            fix_ffprobe()
        else:
            raise ImportError(
                f"ffmpeg's ffprobe is not installed, please fix it manually:\n\n $ {fix_cmd}\n\n"
            )
