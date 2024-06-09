import functools
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast, Concatenate, Literal, NamedTuple, ParamSpec, TypeVar

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
BookStructure = Literal[
    "flat",  # all audio files are in the root/top-level directory
    "flat_nested",  # all audio files are in a single subdirectory
    "multi_disc",  # audio files are in multiple subdirectories, appears to be multiple discs of a single book
    "multi_part",  # audio files are in multiple subdirectories, appears to be multiple parts of a single book or series
    "multi_book_series",  # audio files are in multiple subdirectories, appears to be multiple books in a series
    "multi_nested",  # audio files are in multiple subdirectories, but can't determine if multi-series or multi-disc
    "multi_mixed",  # audio files are in the root dir and subdirectories, but can't determine if multi-series or multi-disc
    "standalone",  # a standalone audio file in the root/top-level directory
    "single",  # a single audio file in a subdirectory
    "readarr_standard", # all audio files in double sub directory following "/Author/Book Title/Author - Book Title (chapter #).mp3"
    "empty",  # no audio files found
]
InboxDirMap = Sequence[tuple[Path]] | Sequence[tuple[Path, Sequence[Path]]]
ScoredProp = Literal["title", "author", "narrator", "date"]
TagSource = Literal[
    "title",
    "album",
    "sortalbum",
    "common_title",
    "common_album",
    "common_sortalbum",
    "artist",
    "albumartist",
    "common_artist",
    "common_albumartist",
    "comment",
    "composer",
    "date",
    "year",
    "fs",
    "unknown",
]
AdditionalTags = Literal["cover", "track", "encoded by", "date", "genre", "publisher"]
NameParserTarget = Literal["fs", "generic", "comment"]
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
SCAN_TTL = 10  # 10 seconds


class BadFileError(Exception): ...


AuthorNarrator = NamedTuple("AuthorNarrator", [("author", str), ("narrator", str)])


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
