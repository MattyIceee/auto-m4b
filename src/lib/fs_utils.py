import import_debug

import_debug.bug.push("src/lib/fs_utils.py")
import os
import shutil
import time
from pathlib import Path
from typing import Literal, NamedTuple, overload

import humanize

from src.lib.config import AUDIO_EXTS
from src.lib.term import (
    print_error,
    print_grey,
    print_notice,
    print_warning,
)
from src.lib.typing import Operation, OverwriteMode, PathType, SizeFmt


def count_audio_files_in_dir(
    path: Path,
    only_file_exts: list[str] = AUDIO_EXTS,
    mindepth: int | None = None,
    maxdepth: int | None = None,
) -> int:
    """
    Count the number of audio files in a directory and its subdirectories.

    Parameters:
    path (Path): The base directory to start the search from.
    only_file_exts (list[str], optional): A list of file extensions to include in the count. Defaults to AUDIO_EXTS.
    mindepth (int | None, optional): The minimum depth of directories to search. This is 0-based, so a mindepth of 0 includes files directly in the base directory. Defaults to None, which includes all depths.
    maxdepth (int | None, optional): The maximum depth of directories to search. This is 0-based, so a maxdepth of 0 includes only files directly in the base directory. Defaults to None, which includes all depths.

    Returns:
    int: The number of audio files found.
    """

    def depth(p: Path) -> int:
        return len(p.parts) - len(path.parts)

    return len(
        [
            f
            for f in path.rglob("*")
            if f.is_file()
            and f.suffix in only_file_exts
            and (mindepth is None or depth(f) >= mindepth)
            and (maxdepth is None or depth(f) <= maxdepth)
        ]
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

    size_int: int

    # if path is a file, return its size
    if path.is_file():
        if not file_ext_ok(path):
            raise ValueError(f"File {path} is not an audio file")
        size_int = path.stat().st_size
    elif path.is_dir():
        size_int = sum(
            f.stat().st_size
            for f in path.glob("**/*")
            if f.is_file() and file_ext_ok(f)
        )
    if fmt == "human":
        size_str = humanize.naturalsize(size_int, format="%.2f")
    return size_str if fmt == "human" else size_int


def is_ok_to_delete(
    path: Path, max_size: int = 10240, ignore_hidden: bool = True
) -> bool:
    src_dir_size = get_size(path, fmt="bytes")

    if ignore_hidden:
        files_count = len(
            [f for f in path.rglob("*") if f.is_file() and not f.name.startswith(".")]
        )
    else:
        files_count = len([f for f in path.rglob("*") if f.is_file()])

    # ok to delete if no visible or un-ignored files or if size is less than 10kb
    return files_count == 0 or src_dir_size < max_size


def check_src_dst(
    src: Path,
    src_type: PathType,
    dst: Path,
    dst_type: PathType,
    overwrite_mode: OverwriteMode = "skip",
):
    # valid overwrite modes are "skip" (default), "overwrite", and "overwrite-silent"
    if overwrite_mode not in ["skip", "overwrite", "overwrite-silent"]:
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


def find_files(d: Path, ignore_files: list):
    return [
        str(f.relative_to(d))
        for f in d.rglob("*")
        if f.is_file() and not f.name.startswith(".") and f.name not in ignore_files
    ]


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
    /,
    overwrite_mode: OverwriteMode | None = None,
    ignore_files: list[str] = [],
    only_file_exts: list[str] = [],
):

    from src.lib.config import cfg

    if operation not in ["move", "copy"]:
        raise ValueError("Invalid operation")

    rm_empty_src_dir = operation == "move"

    overwrite_mode = overwrite_mode or cfg.default_overwrite_mode

    if overwrite_mode not in ["skip", "overwrite", "overwrite-silent"]:
        raise ValueError("Invalid overwrite mode")

    dst_dir.mkdir(parents=True, exist_ok=True)

    if operation == "move" and not src_and_dst_are_on_same_partition(src_dir, dst_dir):
        print_notice(
            f"Notice: Source and destination are not on the same partition, using copy instead of move"
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
    files_common_to_both = set(find_files(src_dir, ignore_files)) & set(
        find_files(dst_dir, ignore_files)
    )

    if files_common_to_both and overwrite_mode != "overwrite-silent":
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
        file_ok = (
            src_file.is_file()
            and src_file.name not in ignore_files
            and (not only_file_exts or src_file.suffix in only_file_exts)
        )
        will_overwrite = dst_file.is_file()
        return file_ok and (overwrite_mode != "skip" or not will_overwrite)

    for src_file in src_dir.glob("*"):
        dst_file = dst_dir / src_file.name
        if ok_to_mv_or_cp(src_file, dst_file):
            if operation == "copy":
                shutil.copy2(src_file, dst_file)
            elif operation == "move":
                shutil.move(src_file, dst_file)

    files_not_in_right = set(find_files(src_dir, ignore_files)) - set(
        find_files(dst_dir, ignore_files)
    )

    if files_not_in_right:
        print_error(f"Error: Some files in {src_dir} could not be {verbed}:")
        for file in files_not_in_right:
            print_grey(f"     - {file}")
        raise FileNotFoundError(f"Error: Some files in {src_dir} could not be {verbed}")

    # Remove the source directory if empty and conditions permit, if moving
    if rm_empty_src_dir and operation == "move" and is_ok_to_delete(src_dir):
        try:
            rmdir_force(src_dir)
        except OSError:
            print_warning(
                f"Warning: {src_dir} was not deleted after {verbing} files because it is not empty"
            )


def mv_dir_contents(
    src_dir: Path,
    dst_dir: Path,
    /,
    overwrite_mode: OverwriteMode | None = None,
    only_file_exts: list[str] = [],
    ignore_files: list[str] = [],
):
    _mv_or_cp_dir_contents(
        "move", src_dir, dst_dir, overwrite_mode, ignore_files, only_file_exts
    )


def cp_dir_contents(
    src_dir: Path,
    dst_dir: Path,
    /,
    overwrite_mode: OverwriteMode | None = None,
    only_file_exts: list[str] = [],
    ignore_files: list[str] = [],
):

    _mv_or_cp_dir_contents(
        "copy", src_dir, dst_dir, overwrite_mode, ignore_files, only_file_exts
    )


def _mv_or_copy_dir(
    operation: Operation,
    src_dir: Path,
    dst_dir: Path,
    /,
    overwrite_mode: OverwriteMode | None = None,
):
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
    _mv_or_cp_dir_contents(operation, src_dir, dst_dir, overwrite_mode)


def mv_dir(
    src_dir: Path,
    dst_dir: Path,
    /,
    overwrite_mode: OverwriteMode | None = None,
):
    """Moves the source directory *into* the destination directory. For example:

    `mv_dir('/path/to/src', '/path/to_other/dst')`

    ...will result in:

    `/path/to_other/dst/src`
    """
    _mv_or_copy_dir("move", src_dir, dst_dir, overwrite_mode)


def cp_dir(
    src_dir: Path,
    dst_dir: Path,
    /,
    overwrite_mode: OverwriteMode | None = None,
):
    """Copies the source directory *into* the destination directory. For example:

    `cp_dir('/path/to/src', '/path/to_other/dst')`

    ...will result in:

    `/path/to_other/dst/src`
    """
    _mv_or_copy_dir("copy", src_dir, dst_dir, overwrite_mode)


def mv_file_to_dir(source_file: Path, dst_dir: Path, new_filename: str | None = None):
    # Check source and destination
    if not source_file.is_file():
        raise FileNotFoundError(f"Source file {source_file} does not exist")
    if not dst_dir.is_dir():
        raise NotADirectoryError(f"Destination {dst_dir} is not a directory")

    dst = dst_dir if new_filename is None else dst_dir / new_filename

    # Move the file
    shutil.move(source_file, dst)


def cp_file_to_dir(
    source_file: Path, dst_dir: Path, new_filename: str | None = None
) -> None:
    # Check source and destination
    if not source_file.is_file():
        raise FileNotFoundError(f"Source file {source_file} does not exist")
    if not dst_dir.is_dir():
        raise NotADirectoryError(f"Destination {dst_dir} is not a directory")

    # Copy the file
    shutil.copy2(source_file, dst_dir)

    # Rename the file if new_filename is specified
    if new_filename:
        shutil.move(dst_dir / source_file.name, dst_dir / new_filename)


def flatten_files_in_dir(
    path: Path,
):
    """Given a directory, moves all files in any subdirectories to the root directory then removes the subdirectories."""
    # if no path specified, assume current directory
    if not path.is_dir():
        raise NotADirectoryError(f"Error: {path} is not a directory")

    # if path is a dir, get all files in the dir and its subdirs
    files = [f for f in path.rglob("*") if f.is_file()]
    for f in files:
        shutil.move(f, path / f.name)

    # remove the subdirs
    for d in path.rglob("*"):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)


def find_root_dirs_with_audio_files(
    root: Path, mindepth: int | None = None, maxdepth: int | None = None
) -> list[Path]:
    """Given a root directory, returns a list of all root directories that contain audio files. E.g.,
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

    all_roots_with_audio_files = [
        d.relative_to(root)
        for d in root.rglob("*")
        if d.is_dir()
        and count_audio_files_in_dir(d, mindepth=0, maxdepth=1) > 0
        and (mindepth is None or depth(d) >= mindepth)
        and (maxdepth is None or depth(d) <= maxdepth)
    ]

    # get the root dirs and remove duplicates
    return list(sorted(set([root / d.parts[0] for d in all_roots_with_audio_files])))


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

    for ext in AUDIO_EXTS:
        audio_file = next(iter(sorted(path.rglob(f"*{ext}"))), None)
        if audio_file:
            return audio_file
    if throw:
        raise FileNotFoundError(f"No audio files found in {path}")
    return None


def find_next_audio_file(current_file: Path) -> Path | None:

    # if path is a file, get its parent dir or use the parent dir of the current file
    parent = current_file.parent if current_file.is_file() else current_file

    # if only one audio file, return None
    if count_audio_files_in_dir(parent) == 1:
        return None

    for ext in AUDIO_EXTS:
        audio_files = list(parent.rglob(ext))
        if audio_files:
            current_index = (
                audio_files.index(current_file) if current_file in audio_files else 0
            )
            if current_index < len(audio_files) - 1:
                return audio_files[current_index + 1]
    return None


def find_recently_modified_files_and_dirs(
    path: Path, minutes: float = 0.1
) -> list[str]:
    current_time = time.time()
    recent_items = []

    for item in Path(path).rglob("*"):
        if current_time - item.stat().st_mtime < minutes * 60:
            recent_items.append(str(item))

    return recent_items


def was_recently_modified(path: Path, minutes: float = 0.1) -> bool:
    from src.lib.config import cfg

    if cfg.TEST:
        return False
    current_time = time.time()
    return current_time - path.stat().st_mtime < minutes * 60


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


def dir_is_empty(path: Path) -> bool:
    return not any(path.iterdir())


import_debug.bug.pop("src/lib/fs_utils.py")