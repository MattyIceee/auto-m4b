from functools import cached_property
from math import floor
from pathlib import Path
from typing import cast, Literal, overload

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
    find_book_dirs_for_series,
    find_cover_art_file,
    find_first_audio_file,
    find_next_audio_file,
    get_size,
    hash_path_audio_files,
    last_updated_at,
)
from src.lib.id3_utils import extract_metadata
from src.lib.misc import get_dir_name_from_path
from src.lib.parsers import count_distinct_roman_numerals, extract_path_info
from src.lib.typing import AudiobookFmt, DirName, SizeFmt


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


    def __str__(self):
        return f"{self.key}"

    def __repr__(self):
        return f"{self.key}"

    def extract_path_info(self, quiet: bool = False):
        return extract_path_info(self, quiet)

    def extract_metadata(self, quiet: bool = False):
        return extract_metadata(self, quiet)

    @property
    def inbox_dir(self):
        return self.path

    @property
    def backup_dir(self) -> Path:
        return cfg.backup_dir.resolve() / self.basename

    @property
    def build_dir(self) -> Path:
        return cfg.build_dir.resolve() / self.basename

    @property
    def build_tmp_dir(self) -> Path:
        return self.build_dir.resolve() / f"{self.basename}-tmpfiles"

    @property
    def converted_dir(self) -> Path:
        return cfg.converted_dir.resolve() / self.key

    @property
    def archive_dir(self) -> Path:
        return cfg.archive_dir.resolve() / self.basename

    @property
    def merge_dir(self) -> Path:
        return cfg.merge_dir.resolve() / self.basename

    @property
    def build_file(self) -> Path:
        return self.build_dir.resolve() / f"{self.basename}.m4b"

    @property
    def converted_file(self) -> Path:
        return self.converted_dir / f"{self.basename}.m4b"

    @cached_property
    def sample_audio1(self):
        return find_first_audio_file(self.path)

    @cached_property
    def sample_audio2(self):
        return find_next_audio_file(self.sample_audio1)

    def last_updated_at(self, for_dir: DirName = "inbox"):
        return last_updated_at(getattr(self, for_dir + "_dir"), only_file_exts=cfg.AUDIO_EXTS)

    def hash(self, for_dir: DirName = "inbox"):
        return hash_path_audio_files(getattr(self, for_dir + "_dir"))

    @property
    def structure(self):
        return find_book_audio_files(self)[0]

    @property
    def is_series(self):
        return self.structure == "multi_book_series"

    @property
    def series_basename(self):
        d = self.path.relative_to(cfg.inbox_dir)
        return d.parent if len(d.parts) > 1 and d.parts[-1] == self.basename else d

    @cached_property
    def num_books_in_series(self):
        return len(find_book_dirs_for_series(self.inbox_dir))

    @cached_property
    def orig_file_type(self):
        return cast(AudiobookFmt, self.sample_audio1.suffix.replace(".", ""))

    def num_files(self, for_dir: DirName):
        return count_audio_files_in_dir(getattr(self, for_dir + "_dir"))

    @property
    def num_roman_numerals(self):
        return count_distinct_roman_numerals(self.inbox_dir)

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
        log_file = self.active_dir / self.log_filename
        log_file.touch(exist_ok=True)
        return log_file

    def write_log(self, *s: str):
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
        return getattr(self, f"{self._active_dir or "inbox"}_dir")

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
    def _src_cover_art(self):
        return find_cover_art_file(self.path)

    @property
    def cover_art(self):
        if not self._src_cover_art:
            return None
        merge_cover = self.merge_dir / self._src_cover_art.relative_to(self.inbox_dir)
        if not merge_cover.exists():
            cp_file_to_dir(self._src_cover_art, self.merge_dir)
        return merge_cover

    @property
    def basename(self):
        """The name of the book, including file extension if it is a single file, 
        e.g 'The Book.mp3' or 'The Book' if it is a directory. Equivalent to `<book>.path.name`."""
        return self.path.name

    @property
    def key(self):
        return str(self.path.relative_to(cfg.inbox_dir))

    @property
    def merge_desc_file(self):
        return self.merge_dir / "description.txt"

    @property
    def final_desc_file(self):
        quality = f"{self.bitrate_friendly} @ {self.samplerate_friendly}".replace(
            "kb/s", "kbps"
        )
        return self.converted_dir / f"{self} [{quality}].txt"

    def write_description_txt(self, out_path: Path | None = None):

        # Write the description to the file with newlines, ensure utf-8 encoding
        content = f"""Book title: {self.title}
Author: {self.author}
Date: {self.date}
Narrator: {self.narrator}
Quality: {self.bitrate_friendly} @ {self.samplerate_friendly}
Original folder name: {self.basename}
Original file type: {self.orig_file_type}
Original size: {self.size("inbox", "human")}
Original duration: {self.duration("inbox", "human")}
"""
        if self.converted_file.exists():
            content += f"Converted size: {self.size('converted', 'human')}\n"
            content += f"Converted duration: {self.duration('converted', 'human')}\n"
        elif self.build_file.exists():
            content += f"Converted size: {self.size('build', 'human')}\n"
            content += f"Converted duration: {self.duration('build', 'human')}\n"

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

