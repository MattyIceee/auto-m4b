import fnmatch
import os
import re
import shutil
import time
from collections.abc import Callable, Generator, Iterable
from pathlib import Path
from typing import Any, cast, Literal, NamedTuple, overload, TYPE_CHECKING

from src.lib.config import AUDIO_EXTS
from src.lib.formatters import human_size
from src.lib.misc import isorted, try_get_stat_mtime
from src.lib.parsers import is_maybe_multi_book_or_series, is_maybe_multi_disc
from src.lib.term import (
    print_debug,
    print_error,
    print_grey,
    print_notice,
    print_warning,
)
from src.lib.typing import (
    BookDirMap,
    BookDirStructure,
    BookHashesDict,
    copy_kwargs_omit_first_arg,
    Operation,
    OVERWRITE_MODES,
    OverwriteMode,
    PathType,
    SizeFmt,
)

if TYPE_CHECKING:
    from src.lib.audiobook import Audiobook


@overload
def find_files_in_dir(
    d: Path,
    *,
    resolve: Literal[False] = False,
    ignore_files: list[str] = [],
    only_file_exts: list[str] = [],
    mindepth: int | None = None,
    maxdepth: int | None = None,
) -> list[str]: ...


@overload
def find_files_in_dir(
    d: Path,
    *,
    resolve: Literal[True] = True,
    ignore_files: list[str] = [],
    only_file_exts: list[str] = [],
    mindepth: int | None = None,
    maxdepth: int | None = None,
) -> list[Path]: ...


def find_files_in_dir(  # type: ignore
    d: Path,
    *,
    resolve: bool | None = None,
    ignore_files: list = [],
    only_file_exts: list[str] = [],
    mindepth: int | None = None,
    maxdepth: int | None = None,
) -> list[str | Path]:
    """
    Finds all files in a directory and its subdirectories.

    Parameters:
    d (Path): The base directory to start the search from.
    resolve (bool, optional): Whether to resolve to absolute paths. Defaults to False (only returns files relative to the base directory).
    ignore_files (list[str], optional): A list of file names to ignore. Defaults to [].
    only_file_exts (list[str], optional): A list of file extensions to include in the count. Defaults to AUDIO_EXTS.
    mindepth (int | None, optional): The minimum depth of directories to search. This is 0-based, so a mindepth of 0 includes files directly in the base directory. Defaults to None, which includes all depths.
    maxdepth (int | None, optional): The maximum depth of directories to search. This is 0-based, so a maxdepth of 0 includes only files directly in the base directory. Defaults to None, which includes all depths.

    Returns:
    list[str | Path]: A list of file names (str) or Path objects (if absolute=True)
    """

    if d.is_file():
        raise NotADirectoryError(f"Error: {d} is not a directory")

    def depth(p: Path) -> int:
        return len(p.parts) - len(d.parts)

    return [
        f if resolve else str(f.relative_to(d))
        for f in isorted(d.rglob("*"))
        if all(
            [
                f.is_file(),
                not f.name.startswith("."),
                f.name not in ignore_files,
                not only_file_exts or f.suffix in only_file_exts,
                mindepth is None or depth(f) >= mindepth,
                maxdepth is None or depth(f) <= maxdepth,
            ]
        )
    ]


def count_audio_files_in_dir(
    d: Path,
    *,
    only_file_exts: list[str] = [],
    mindepth: int | None = None,
    maxdepth: int | None = None,
) -> int:
    """
    Count the number of audio files in a directory and its subdirectories.

    Parameters:
    d (Path): The base directory to start the search from.
    only_file_exts (list[str], optional): A list of file extensions to include in the count. Defaults to AUDIO_EXTS.
    mindepth (int | None, optional): The minimum depth of directories to search. This is 0-based, so a mindepth of 0 includes files directly in the base directory. Defaults to None, which includes all depths.
    maxdepth (int | None, optional): The maximum depth of directories to search. This is 0-based, so a maxdepth of 0 includes only files directly in the base directory. Defaults to None, which includes all depths.

    Returns:
    int: The number of audio files found.
    """

    audio_files = find_files_in_dir(
        d,
        resolve=True,
        only_file_exts=only_file_exts or AUDIO_EXTS,
        mindepth=mindepth,
        maxdepth=maxdepth,
    )

    return len(audio_files)


def count_audio_files_in_inbox() -> int:
    from src.lib.config import cfg

    return count_audio_files_in_dir(cfg.inbox_dir, only_file_exts=cfg.AUDIO_EXTS)


def count_standalone_books_in_inbox() -> int:
    from src.lib.config import cfg

    return count_audio_files_in_dir(
        cfg.inbox_dir, only_file_exts=cfg.AUDIO_EXTS, maxdepth=0
    )


@overload
def get_size(
    path: Path, fmt: Literal["bytes"] = "bytes", only_file_exts: list[str] = []
) -> int: ...


@overload
def get_size(
    path: Path, fmt: Literal["human"] = "human", only_file_exts: list[str] = []
) -> str: ...


def get_size(
    path: Path, fmt: SizeFmt = "bytes", only_file_exts: list[str] = []
) -> str | int:
    # takes a file or directory and returns the size in either bytes or human readable format, only counting audio files
    # if no path specified, assume current directory

    if not path.exists():
        raise FileNotFoundError(f"Cannot get size, '{path}' does not exist")

    def file_ext_ok(f: Path) -> bool:
        return f.suffix in only_file_exts if only_file_exts else True

    size: int

    # if path is a file, return its size
    if path.is_file():
        if not file_ext_ok(path):
            raise ValueError(f"File {path} is not an audio file")
        size = path.stat().st_size
    elif path.is_dir():
        size = sum(
            f.stat().st_size
            for f in path.glob("**/*")
            if f.is_file() and file_ext_ok(f)
        )
    return human_size(size) if fmt == "human" else size


def is_ok_to_delete(
    path: Path,
    max_size: int = 10240,
    only_file_exts: list[str] = [],
    ignore_hidden: bool = True,
) -> bool:
    src_dir_size = get_size(path, fmt="bytes")

    if ignore_hidden:
        files = [
            f for f in path.rglob("*") if f.is_file() and not f.name.startswith(".")
        ]

    else:
        files = [f for f in path.rglob("*") if f.is_file()]

    if only_file_exts:
        files = [f for f in files if f.suffix in only_file_exts]

    # ok to delete if no visible or un-ignored files or if size is less than 10kb
    return len(files) == 0 or src_dir_size < max_size


def check_src_dst(
    src: Path,
    src_type: PathType,
    dst: Path,
    dst_type: PathType,
    overwrite_mode: OverwriteMode = "skip",
):
    # valid overwrite modes are "skip" (default), "overwrite", and "overwrite-silent"
    if overwrite_mode not in OVERWRITE_MODES:
        raise ValueError("Invalid overwrite mode")

    # if dst should be dir but does not exist, try to create it
    if dst_type == "dir" and not dst.is_dir():
        dst.mkdir(parents=True, exist_ok=True)

    # if src or dst do not exist, raise an error
    if not src.exists():
        raise FileNotFoundError(f"Source {src_type} {src} does not exist")

    if not dst.exists():
        raise FileNotFoundError(f"Destination {dst_type} {dst} does not exist")

    if src_type == "dir" and not src.is_dir():
        raise NotADirectoryError(f"Source {src} is not a directory")

    if src_type == "file" and not src.is_file():
        raise FileNotFoundError(f"Source {src} is not a file")

    if dst_type == "dir" and not dst.is_dir():
        raise NotADirectoryError(f"Destination {dst} is not a directory")

    if dst_type == "file" and not dst.parent.is_dir():
        raise NotADirectoryError(f"Destination parent dir {dst.parent} does not exist")

    if dst_type == "file" and dst.is_file() and overwrite_mode == "skip":
        raise FileExistsError(
            f"Destination file {dst} already exists and overwrite mode is 'skip'"
        )

    return True


def src_and_dst_are_on_same_partition(src: Path, dst: Path) -> bool:
    return src.stat().st_dev == dst.stat().st_dev


def rmdir_force(dir_path: Path):
    # Remove the directory and handle errors
    if not dir_path.is_dir():
        return
    try:
        shutil.rmtree(dir_path)
    except OSError as e:
        raise OSError(
            f"Unable to delete {dir_path}, please delete it manually and try again"
        ) from e


def rm_all_empty_dirs(dir_path: Path):
    # Recursively remove all empty directories in the current directory, using ok_to_del
    for current_dir in dir_path.glob("**"):
        if (
            current_dir.is_dir()
            and not any(current_dir.iterdir())
            and is_ok_to_delete(current_dir)
        ):
            rmdir_force(current_dir)


def _mv_or_cp_dir_contents(
    operation: Operation,
    src_dir: Path,
    dst_dir: Path,
    *,
    overwrite_mode: OverwriteMode | None = None,
    ignore_files: list[str] = [],
    silent_files: list[str] = [],
    only_file_exts: list[str] = [],
):

    from src.lib.config import cfg

    if operation not in ["move", "copy"]:
        raise ValueError("Invalid operation")

    rm_empty_src_dir = operation == "move"

    overwrite_mode = overwrite_mode or cfg.OVERWRITE_MODE

    if overwrite_mode not in OVERWRITE_MODES:
        raise ValueError("Invalid overwrite mode")

    dst_dir.mkdir(parents=True, exist_ok=True)

    if operation == "move" and not src_and_dst_are_on_same_partition(src_dir, dst_dir):
        if cfg.DEBUG:
            print_debug(
                f"Source and destination are not on the same partition, using copy instead of move\n src: {src_dir}\n dst: {dst_dir}"
            )
        operation = "copy"

    # ignore if src ends in .bak
    if str(src_dir).endswith(".bak"):
        print_notice(f"Source {src_dir} ends in .bak, ignoring")
        return

    verbed = "moved" if operation == "move" else "copied"
    verbing = "moving" if operation == "move" else "copying"

    # Check source and destination directories
    if not check_src_dst(src_dir, "dir", dst_dir, "dir", overwrite_mode):
        raise FileNotFoundError("Source or destination directory does not exist")

    # Check for files that may require overwriting
    files_common_to_both = set(
        find_files_in_dir(src_dir, ignore_files=ignore_files)
    ) & set(find_files_in_dir(dst_dir, ignore_files=ignore_files))

    # remove files that are in silent_files from files_common_to_both
    files_common_to_both = [f for f in files_common_to_both if f not in silent_files]

    if files_common_to_both and not overwrite_mode.endswith("silent"):
        if overwrite_mode == "overwrite":
            print_warning(f"Warning: Some files in {dst_dir} will be overwritten:")
        else:
            print_error(
                f"Error: Some files already exist in {dst_dir} and will not be {verbed}:"
            )

        for file in files_common_to_both:
            print_grey(f"     - {file}")

    if not any(src_dir.iterdir()):
        print_notice(f"No files found in {src_dir}, skipping")
        return

    def ok_to_mv_or_cp(src_file: Path, dst_file: Path) -> bool:

        if any(
            [
                (not src_file.is_file()),
                (src_file.name in ignore_files),
                (only_file_exts and src_file.suffix not in only_file_exts),
                (dst_file.is_file() and not overwrite_mode.startswith("overwrite")),
            ]
        ):
            return False

        return True

    files_not_verbed = []

    for src_file in src_dir.glob("*"):
        if src_file.is_dir():
            _mv_or_cp_dir_contents(
                operation,
                src_file,
                dst_dir / src_file.name,
                overwrite_mode=overwrite_mode,
                ignore_files=ignore_files,
                only_file_exts=only_file_exts,
            )
        dst_file = dst_dir / src_file.name
        if ok_to_mv_or_cp(src_file, dst_file):
            if operation == "copy":
                shutil.copy2(src_file, dst_file)
            elif operation == "move":
                shutil.move(src_file, dst_file)
            if not dst_file.is_file():
                files_not_verbed.append(src_file)

    # files_not_in_right = set(find_files(src_dir, ignore_files)) - set(
    #     find_files(dst_dir, ignore_files)
    # )

    if files_not_verbed:
        if not overwrite_mode.endswith("silent"):
            print_error(f"Error: Some files in {src_dir} could not be {verbed}:")
            for file in files_not_verbed:
                print_grey(f"     - {file}")
        if overwrite_mode == "overwrite":
            err = f"Some files in {src_dir} could not be {verbed}"
            raise FileNotFoundError(err)

    # Remove the source directory if empty and conditions permit, if moving
    if (
        rm_empty_src_dir
        and operation == "move"
        and is_ok_to_delete(src_dir, only_file_exts=only_file_exts)
    ):
        try:
            rmdir_force(src_dir)
        except OSError:
            print_warning(
                f"Warning: {src_dir} was not deleted after {verbing} files because it is not empty"
            )


@copy_kwargs_omit_first_arg(_mv_or_cp_dir_contents)
def mv_dir_contents(*args, **kwargs):
    _mv_or_cp_dir_contents("move", *args, **kwargs)


@copy_kwargs_omit_first_arg(_mv_or_cp_dir_contents)
def cp_dir_contents(*args, **kwargs):
    _mv_or_cp_dir_contents("copy", *args, **kwargs)


def _mv_or_copy_dir(
    operation: Operation,
    src_dir: Path,
    dst_dir: Path,
    *,
    overwrite_mode: OverwriteMode = "skip",
    silent_files: list[str] = [],
):
    """Moves or copies the source directory *into* the destination directory. For example:

    `cp_dir('/path/to/src', '/path/to_other/dst')`

    ...will result in:

    `/path/to_other/dst/src`

    Default overwrite mode is 'skip', which will raise an error if the destination directory already exists, because we shouldn't ever be automatically overwriting an entire directory.
    """

    # check that both are dirs:
    if not src_dir.is_dir():
        raise NotADirectoryError(f"Source {src_dir} is not a directory")
    if not dst_dir.is_dir():
        raise NotADirectoryError(f"Destination {dst_dir} is not a directory")

    # check that src_dir.name and dst_dir.name are not the same, if they are, append src_dir.name to dst_dir
    if src_dir.name == dst_dir.name:
        print_warning(
            f"Warning: It looks like you tried to use mv_dir or cp_dir by including the destination directory name in the path, e.g. mv_dir('/path/to/dir', '/path/to_other/dir'). This will result in the source directory being moved into the destination directory, e.g. /path/to_other/dir/dir. If you want to move the contents of the source directory into the destination directory, use mv_dir_contents or cp_dir_contents instead."
        )

    dst_dir = dst_dir / src_dir.name
    _mv_or_cp_dir_contents(
        operation,
        src_dir,
        dst_dir,
        overwrite_mode=overwrite_mode,
        silent_files=silent_files,
    )


@copy_kwargs_omit_first_arg(_mv_or_copy_dir)
def mv_dir(*args, **kwargs):
    _mv_or_copy_dir("move", *args, **kwargs)


@copy_kwargs_omit_first_arg(_mv_or_copy_dir)
def cp_dir(*args, **kwargs):
    _mv_or_copy_dir("copy", *args, **kwargs)


def mv_file_to_dir(
    source_file: Path,
    dst_dir: Path,
    *,
    new_filename: str | None = None,
    overwrite_mode: OverwriteMode | None = None,
) -> None:
    # Check source and destination
    if not source_file.is_file():
        raise FileNotFoundError(f"Source file {source_file} does not exist")
    if not dst_dir.is_dir():
        raise NotADirectoryError(f"Destination {dst_dir} is not a directory")

    dst = dst_dir if new_filename is None else dst_dir / new_filename

    if dst.is_file() and overwrite_mode == "skip":
        raise FileExistsError(
            f"Destination file {dst} already exists and overwrite mode is 'skip'"
        )
    if dst.is_file() and overwrite_mode != "overwrite-silent":
        print_warning(f"Warning: {dst} already exists and will be overwritten")

    # Move the file
    shutil.move(source_file, dst)


def cp_file_to_dir(
    source_file: Path,
    dst_dir: Path,
    new_filename: str | None = None,
    overwrite_mode: OverwriteMode | None = None,
) -> None:
    # Check source and destination
    if not source_file.is_file():
        raise FileNotFoundError(f"Source file {source_file} does not exist")
    if not dst_dir.is_dir():
        raise NotADirectoryError(f"Destination {dst_dir} is not a directory")

    dst_file = dst_dir / new_filename if new_filename else dst_dir / source_file.name

    if dst_file.is_file() and overwrite_mode == "skip":
        raise FileExistsError(
            f"Destination file {dst_file} already exists and overwrite mode is 'skip'"
        )
    if dst_file.is_file() and overwrite_mode != "overwrite-silent":
        print_warning(f"Warning: {dst_file} already exists and will be overwritten")

    # Copy the file
    shutil.copy2(source_file, dst_dir)

    # Rename the file if new_filename is specified
    if new_filename:
        shutil.move(dst_dir / source_file.name, dst_file)


def dir_is_empty_ignoring_hidden_files(d: Path) -> bool:
    if not d.is_dir():
        return True
    return not any(filter_ignored(f for f in d.iterdir() if not f.name.startswith(".")))


def flatten_files_in_dir(
    path: Path,
    *,
    preview: bool = False,
    on_conflict: Literal["raise", "skip"] = "skip",
):
    """Given a directory, moves all files in any subdirectories to the root directory then removes the subdirectories."""
    if not path.is_dir():
        raise NotADirectoryError(f"Error: {path} is not a directory")

    # if path is a dir, get all files in the dir and its subdirs
    files = [f for f in filter_ignored(isorted(path.rglob("*"))) if f.is_file()]
    new_files = []
    for f in files:
        new_files.append(path / f.name)
        if not preview:
            # if file would overwrite an existing file, raise or skip
            if (path / f.name).exists():
                if on_conflict == "raise":
                    raise FileExistsError(
                        f"Error: {path / f.name} already exists in the directory"
                    )
                elif on_conflict == "skip":
                    continue
            shutil.move(f, path / f.name)

    # remove the subdirs
    if not preview:
        for d in path.rglob("*"):
            if d.is_dir() and dir_is_empty_ignoring_hidden_files(d):
                shutil.rmtree(d, ignore_errors=True)

    return new_files


def flattening_files_in_dir_affects_order(path: Path) -> bool:
    """Compares the order of files in a directory, both before and after flattening, by checking if the file names are in the same order."""

    files_flat = [
        f.stem for f in filter_ignored(flatten_files_in_dir(path, preview=True))
    ]
    files_flat_sorted = list(isorted(files_flat))

    return files_flat_sorted != files_flat


def name_matches(name: Any, match_name: str | None = None) -> bool:
    from src.lib.config import cfg

    if cfg.MATCH_NAME:
        match_name = cfg.MATCH_NAME

    if not match_name:
        return True

    return re.search(match_name, str(name), re.I) is not None


def find_base_dirs_with_audio_files(
    root: Path,
    mindepth: int | None = None,
    maxdepth: int | None = None,
) -> list[Path]:
    """Given a root directory, returns a list of all base directories that contain audio files. E.g.,
    if the root directory is '/path/to' and contains:
    - /path/to/folder1/file1
    - /path/to/folder1/folder2/file2
    - /path/to/folder1/folder2/file3
    - /path/to/folder1/folder2/file4
    - /path/to/folder2/file1
    - /path/to/folder2/file2
    - /path/to/folder2/folder3/file3

    then the return value will be:
    - /path/to/folder1
    - /path/to/folder2
    """

    if not root.is_dir():
        raise NotADirectoryError(f"Error: {root} is not a directory")

    def depth(p: Path) -> int:
        return len(p.parts) - len(root.parts)

    def is_valid_dir(_d: Path) -> bool:
        return _d.is_dir() and all(
            [
                count_audio_files_in_dir(_d, mindepth=0, maxdepth=1) > 0,
                mindepth is None or depth(_d) >= mindepth,
                maxdepth is None or depth(_d) <= maxdepth,
            ]
        )

    all_roots_with_audio_files = list(
        set(
            [
                root / d.relative_to(root).parts[0]
                for d in root.rglob("*")
                if is_valid_dir(d)
            ]
        )
    )

    return list(isorted(all_roots_with_audio_files))


def find_book_dirs_in_inbox():
    from src.lib.config import cfg

    return find_base_dirs_with_audio_files(cfg.inbox_dir, mindepth=1)


def find_book_audio_files(
    book: "Audiobook | Path",
) -> tuple[BookDirStructure, BookDirMap]:
    """Given a book directory, returns a tuple of the book's directory structure type, and a map of the book's audio files."""
    from src.lib.config import cfg

    path = book if isinstance(book, Path) else book.inbox_dir

    if path.is_file():
        return ("file", [(path,)])

    all_audio_files = find_files_in_dir(
        path, resolve=True, only_file_exts=cfg.AUDIO_EXTS
    )
    root_audio_files = [f for f in all_audio_files if f.parent == path]

    if not all_audio_files:
        return ("empty", [])

    if len(all_audio_files) == 1:
        return ("standalone", [(all_audio_files[0],)])

    root_audio_files_tuples: BookDirMap = [(f,) for f in root_audio_files]

    if len(root_audio_files) == len(all_audio_files):
        return ("flat", root_audio_files_tuples)

    # generate a dictionary of nested audio files keyed by the directory they're in
    nested_audio_files_dict = {
        d: [f for f in all_audio_files if f.parent == d]
        for d in [f.parent for f in all_audio_files]
        if d != path and d.is_dir()
    }

    nested_audio_dirs = nested_audio_files_dict.keys()

    if not root_audio_files and len(nested_audio_files_dict) == 1:
        first_nested_dir = next(iter(nested_audio_dirs))
        return (
            "flat_nested",
            [
                (
                    first_nested_dir,
                    nested_audio_files_dict[first_nested_dir],
                )
            ],
        )

    # if audio files exist in more than one level, return the structure as "mixed"
    number_of_different_levels = len(
        set([len(f.relative_to(path).parts) for f in all_audio_files])
    )
    if number_of_different_levels > 1:
        nested_dirs_tuples: BookDirMap = [
            (d, nested_audio_files_dict[d]) for d in nested_audio_files_dict
        ]
        return (
            "mixed",
            cast(BookDirMap, root_audio_files_tuples + nested_dirs_tuples),
        )

    multi_disc = any(is_maybe_multi_disc(d.name) for d in nested_audio_dirs)
    multi_book = any(is_maybe_multi_book_or_series(d.name) for d in nested_audio_dirs)

    file_map = [
        *[(f,) for f in root_audio_files],
        *[
            (d, find_files_in_dir(d, resolve=True, only_file_exts=cfg.AUDIO_EXTS))
            for d in nested_audio_dirs
        ],
    ]

    struc: BookDirStructure
    if multi_disc:
        struc = "multi_disc"
    elif multi_book:
        struc = "multi_book"
    elif len(nested_audio_dirs) > 0 and number_of_different_levels == 1:
        struc = "multi_nested"
    else:
        struc = "mixed"

    return (
        struc,
        file_map,
    )


def clean_dir(dir_path: Path) -> None:
    dir_path = dir_path.resolve()

    rmdir_force(dir_path)

    # Recreate the directory
    dir_path.mkdir(parents=True, exist_ok=True)

    # Check if the directory is writable
    if not os.access(dir_path, os.W_OK):
        raise PermissionError(
            f"'{dir_path}' is not writable by current user, please fix permissions and try again"
        )

    # Check if the directory is empty
    if any(dir_path.iterdir()):
        raise OSError(
            f"'{dir_path}' is not empty, please empty it manually and try again"
        )


@overload
def find_first_audio_file(path: Path, throw: bool = True) -> Path: ...


@overload
def find_first_audio_file(path: Path, throw: bool = False) -> Path | None: ...


def find_first_audio_file(path: Path, throw: bool = True) -> Path | None:

    if path.is_file() and path.suffix in AUDIO_EXTS:
        return path

    audio_files = find_files_in_dir(path, resolve=True, only_file_exts=AUDIO_EXTS)

    if audio_file := next(iter(sorted(audio_files)), None):
        return audio_file
    if throw:
        raise FileNotFoundError(f"No audio files found in {path}")
    return None


def find_next_audio_file(current_file: Path) -> Path | None:

    # if path is a file, get its parent dir or use the parent dir of the current file
    parent = current_file.parent if current_file.is_file() else current_file

    audio_files = find_files_in_dir(
        parent,
        resolve=True,
        ignore_files=[current_file.name],
        only_file_exts=AUDIO_EXTS,
    )

    if not audio_files:
        return None

    return find_first_audio_file(audio_files[0])


def find_cover_art_file(path: Path) -> Path | None:
    supported_image_exts = [".jpg", ".jpeg", ".png"]
    all_images_in_dir = [f for f in path.rglob("*") if f.suffix in supported_image_exts]

    # if any of the images match *cover* or *folder*, return it
    img = next(
        (i for i in all_images_in_dir if i.name.lower() in ["cover", "folder"]), None
    )

    # otherwise, find the biggest image
    if not img and all_images_in_dir:
        img = max(all_images_in_dir, key=lambda f: f.stat().st_size)

    # if img less than 10kb, return None
    if img and img.stat().st_size < 10240:
        return None

    return img


def filter_ignored(
    paths: Iterable[Path | None] | Generator[Path, Any, Any],
) -> list[Path]:
    from src.lib.config import cfg

    paths = [p for p in paths if p]

    return [
        p
        for p in paths
        if not any(fnmatch.filter([str(p.name)], ignore) for ignore in cfg.IGNORE_FILES)
    ]


def find_recently_modified_files_and_dirs(
    path: Path,
    within_seconds: float = 0,
    *,
    since: float = 0,
    only_file_exts: list[str] = [],
) -> list[tuple[Path, float, float]]:
    from src.lib.config import cfg

    if within_seconds <= 0:
        within_seconds = 2 if cfg.TEST else 15
    current_time = time.time()
    recent_items: list[tuple[Path, float, float]] = []

    found_items = list(
        sorted(
            [(f, try_get_stat_mtime(f)) for f in filter_ignored(path.rglob("*"))],
            key=lambda x: -x[1],
        )
    )

    for path, last_modified in found_items:
        # check p against cfg.IGNORE_FILES - a list of glob patterns to ignore
        if not path.exists():
            continue  # protect against race conditions & async ops
        if path.is_file() and only_file_exts and path.suffix in only_file_exts:
            continue
        age = (since or current_time) - last_modified
        if age < within_seconds:
            recent_items.append((path, age, last_modified))

    return recent_items


def last_updated_at(path: Path, *, only_file_exts: list[str] = []) -> float:
    find_all_sorted_by_modified = find_recently_modified_files_and_dirs(
        path, 60, since=0, only_file_exts=only_file_exts
    )
    paths_m = [m for _1, _2, m in find_all_sorted_by_modified]
    return max(paths_m, default=0)


def last_updated_audio_files_at(path: Path) -> float:
    return last_updated_at(path, only_file_exts=AUDIO_EXTS)


def inbox_last_updated_at() -> float:
    from src.lib.config import cfg

    return last_updated_at(cfg.inbox_dir, only_file_exts=cfg.AUDIO_EXTS)


def was_recently_modified(
    path: Path,
    within_seconds: float = 0,
    since: float = 0,
    *,
    only_file_exts: list[str] = [],
) -> bool:
    from src.lib.config import cfg

    if within_seconds <= 0:
        within_seconds = 2 if cfg.TEST else 15

    within_seconds = max(within_seconds, 0)

    this_m = time.time() - try_get_stat_mtime(path) < within_seconds

    if path.is_file():
        if only_file_exts and path.suffix not in only_file_exts:
            return False
        return this_m

    recents = find_recently_modified_files_and_dirs(
        path, within_seconds, since=since, only_file_exts=only_file_exts
    )
    return bool(this_m or recents)


def inbox_was_recently_modified() -> bool:
    from src.lib.config import cfg

    return was_recently_modified(cfg.inbox_dir, only_file_exts=cfg.AUDIO_EXTS)


def hash_dir(path: Path, *, only_file_exts: list[str] = [], debug: bool = True) -> str:
    """Makes a has of the dir's contents of filenames and file sizes in an array, sorted by filename
    then hashes the array"""
    import hashlib

    def hash_file(f: Path) -> str:
        if any(
            [
                not f.is_file(),
                f.name.startswith("."),
                only_file_exts and f.suffix not in only_file_exts,
            ]
        ):
            return ""
        return f"{f.relative_to(path)}|{f.stat().st_size}"

    files = sorted(
        filter(
            None, [hash_file(f) for f in filter_ignored(path.rglob("*"))]
        ),  # case insensitive sort
        key=lambda f: f.lower(),
    )
    if debug:
        return files  # type: ignore
    return hashlib.md5(":".join(files).encode()).hexdigest()


def hash_dir_audio_files(path: Path, *, debug: bool = False) -> str:
    """Makes a hash of the dir's audio files' filenames and file sizes in an array, sorted by filename
    then hashes the array"""
    return hash_dir(path, only_file_exts=AUDIO_EXTS, debug=debug)


def hash_inbox():
    from src.lib.config import cfg

    return hash_dir_audio_files(cfg.inbox_dir)


def hash_inbox_books(dirs: list[Path]) -> BookHashesDict:
    return {p.name: hash_dir_audio_files(p) for p in dirs if p.exists()}


# TODO: No need for fix dir anymore, move this functionality into fail_book and remove func
def mv_to_fix_dir(book: "Audiobook", fail_book: Callable[["Audiobook"], None]):

    fail_book(book)
    # if cfg.NO_FIX:
    book.write_log("This book needs to be fixed before it can be converted.")
    book.set_active_dir("inbox")
    if (build_log := book.build_dir / f"m4b-tool.{book}.log") and build_log.exists():
        if book.log_file.exists():
            # update inbox log with build dir log, preceded by a \n
            with open(build_log, "r") as f:
                log = f.read()
            with open(book.log_file, "a") as f:
                f.write(f"\n{log}")
        else:
            # move build dir log to inbox dir
            shutil.move(build_log, book.log_file)
    return
    # smart_print(f"Moving to fix folder → {tint_path(book.fix_dir)}")
    # mv_dir(book.inbox_dir, cfg.fix_dir)
    # cp_file_to_dir(book.log_file, book.fix_dir, new_filename=f"m4b-tool.{book}.log")
    # book.set_active_dir("fix")


FlatListOfFilesInDir = NamedTuple(
    "FlatListOfFilesInDir",
    [
        ("original_order", list[Path]),
        ("sorted_alphabetically", list[Path]),
        ("is_same_order", bool),
    ],
)


def get_flat_list_of_files_in_dir(
    path: Path, only_file_exts: list[str] = []
) -> tuple[list[Path], list[Path], bool]:
    """Takes a path of all nested files and returns a flat list of all files relative to the path. E.g.,
    if the path contains:
    - /path/to/folder/file1
    - /path/to/folder/nested/file2
    - /path/to/folder/nested/file3
    - /path/to/folder/nested2/file4
    then the return value will be:
    - /path/to/folder/file1
    - /path/to/folder/file2
    - /path/to/folder/file3
    - /path/to/folder/file4

    Returns a tuple:
     - a list contains all file names in their original order according to the subdirectory structure
     - a list contains all file names sorted alphabetically (flat)
     - a bool indicating whether the flat list would be in the same order as the original list if the dir structure were flattened.
    """

    if not path.is_dir():
        raise NotADirectoryError(f"Error: {path} is not a directory")

    # if path is a dir, get all files in the dir and its subdirs
    files = [f for f in path.rglob("*") if f.is_file()]
    if only_file_exts:
        files = [f for f in files if f.suffix in only_file_exts]

    flat_files_list = [path / f.name for f in files]
    sorted_files_list = sorted(flat_files_list)
    do_lists_order_match = flat_files_list == sorted_files_list

    return FlatListOfFilesInDir(
        original_order=flat_files_list,
        sorted_alphabetically=sorted_files_list,
        is_same_order=do_lists_order_match,
    )


def compare_dirs_by_files(dir1: Path, dir2: Path) -> list[tuple[Path, int, Path, int]]:
    """Finds files from one dir in another, and includes the file sizes of each"""
    files1 = filter_ignored(dir1.glob("**/*"))
    files2 = filter_ignored(dir2.glob("**/*"))

    # make a list of files matched by name and size, e.g. [(left, left_size, right, right_size), ...]
    files1 = [(f, f.stat().st_size) for f in files1 if f.is_file()]
    files2 = [(f, f.stat().st_size) for f in files2 if f.is_file()]

    mapped_files = []
    for f1, s1 in files1:
        found_in_right = False
        for f2, s2 in files2:
            if f1.name == f2.name and s1 == s2:
                mapped_files.append((f1, s1, f2, s2))
                found_in_right = True
                break
        if not found_in_right:
            mapped_files.append((f1, s1, None, 0))

    return mapped_files
