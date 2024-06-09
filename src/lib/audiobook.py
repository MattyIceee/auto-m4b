from functools import cached_property
from math import floor
from pathlib import Path
from typing import cast, Literal, overload

import cachetools
import cachetools.func
from pydantic import BaseModel

from src.lib.config import cfg
from src.lib.ffmpeg_utils import (
    DurationFmt,
    get_bitrate_py,
    get_duration,
    get_samplerate_py,
)
from src.lib.formatters import human_bitrate
from src.lib.fs_utils import (
    count_audio_files_in_dir,
    cp_file_to_dir,
    find_book_audio_files,
    find_cover_art_file,
    find_first_audio_file,
    find_next_audio_file,
    get_size,
    hash_path_audio_files,
    last_updated_at,
)
from src.lib.id3_utils import extract_cover_art, extract_metadata
from src.lib.misc import get_dir_name_from_path
from src.lib.parsers import count_distinct_romans, extract_path_info
from src.lib.typing import AudiobookFmt, BookStructure, DirName, SizeFmt


class Audiobook(BaseModel):
    path: Path
    id3_title: str = ""
    id3_artist: str = ""
    id3_albumartist: str = ""
    id3_album: str = ""
    id3_sortalbum: str = ""
    id3_date: str = ""
    id3_year: str = ""
    id3_comment: str = ""
    id3_composer: str = ""
    has_id3_cover: bool = False
    fs_author: str = ""
    fs_title: str = ""
    fs_year: str = ""
    fs_narrator: str = ""
    dir_extra_junk: str = ""
    file_extra_junk: str = ""
    orig_file_type: AudiobookFmt = ""  # type: ignore
    orig_file_name: str = ""
    title: str = ""
    artist: str = ""
    albumartist: str = ""
    album: str = ""
    sortalbum: str = ""
    date: str = ""
    year: str | None = None
    comment: str = ""
    composer: str = ""
    narrator: str = ""
    title_is_partno: bool = False
    track_num: tuple[int, int] = (1, 1)
    m4b_num_parts: int = 1
    _active_dir: DirName | None = None

    def __init__(self, path: Path):

        if not path.is_absolute():
            path = cfg.inbox_dir.resolve() / path

        super().__init__(path=path)

        self.path = path
        self._active_dir = get_dir_name_from_path(path)
        if f := find_first_audio_file(self.path, ignore_errors=True):
            self.orig_file_type = cast(AudiobookFmt, f.suffix.replace(".", ""))

    def __str__(self):
        return f"{self.key}"

    def __repr__(self):
        return f"{self.key}"

    def extract_path_info(self, quiet: bool = False):
        return extract_path_info(self, quiet)

    def extract_metadata(self, quiet: bool = False):
        return extract_metadata(self, quiet)

    def extract_cover_art(self):
        if self.cover_art_file:
            return self.cover_art_file
        try:
            extract_cover_art(self.sample_audio1, save_to_file=True)
            self._inbox_cover_art_file = cast(Path, find_cover_art_file(self.path))
            cp_file_to_dir(self._inbox_cover_art_file, self.merge_dir)
            return self.cover_art_file
        except Exception:
            # no cover art found, probably
            return None

    @property
    def inbox_dir(self):
        return self.path

    @property
    def backup_dir(self) -> Path:
        return cfg.backup_dir.resolve() / self.key

    @property
    def build_dir(self) -> Path:
        return (cfg.build_dir.resolve() / self.key).with_suffix("") if cfg.PLEX_FORMAT else (cfg.build_dir.resolve() / self.basename).with_suffix("")

    @property
    def build_tmp_dir(self) -> Path:
        return self.build_dir / f"{self.basename}-tmpfiles"

    @property
    def converted_dir(self) -> Path:
        if cfg.PLEX_FORMAT:
            return (cfg.converted_dir.resolve() / self.key).with_suffix("")
        return (cfg.converted_dir.resolve() / self.basename).with_suffix("")

    @property
    def archive_dir(self) -> Path:
        return cfg.archive_dir.resolve() / self.key

    @property
    def merge_dir(self) -> Path:
        return cfg.merge_dir.resolve() / self.basename

    @property
    def build_file(self) -> Path:
        if self.build_dir.suffix == ".m4b":
            return self.build_dir
        if cfg.PLEX_FORMAT:
                return self.build_dir / f"{self.title}.m4b"
        try:
            return find_first_audio_file(self.build_dir, ".m4b")
        except FileNotFoundError:
            return self.build_dir / f"{self.basename}.m4b"

    @property
    def converted_file(self) -> Path:
        if self.converted_dir.suffix == ".m4b":
            return self.converted_dir
        if cfg.PLEX_FORMAT:
                return self.converted_dir / f"{self.title}.m4b"
        try:
            return find_first_audio_file(self.converted_dir, ".m4b")
        except FileNotFoundError:
            return self.converted_dir / f"{self.basename}.m4b"

    @cached_property
    def sample_audio1(self):
        return find_first_audio_file(self.path)

    @cached_property
    def sample_audio2(self):
        return find_next_audio_file(self.sample_audio1)

    def rescan_structure(self):
        for attr in ["sample_audio1", "sample_audio2", "structure"]:
            try:
                delattr(self, attr)
            except AttributeError:
                pass
            getattr(self, attr)

    def last_updated_at(self, for_dir: DirName = "inbox"):
        return last_updated_at(
            getattr(self, for_dir + "_dir"), only_file_exts=cfg.AUDIO_EXTS
        )

    def hash(self, for_dir: DirName = "inbox"):
        return hash_path_audio_files(getattr(self, for_dir + "_dir"))

    @cached_property
    def structure(self) -> BookStructure:
        return find_book_audio_files(self)[0]

    def is_a(
        self,
        structure: BookStructure | tuple[BookStructure, ...],
        fmt: AudiobookFmt | None = None,
        *,
        not_fmt: AudiobookFmt | tuple[AudiobookFmt | None, ...] | None = None,
    ):
        if not isinstance(structure, tuple):
            structure = (structure,)
        if not isinstance(not_fmt, tuple):
            not_fmt = (not_fmt,)
        not_fmt_matches = not not_fmt or self.orig_file_type not in not_fmt
        fmt_matches = not fmt or self.orig_file_type == fmt
        return self.structure in structure and fmt_matches and not_fmt_matches

    @property
    def is_maybe_series_book(self):
        # return self.structure == "multi_book_series"
        return self._inbox_item.is_maybe_series_book if self._inbox_item else False

    @property
    def is_maybe_series_parent(self):
        return self._inbox_item.is_maybe_series_parent if self._inbox_item else False

    @property
    def is_first_book_in_series(self):
        return self._inbox_item.is_first_book_in_series if self._inbox_item else False

    @property
    def is_last_book_in_series(self):
        return self._inbox_item.is_last_book_in_series if self._inbox_item else False

    @property
    def series_parent(self):
        return self._inbox_item.series_parent if self._inbox_item else None

    @property
    def series_books(self):
        return self._inbox_item.series_books if self._inbox_item else None

    @property
    def series_basename(self):
        return self._inbox_item.series_basename if self._inbox_item else None

    @cachetools.func.ttl_cache(maxsize=6, ttl=20)
    @property
    def num_books_in_series(self):
        return self._inbox_item.num_books_in_series if self._inbox_item else -1

    def num_files(self, for_dir: DirName):
        return count_audio_files_in_dir(getattr(self, for_dir + "_dir"))

    @property
    def num_roman_numerals(self):
        return count_distinct_romans(self.inbox_dir)

    @overload
    def size(self, for_dir: DirName, fmt: Literal["bytes"]) -> int: ...

    @overload
    def size(self, for_dir: DirName, fmt: Literal["human"]) -> str: ...

    def size(self, for_dir: DirName, fmt: SizeFmt = "bytes"):
        return get_size(getattr(self, for_dir + "_dir"), fmt=fmt)

    @overload
    def duration(self, for_dir: DirName, fmt: Literal["seconds"]) -> float: ...

    @overload
    def duration(self, for_dir: DirName, fmt: Literal["human"]) -> str: ...

    def duration(self, for_dir: DirName, fmt: DurationFmt = "seconds"):
        return get_duration(getattr(self, for_dir + "_dir"), fmt=fmt)

    @property
    def bitrate_actual(self):
        return get_bitrate_py(self.sample_audio1)[1]

    @property
    def bitrate_target(self):
        return get_bitrate_py(self.sample_audio1)[0]

    @property
    def samplerate(self):
        return get_samplerate_py(self.sample_audio1)

    @property
    def log_filename(self):
        return f"auto-m4b.{self.basename}.log"

    @property
    def log_file(self) -> Path:
        return (
            self.active_dir.parent if self.active_dir.is_file() else self.active_dir
        ) / self.log_filename

    def write_log(self, *s: str):
        self.log_file.touch(exist_ok=True)
        with open(self.log_file, "a+") as f:
            # if file is not empty, and last line is not empty, add a newline
            if f.tell() and (existing := f.readlines()) and existing[-1].strip():
                f.write("\n")
            line = " ".join(s)
            # ensure newline at end of file
            if not line.endswith("\n"):
                line += "\n"
            f.write(line)

    def set_active_dir(self, new_dir: DirName):
        self._active_dir = new_dir

    @property
    def active_dir(self) -> Path:
        return getattr(self, f"{self._active_dir or 'inbox'}_dir")

    @property
    def author(self):
        return self.artist or self.albumartist or self.composer

    @property
    def bitrate_friendly(self):
        return human_bitrate(self.sample_audio1)

    @property
    def samplerate_friendly(self):  # round to nearest .1 kHz
        khz = self.samplerate / 1000
        if round(khz % 1, 2) <= 0.05:
            # if sample rate is .05 or less from a 0, round down to the nearest 0
            return f"{int(floor(khz))} kHz"
        return f"{round(khz, 1)} kHz"

    @cached_property
    def _inbox_cover_art_file(self):
        return find_cover_art_file(self.path)

    @property
    def cover_art_file(self):
        if not self._inbox_cover_art_file:
            return None
        merge_cover = self.merge_dir / self._inbox_cover_art_file.relative_to(
            self.inbox_dir
        )
        if not merge_cover.exists():
            cp_file_to_dir(self._inbox_cover_art_file, self.merge_dir)
        return merge_cover

    @cached_property
    def id3_cover(self):
        return extract_cover_art(self.sample_audio1, save_to_file=False)

    @property
    def basename(self):
        """The name of the book, including file extension if it is a single file,
        e.g 'The Book.mp3' or 'The Book' if it is a directory. Equivalent to `<book>.path.name`.
        """
        return self.path.name

    @property
    def key(self):
        return str(self.path.relative_to(cfg.inbox_dir))

    @property
    def _inbox_item(self):
        from src.lib.inbox_state import InboxState

        return InboxState().get(self.key)

    @property
    def merge_desc_file(self):
        return self.merge_dir / "description.txt"

    @property
    def final_desc_file(self):
        quality = f"{self.bitrate_friendly} @ {self.samplerate_friendly}".replace(
            "kb/s", "kbps"
        )
        return self.converted_dir / f"{self.basename} [{quality}].txt"

    def write_description_txt(self, out_path: Path | None = None):

        # Write the description to the file with newlines, ensure utf-8 encoding

        m4b_file = next(
            (f for f in [self.converted_file, self.build_file] if f.exists()),
            None,
        )
        converted_duration = get_duration(m4b_file, "human") if m4b_file else "N/A"
        converted_size = get_size(m4b_file, "human") if m4b_file else "N/A"
        orig_basename = (
            f"{'File' if self.path.is_file() else 'Folder'} name: {self.basename}"
        )

        content = f"""Book title: {self.title}
Author: {self.author}
Date: {self.date}
Narrator: {self.narrator}
Format: m4b
Quality: {self.bitrate_friendly} @ {self.samplerate_friendly}
Duration: {converted_duration}
Size: {converted_size}

(Original)
{orig_basename}
Format: {self.orig_file_type or 'N/A'}
Size: {self.size("inbox", "human")}
"""
        out_path = out_path or self.merge_desc_file
        # write the description to the file, overwriting if it already exists
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)

        # check to make sure the file was created
        if not out_path.exists():
            raise ValueError(f"Failed to create {out_path}")

    def metadata(self):
        """Prints all known metadata for the book"""

        for k, v in self.model_dump().items():
            if k.startswith("_") or v is None or v == "":
                continue
            print(f"- {k}: {v}")
