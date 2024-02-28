import import_debug

import_debug.bug.push("src/lib/ffmpeg_utils.py")
import subprocess
from pathlib import Path
from typing import Any, Literal, overload

import ffmpeg

from src.lib.config import AUDIO_EXTS
from src.lib.formatters import round_bitrate

DurationFmt = Literal["seconds", "human"]


def get_file_duration(file_path: Path) -> float:
    x = f"ffprobe -hide_banner -loglevel 0 -of flat -i {file_path} -show_entries format=duration -of default=noprint_wrappers=1:nokey=1"
    return float(subprocess.check_output(x, shell=True).decode().strip())


def get_file_duration_py(file_path: Path) -> float:
    return float(ffmpeg.probe(str(file_path))["format"]["duration"])


def format_duration(duration: float, fmt: DurationFmt) -> str | float:
    if fmt == "human":
        duration_int = round(duration)
        return f"{duration_int // 3600}h:{(duration_int % 3600) // 60}m:{duration_int % 60}s"
    return duration


@overload
def get_duration(path: Path, fmt: Literal["seconds"] = "seconds") -> float: ...


@overload
def get_duration(path: Path, fmt: Literal["human"] = "human") -> str: ...


def get_duration(path: Path, fmt: DurationFmt = "human") -> str | float:
    if not path.exists():
        raise ValueError(f"Error getting duration: Path {path} does not exist")

    if path.is_file():
        if path.suffix not in AUDIO_EXTS:
            raise ValueError(f"File {path} is not an audio file")

        duration = get_file_duration_py(path)

    elif path.is_dir():
        files = list(path.glob("**/*"))
        audio_files = [file for file in files if file.suffix in AUDIO_EXTS]
        if not audio_files:
            raise ValueError(f"No audio files found in {path}")

        duration = 0
        for file in audio_files:
            duration += get_file_duration_py(file)

    return format_duration(duration, fmt)


# def extract_id3_tag(file: Path, tag: str) -> str:
#     command = f"ffprobe -hide_banner -loglevel 0 -of flat -i {file} -select_streams a -show_entries format_tags={tag} -of default=noprint_wrappers=1:nokey=1"
#     result = subprocess.check_output(command, shell=True).decode().strip()
#     return result


# def get_bitrate(file: Path, round: bool = True) -> int:
#     command = f"ffprobe -hide_banner -loglevel 0 -select_streams a:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 {file}"
#     bitrate = subprocess.check_output(command, shell=True).decode().strip()
#     return round_bitrate(int(bitrate)) if round else int(bitrate)


def get_bitrate_py(file: Path, round: bool = True) -> int:
    probe_result = ffmpeg.probe(str(file))
    bitrate = probe_result["streams"][0]["bit_rate"]
    return round_bitrate(int(bitrate)) if round else int(bitrate)


# def get_samplerate(file: Path) -> int:
#     command = f"ffprobe -hide_banner -loglevel 0 -of flat -i {file} -select_streams a -show_entries stream=sample_rate -of default=noprint_wrappers=1:nokey=1"
#     sample_rate = subprocess.check_output(command, shell=True).decode().strip()
#     return int(sample_rate)


def get_samplerate_py(file: Path) -> int:
    probe_result = ffmpeg.probe(str(file))
    sample_rate = probe_result["streams"][0]["sample_rate"]
    return int(sample_rate)


def build_id3_tags_args(
    title: str = "", author: str = "", year: str | None = "", comment: str = ""
) -> list[tuple[str, Any]]:

    # build m4b-tool command switches based on which properties are defined
    # --name[=NAME]                              $title
    # --sortname[=SORTNAME]                      $title
    # --album[=ALBUM]                            $title
    # --sortalbum[=SORTALBUM]                    $title
    # --artist[=ARTIST]                          $author
    # --sortartist[=SORTARTIST]                  $author
    # --genre[=GENRE]                            always Audiobook
    # --writer[=WRITER]                          $author
    # --albumartist[=ALBUMARTIST]                $author
    # --year[=YEAR]                              $year
    # --description[=DESCRIPTION]                $description
    # --comment[=COMMENT]                        $comment
    # --encoded-by[=ENCODED-BY]                  always PHNTM

    id3tags = {}

    if title:
        id3tags.update(
            {
                "name": title,
                "sortname": title,
                "album": title,
                "sortalbum": title,
            }
        )

    if author:
        id3tags.update(
            {
                "artist": author,
                "sortartist": author,
                "writer": author,
                "albumartist": author,
            }
        )

    if year:
        id3tags["year"] = year

    if comment:
        id3tags["comment"] = comment

    id3tags.update({"encoded-by": "PHNTM", "genre": "Audiobook"})

    return [(f"--{k}", v) for k, v in id3tags.items()]


import_debug.bug.pop("src/lib/fs_utils.py")
