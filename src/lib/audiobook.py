import import_debug

import_debug.bug.push("src/lib/audiobook.py")
from functools import cached_property
from pathlib import Path
from typing import cast, Literal, overload

from pydantic import BaseModel

from src.lib.config import cfg
from src.lib.ffmpeg_utils import DurationFmt, get_duration
from src.lib.fs_utils import (
    count_audio_files_in_dir,
    find_first_audio_file,
    find_next_audio_file,
    get_size,
)
from src.lib.parsers import extract_metadata, extract_path_info
from src.lib.typing import AudiobookFmt, DirName, SizeFmt


class Audiobook(BaseModel):
    path: Path
    bitrate: int = 0
    samplerate: int = 0
    id3_title: str = ""
    id3_artist: str = ""
    id3_albumartist: str = ""
    id3_album: str = ""
    id3_sortalbum: str = ""
    id3_date: str = ""
    id3_year: str = ""
    id3_comment: str = ""
    id3_composer: str = ""
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

    def __init__(self, path: Path):

        if not path.is_absolute():
            path = cfg.inbox_dir / path

        super().__init__(path=path)

        self.path = path

    def __str__(self):
        return f"{self.dir_name}"

    def __repr__(self):
        return f"{self.dir_name}"

    def extract_path_info(self):
        extract_path_info(self)

    def extract_metadata(self):
        extract_metadata(self)

    @property
    def inbox_dir(self):
        return cfg.inbox_dir.resolve() / self.dir_name

    @property
    def fix_dir(self) -> Path:
        return cfg.fix_dir.resolve() / self.dir_name

    @property
    def backup_dir(self) -> Path:
        return cfg.backup_dir.resolve() / self.dir_name

    @property
    def build_dir(self) -> Path:
        return cfg.build_dir.resolve() / self.dir_name

    @property
    def build_tmp_dir(self) -> Path:
        return self.build_dir.resolve() / f"{self.dir_name}-tmpfiles"

    @property
    def converted_dir(self) -> Path:
        return cfg.converted_dir.resolve() / self.dir_name

    @property
    def archive_dir(self) -> Path:
        return cfg.archive_dir.resolve() / self.dir_name

    @property
    def merge_dir(self) -> Path:
        return cfg.merge_dir.resolve() / self.dir_name

    @property
    def build_file(self) -> Path:
        return self.build_dir.resolve() / f"{self.dir_name}.m4b"

    @property
    def converted_file(self) -> Path:
        return self.converted_dir / f"{self.dir_name}.m4b"

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

    @cached_property
    def sample_audio1(self):
        return find_first_audio_file(self.inbox_dir)

    @cached_property
    def sample_audio2(self):
        return find_next_audio_file(self.sample_audio1)

    @property
    def log_file(self) -> Path:
        return self.build_dir / f"{self.dir_name}.log"

    @property
    def author(self):
        return self.artist or self.albumartist or self.composer

    @property
    def bitrate_friendly(self):
        return f"{round(self.bitrate / 1000)} kb/s"

    @property
    def samplerate_friendly(self):
        return f"{round(self.samplerate / 1000)} kHz"

    @property
    def dir_name(self):
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
Original folder name: {self.dir_name}
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


import_debug.bug.pop("src/lib/audiobook.py")
