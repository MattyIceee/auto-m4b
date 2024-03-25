import functools
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast, Concatenate, Literal, ParamSpec, TypeVar

import numpy as np

P = ParamSpec("P")
R = TypeVar("R")

AudiobookFmt = Literal["m4b", "mp3", "m4a", "wma"]
Operation = Literal["move", "copy"]
OverwriteMode = Literal["skip", "skip-silent", "overwrite", "overwrite-silent"]
OVERWRITE_MODES = ["skip", "skip-silent", "overwrite", "overwrite-silent"]
PathType = Literal["dir", "file"]
SizeFmt = Literal["bytes", "human"]
DurationFmt = Literal["seconds", "human"]
DirName = Literal[
    "inbox", "converted", "archive", "fix", "backup", "build", "merge", "trash"
]
FailedBooksDict = dict[str, float]
BookHashesDict = dict[str, str]
ExifWriter = Literal["exiftool", "eyed3"]
BookDirStructure = Literal[
    # "flat" - all audio files are in the root/top-level directory
    "flat",
    # "flat_nested" - all audio files are in a single subdirectory
    "flat_nested",
    # "multi_nested" - audio files are in multiple subdirectories, but can't determine if multi-series or multi-disc
    "multi_disc",
    # "multi_book" - audio files are in multiple subdirectories, appears to be multiple books
    "multi_book",
    # "mixed" - audio files are in the root/top-level directory and in nested subdirectories, no way to determine the book structure
    "multi_nested",
    # "multi_disc" - audio files are in multiple subdirectories, appears to be a multi-disc book
    "mixed",
    # "file" - a single audio file as the target path, vs. a directory
    "file",
    # "standalone" - a single audio file in the root/top-level directory or subdirectory
    "standalone",
    # "empty" - no audio files found
    "empty",
]
BookDirMap = Sequence[tuple[Path]] | Sequence[tuple[Path, Sequence[Path]]]
TagSource = Literal[
    "title",
    "album",
    "sortalbum",
    "common_title",
    "common_album",
    "common_sortalbum",
    "unknown",
]
ENV_DIRS = [
    "INBOX_FOLDER",
    "CONVERTED_FOLDER",
    "ARCHIVE_FOLDER",
    "BACKUP_FOLDER",
    "WORKING_FOLDER",
    "BUILD_FOLDER",
    "MERGE_FOLDER",
    "TRASH_FOLDER",
]

STANDARD_BITRATES = np.array(
    [24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320], int
)  # see https://superuser.com/a/465660/254022

MEMO_TTL = 60 * 5  # 5 minutes


class BadFileError(Exception): ...


# Source: https://stackoverflow.com/a/71968448/1214800
def copy_kwargs(func: Callable[P, R]) -> Callable[..., Callable[P, R]]:
    """Decorator does nothing but casts the original function to match the given function signature"""

    @functools.wraps(func, updated=())
    def _cast_func(_func: Callable[..., Any]) -> Callable[P, R]:
        return cast(Callable[P, R], _func)

    if not callable(func):
        raise RuntimeError(
            f"You must pass a function to this decorator, got {func} instead."
        )

    return _cast_func


F = TypeVar("F")


def copy_kwargs_omit_first_arg(
    func: Callable[Concatenate[F, P], R],
) -> Callable[..., Callable[P, R]]:
    """Decorator does nothing but casts the original function to match the given function signature, but omits the first parameter"""

    @functools.wraps(func, updated=())
    def _cast_func(_func: Callable[..., Any]) -> Callable[P, R]:
        return cast(Callable[P, R], _func)

    if not callable(func):
        raise RuntimeError(
            f"You must pass a function to this decorator, got {func} instead."
        )

    return _cast_func
