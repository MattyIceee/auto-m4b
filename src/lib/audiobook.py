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
    find_cover_art_file,
    find_first_audio_file,
    find_next_audio_file,
    get_size,
)
from src.lib.id3_utils import extract_metadata
from src.lib.misc import get_dir_name_from_path
from src.lib.parsers import extract_path_info
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
        return f"{self.basename}"

    def __repr__(self):
        return f"{self.basename}"

    def extract_path_info(self, quiet: bool = False):
        return extract_path_info(self, quiet)

    def extract_metadata(self, quiet: bool = False):
        return extract_metadata(self, quiet)

    @property
    def inbox_dir(self):
        return self.path
        # return cfg.inbox_dir.resolve() / self.dir_name

    @property
    def fix_dir(self) -> Path:
        d = cfg.inbox_dir.resolve() if cfg.NO_FIX else cfg.fix_dir.resolve()
        return d / self.basename

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
        return cfg.converted_dir.resolve() / self.basename

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

    @cached_property
    def orig_file_type(self):
        return cast(AudiobookFmt, self.sample_audio1.suffix.replace(".", ""))

    def num_files(self, for_dir: DirName):
        return count_audio_files_in_dir(getattr(self, for_dir + "_dir"))

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
    def log_file(self) -> Path:
        log_file = self.active_dir / f"m4b-tool.{self}.log"
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
    def cover_art(self):
        return find_cover_art_file(self.path)

    @property
    def basename(self):
        """The name of the book, including file extension if it is a single file"""
        return self.path.name

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

