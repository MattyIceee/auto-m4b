import datetime
import functools
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast, Literal, overload, TYPE_CHECKING

import bidict
import ffmpeg
from columnar import columnar
from eyed3 import AudioFile, core
from eyed3.core import Date
from eyed3.id3 import ID3_V2_3, ID3_V2_4, Tag
from rapidfuzz import fuzz
from tinta import Tinta

from src.lib.cleaners import clean_string, strip_leading_articles
from src.lib.misc import compare_trim, fix_ffprobe, get_numbers_in_string

fix_ffprobe()

from src.lib.cleaners import strip_part_number
from src.lib.parsers import (
    common_str_pattern,
    contains_partno,
    find_greatest_common_string,
    get_title_partno_score,
    get_year_from_date,
    has_graphic_audio,
    parse_author,
    parse_narrator,
    parse_year,
    startswith_num_pattern,
    to_words,
)
from src.lib.term import (
    nl,
    PATH_COLOR,
    print_debug,
    print_error,
    print_list_item,
    smart_print,
)
from src.lib.typing import AdditionalTags, BadFileError, ScoredProp, TagSource

MissingApplicationError = ValueError

if TYPE_CHECKING:
    from src.lib.audiobook import Audiobook


def write_id3_tags_exiftool(file: Path, exiftool_args: list[str]) -> None:
    api_opts = ["-api", 'filter="s/ \\(approx\\)//"']  # remove (approx) from output

    # if file doesn't exist, throw error
    if not file.is_file():
        raise RuntimeError(f"Error: Cannot write id3 tags, {file} does not exist")

    # make sure the exiftool command exists
    if not shutil.which("exiftool"):
        raise RuntimeError(
            "exiftool is not available, please install it with\n\n $ apt-get install exiftool\n\n...or make sure it is in your PATH variable, then try again"
        )

    # write tag to file, using eval so that quotes are not escaped
    subprocess.run(
        ["exiftool", "-overwrite_original"] + exiftool_args + api_opts + [str(file)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# Patch eyed3 to support recording date, per https://github.com/nicfit/eyeD3/issues/517
def _setRecordingDate(tag: Tag, date: str | core.Date | None) -> None:
    if date in (None, ""):
        for fid in (b"TDRC", b"TYER", b"TDAT", b"TIME"):
            tag._setDate(fid, None)
    elif tag.version == ID3_V2_4 or tag.version == ID3_V2_3:
        try:
            tag._setDate(b"TDRC", date)
        except ValueError:
            pass
    else:
        if not isinstance(date, core.Date):
            parsed_date = core.Date.parse(date)
        else:
            parsed_date = date

        year = parsed_date.year
        month = parsed_date.month
        day = parsed_date.day

        if year is not None:
            tag._setDate(b"TYER", str(year))
        if None not in (month, day):
            date_str = "%s%s" % (str(day).rjust(2, "0"), str(month).rjust(2, "0"))
            tag._setDate(b"TDAT", date_str)


def write_id3_tags_eyed3(file: Path, book: "Audiobook | dict[str, Any]") -> None:
    # uses native python library eyed3 to write id3 tags to file
    try:
        import eyed3
    except ImportError:
        raise MissingApplicationError(
            "Error: eyed3 is not available, please install it with\n\n $ pip install eyed3\n\n...then try again"
        )

    if not file.exists():
        raise FileNotFoundError(
            f"Error: Cannot write id3 tags, '{file}' does not exist"
        )

    if isinstance(book, dict):
        title = str(book.get("title", ""))
        artist = str(book.get("artist", ""))
        album = str(book.get("album", ""))
        albumartist = str(book.get("albumartist", ""))
        composer = str(book.get("composer", ""))
        date = str(book.get("date", ""))
        track_num = book.get("track_num", (1, 1))
        comment = str(book.get("comment", ""))
    else:
        title = book.title
        artist = book.artist
        album = book.album
        albumartist = book.albumartist
        composer = book.composer
        date = book.date
        track_num = book.track_num
        comment = book.comment

    audiofile: AudioFile
    if audiofile := eyed3.load(file):  # type: ignore
        audiofile.tag = cast(Tag, audiofile.tag)
        if not audiofile.tag:
            audiofile.initTag()
        audiofile.tag.title = title
        audiofile.tag.artist = artist
        audiofile.tag.album = album
        audiofile.tag.album_artist = albumartist
        audiofile.tag.composer = composer
        audiofile.tag.comments.set(comment)  # type: ignore

        # if track_num is not None and not a tuple of (int, int), throw error
        if (
            not isinstance(track_num, tuple)
            or len(track_num) != 2
            or not all(isinstance(i, int) for i in track_num)
        ):
            raise ValueError(
                f"Error: track_num must be a tuple of (int, int), not {track_num}"
            )
        audiofile.tag.track_num = track_num

        year = get_year_from_date(date)
        try:
            d = datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            d = None
        year = year or d.year if d else None
        if year or d:
            date_obj = Date(d.year, d.month, d.day) if d else Date(year)
            _setRecordingDate(audiofile.tag, date_obj)
            audiofile.tag.recording_date = date_obj
            audiofile.tag.release_date = date_obj
            audiofile.tag.original_release_date = date_obj
            assert audiofile.tag.getBestDate() == date_obj

        audiofile.tag.save()
    else:
        raise BadFileError(
            f"Error: Could not load '{file}' for tagging, it may be corrupt or not an audio file"
        )


def verify_and_update_id3_tags(
    book: "Audiobook", in_dir: Literal["build", "converted"]
) -> None:
    # takes the inbound book, then checks the converted file and verifies that the id3 tags match the extracted metadata
    # if they do not match, it will print a notice and update the id3 tags

    from src.lib.audiobook import Audiobook
    from src.lib.config import cfg

    m4b_to_check = book.converted_file if in_dir == "converted" else book.build_file

    if not m4b_to_check.is_file():
        raise FileNotFoundError(
            f"Cannot verify id3 tags, {m4b_to_check} does not exist"
        )

    smart_print("\nVerifying id3 tags...", end="")

    book_to_check = Audiobook(m4b_to_check).extract_metadata(quiet=True)

    exiftool_args = []

    title_needs_updating = False
    author_needs_updating = False
    date_needs_updating = False
    comment_needs_updating = False

    updates = []

    def _print_needs_updating(
        what: str, left_value: str | None, right_value: str
    ) -> None:
        s = Tinta().dark_grey(f"- ").grey(what).dark_grey("needs updating:")
        if left_value:
            s.amber(left_value)
        else:
            s.light_grey("Missing")
        s.dark_grey("»").mint(right_value)
        smart_print(s.to_str())

    if book.title and book_to_check.id3_title != book.title:
        title_needs_updating = True
        updates.append(
            lambda: _print_needs_updating("Title", book_to_check.id3_title, book.title)
        )

    if book.author and book_to_check.id3_artist != book.author:
        author_needs_updating = True
        updates.append(
            lambda: _print_needs_updating(
                "Artist (author)", book_to_check.id3_artist, book.author
            )
        )

    if book.title and book_to_check.id3_album != book.title:
        title_needs_updating = True
        updates.append(
            lambda: _print_needs_updating(
                "Album (title)", book_to_check.id3_album, book.title
            )
        )

    if book.title and book_to_check.id3_sortalbum != book.title:
        title_needs_updating = True
        updates.append(
            lambda: _print_needs_updating(
                "Sort album (title)", book_to_check.id3_sortalbum, book.title
            )
        )

    if book.author and book_to_check.id3_albumartist != book.author:
        author_needs_updating = True
        updates.append(
            lambda: _print_needs_updating(
                "Album artist (author)", book_to_check.id3_albumartist, book.author
            )
        )

    if book.date and get_year_from_date(book_to_check.id3_date) != get_year_from_date(
        book.date
    ):
        date_needs_updating = True
        updates.append(
            lambda: _print_needs_updating("Date", book_to_check.id3_date, book.date)
        )

    if book.comment and compare_trim(book_to_check.id3_comment, book.comment):
        comment_needs_updating = True
        updates.append(
            lambda: _print_needs_updating(
                "Comment", book_to_check.id3_comment, book.comment
            )
        )

    if cfg.EXIF_WRITER == "exiftool":
        # for each of the id3 tags that need updating, write the id3 tags
        if title_needs_updating:
            exiftool_args.extend(
                [
                    "-Title=" + book.title,
                    "-Album=" + book.title,
                    "-SortAlbum=" + book.title,
                ]
            )

        if author_needs_updating:
            exiftool_args.extend(
                ["-Artist=" + book.author, "-SortArtist=" + book.author]
            )

        if date_needs_updating:
            exiftool_args.append("-Date=" + book.date)

        if comment_needs_updating:
            exiftool_args.append("-Comment=" + book.comment)

        # set track_number and other statics
        exiftool_args.extend(
            [
                "-TrackNumber=1/" + str(book.m4b_num_parts),
                "-EncodedBy=auto-m4b",
                "-Genre=Audiobook",
                "-Copyright=",
            ]
        )

        # write with exiftool
        if exiftool_args:
            write_id3_tags_exiftool(m4b_to_check, exiftool_args)

    elif cfg.EXIF_WRITER == "eyed3":
        if (
            title_needs_updating
            or author_needs_updating
            or date_needs_updating
            or comment_needs_updating
        ):
            write_id3_tags_eyed3(m4b_to_check, book)

    if not any(
        [
            title_needs_updating,
            author_needs_updating,
            date_needs_updating,
            comment_needs_updating,
        ]
    ):
        sys.stdout.write(Tinta().mint(" ✓\n").to_str())
        smart_print()

    else:
        [update() for update in updates]
        smart_print(Tinta("Done").mint("✓").to_str())

    nl()


def ffprobe_file(file: Path, *, options: dict[str, Any] = {}, throw: bool = False):
    from src.lib.config import cfg

    if file is None:
        return None

    if file and not file.exists():
        raise FileNotFoundError(
            f"Error: Cannot extract id3 tag, '{file}' does not exist"
        )
    try:
        probe_result = ffmpeg.probe(str(file), cmd="ffprobe", **options)
    except ffmpeg.Error as e:
        from src.lib.logger import write_err_file

        write_err_file(file, e, "ffprobe")
        if throw:
            raise BadFileError(
                f"Error: Could run ffprobe on file '{file}' with options {options}"
            ) from e
        print_error(f"Error: Could run ffprobe on file '{file}' with options {options}")
        if cfg.DEBUG:
            print_debug(e.stderr)
        return None

    return cast(dict, probe_result)


def ffmpeg_file(file: Path, *, options: dict[str, Any] = {}, throw: bool = False):
    from src.lib.config import cfg

    if file is None:
        return None

    if file and not file.exists():
        raise FileNotFoundError(
            f"Error: Cannot extract id3 tag, '{file}' does not exist"
        )
    try:
        ffmpeg_result = ffmpeg.run(str(file), cmd="ffmpeg", **options)
    except ffmpeg.Error as e:
        from src.lib.logger import write_err_file

        write_err_file(file, e, "ffmpeg")
        if throw:
            raise BadFileError(
                f"Error: Could run ffmpeg on file '{file}' with options {options}"
            ) from e
        print_error(f"Error: Could run ffmpeg on file '{file}' with options {options}")
        if cfg.DEBUG:
            print_debug(e.stderr)
        return None

    return cast(dict, ffmpeg_result)


@overload
def extract_cover_art(file: Path, save_to_file: Literal[False] = False) -> bytes: ...


@overload
def extract_cover_art(
    file: Path, save_to_file: Literal[True], filename: str = "cover"
) -> Path: ...


def extract_cover_art(
    file: Path, save_to_file: bool = False, filename: str = "cover"
) -> bytes | Path:
    from src.lib.config import cfg

    out_file = file.parent / filename

    try:
        if ffresult := ffprobe_file(file):
            # '-s': '320x240'}):
            # find a stream that is jpg or png and has a disposition of attached_pic
            for stream in ffresult["streams"]:
                if stream.get("codec_name") in ["mjpeg", "png"] and stream.get(
                    "disposition", {}
                ).get("attached_pic"):
                    content_type = stream.get("codec_name")
                    common_steps = [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "0",
                        "-i",
                        str(file),
                        "-map",
                        f"0:{stream['index']}",
                        "-c",
                        "copy",
                    ]
                    if save_to_file:
                        ext = "png" if content_type == "png" else "jpg"
                        out_file = out_file.with_suffix(f".{ext}")
                        subprocess.check_output(
                            [
                                *common_steps,
                                out_file,
                            ]
                        )
                        return out_file
                    return subprocess.check_output(
                        [
                            *common_steps,
                            "-f",
                            "image2pipe",
                            "-vcodec",
                            "png" if content_type == "png" else "mjpeg",
                            "-",
                        ]
                    )
    except KeyError:
        if cfg.DEBUG:
            print_debug(f"Could not extract cover art from {file}'s streams")
    return out_file.with_suffix(".jpg") if save_to_file else b""


id3_tag_map = bidict.bidict(
    {
        "title": "title",
        "artist": "artist",
        "album_artist": "albumartist",
        "album": "album",
        "composer": "composer",
        "comment": "comment",
        "genre": "genre",
        "date": "date",
        "track": "track",
        "sort_name": "sortname",
        "sort_artist": "sortartist",
        "sort_album": "sortalbum",
        "description": "description",
        "encoder": "encoder",
    }
)


def id3_tags_raw_to_source(
    in_dict: dict[str, str],
) -> dict[TagSource | AdditionalTags, str]:
    """Takes raw id3 tag keys and converts them to the source tag names"""
    return {cast(TagSource, id3_tag_map.get(k, k)): v for k, v in in_dict.items()}


def id3_tags_source_to_raw(
    in_dict: dict[TagSource | AdditionalTags, str],
) -> dict[str, str]:
    """Takes raw id3 tag keys and converts them to the source tag names"""
    return {cast(TagSource, id3_tag_map.inv.get(k, k)): v for k, v in in_dict.items()}


def extract_id3_tags(
    file: Path | None, *tags: TagSource | AdditionalTags, throw=False
) -> dict[TagSource | AdditionalTags, str]:

    if isinstance(file, str):
        file = Path(file)
    if not file or not file.exists():
        if throw:
            raise BadFileError(
                f"Error: Cannot extract id3 tags, '{file}' does not exist"
            )
        return {}

    try:
        if ffresult := ffprobe_file(file, throw=throw):
            tag_dict = id3_tags_raw_to_source(
                {
                    key.lower(): value
                    for key, value in (ffresult["format"]["tags"] or {}).items()
                }
            )
            if not tags:
                return tag_dict
            return {tag: tag_dict.get(tag, "") for tag in tags}
    except Exception as e:
        if throw:
            raise BadFileError(
                f"Error: Could not extract id3 tags from {file} with tags {tags}"
            ) from e
        # if cfg.DEBUG:
        #     print_debug(
        #         f"Could not read '{tag}' from {file}'s id3 tags, it probably doesn't exist"
        #     )
    return {}


class BaseScoreCard:

    props: list[TagSource] = []

    def reset(self):
        for attr in dir(self):
            if not attr.startswith("_") and isinstance(getattr(self, attr), int):
                setattr(self, attr, 0)

    @property
    def _prop(self):
        return self.__class__.__name__.split("ScoreCard")[0].lower()

    @property
    def is_likely(self) -> tuple[TagSource, int, str | None]:
        # put all the scores in a list and return the highest score and its var name
        rep = re.compile(rf"_(is|contains)_{self._prop}$")
        scores = [
            (cast(TagSource, re.sub(rep, "", p)), getattr(self, p), p)
            for p in dir(self)
            if not p.startswith("_")
            and p.endswith(self._prop)
            and isinstance(getattr(self, p), int)
        ]
        if not scores or all(score[1] <= 0 for score in scores):
            return "unknown", 0, None
        tag, best, prop = max(scores, key=lambda x: x[1])
        # return the highest score and the name of its variable - use inflection or inspect
        return tag, best, prop

    def __repr__(self):
        return self.__str__()


class TitleScoreCard(BaseScoreCard):
    title_is_title: int = 0
    album_is_title: int = 0
    sortalbum_is_title: int = 0
    common_title_is_title: int = 0
    common_album_is_title: int = 0
    common_sortalbum_is_title: int = 0

    props: list[TagSource] = [
        "title",
        "album",
        "sortalbum",
        "common_title",
        "common_album",
        "common_sortalbum",
    ]

    def __str__(self):
        return (
            f"TitleScoreCard\n"
            f" - title_is_title: {self.title_is_title}\n"
            f" - album_is_title: {self.album_is_title}\n"
            f" - sortalbum_is_title: {self.sortalbum_is_title}\n"
            f" - common_title_is_title: {self.common_title_is_title}\n"
            f" - common_album_is_title: {self.common_album_is_title}\n"
            f" - common_sortalbum_is_title: {self.common_sortalbum_is_title}\n"
        )


class AuthorScoreCard(BaseScoreCard):
    artist_is_author: int = 0
    albumartist_is_author: int = 0
    common_artist_is_author: int = 0
    common_albumartist_is_author: int = 0
    comment_contains_author: int = 0

    props: list[TagSource] = [
        "artist",
        "albumartist",
        "common_artist",
        "common_albumartist",
        "comment",
    ]

    def __str__(self):
        return (
            f"AuthorScoreCard\n"
            f" - artist_is_author: {self.artist_is_author}\n"
            f" - albumartist_is_author: {self.albumartist_is_author}\n"
            f" - common_artist_is_author: {self.common_artist_is_author}\n"
            f" - common_albumartist_is_author: {self.common_albumartist_is_author}\n"
            f" - comment_contains_author: {self.comment_contains_author}\n"
        )


class NarratorScoreCard(BaseScoreCard):
    artist_is_narrator: int = 0
    albumartist_is_narrator: int = 0
    common_artist_is_narrator: int = 0
    common_albumartist_is_narrator: int = 0
    comment_contains_narrator: int = 0
    composer_is_narrator: int = 0

    props: list[TagSource] = [
        "artist",
        "albumartist",
        "common_artist",
        "common_albumartist",
        "comment",
        "composer",
    ]

    def __str__(self):
        return (
            f"NarratorScoreCard\n"
            f" - artist_is_narrator: {self.artist_is_narrator}\n"
            f" - albumartist_is_narrator: {self.albumartist_is_narrator}\n"
            f" - common_artist_is_narrator: {self.common_artist_is_narrator}\n"
            f" - common_albumartist_is_narrator: {self.common_albumartist_is_narrator}\n"
            f" - composer_is_narrator: {self.composer_is_narrator}\n"
            f" - comment_contains_narrator: {self.comment_contains_narrator}\n"
        )


class DateScoreCard(BaseScoreCard):
    date_is_date: int = 0
    fs_contains_date: int = 0

    props: list[TagSource] = ["date", "year", "fs"]

    def __str__(self):
        return (
            f"DateScoreCard\n"
            f" - date_is_date: {self.date_is_date}\n"
            f" - fs_contains_date: {self.fs_contains_date}\n"
        )


KEY_MAP = {
    "_aar": "albumartist",
    "_ar": "artist",
    "_al": "album",
    "_comment": "comment",
    "_sal": "sortalbum",
    "_t": "title",
    "_fs": "fs",
    # add more mappings here if needed
}


def custom_sort(key: str, next_key: str) -> int:
    underscored = key.startswith("_")
    next_underscored = next_key.startswith("_")
    # next_group = not next_key.startswith("_") and re.sub(r"(^[a-z])", "", next_key)
    mapped_key = (
        None
        if not underscored
        else next((KEY_MAP[i] for i in KEY_MAP if key.startswith(i)), None)
    )
    next_mapped_key = (
        None
        if not next_underscored
        else next((KEY_MAP[i] for i in KEY_MAP if next_key.startswith(i)), None)
    )

    # if neither have mapped keys, just compare them as is
    if not mapped_key and not next_mapped_key:
        return -1 if key < next_key else int(key > next_key)

    group = mapped_key if mapped_key else re.sub(r"([^a-z]*)$", "", key)
    next_group = (
        next_mapped_key if next_mapped_key else re.sub(r"([^a-z]*)$", "", next_key)
    )
    # next_group = not next_key.startswith("_") and re.sub(r"(^[a-z])", "", next_key)
    groups_match = group == next_group

    # groups don't match, so compare them
    if not groups_match:
        return -1 if group < next_group else int(group > next_group)

    # otherwise we can assume same group, so we have to compare more granularly
    if underscored and not next_underscored:
        return 1
    elif not underscored and next_underscored:
        return -1

    return -1 if key < next_key else int(key > next_key)


class MetadataProps:

    def __init__(
        self,
        book: "Audiobook",
        sample_audio2_tags: dict[TagSource | AdditionalTags, str],
    ):

        common_filename = (
            find_greatest_common_string(
                [book.sample_audio1.name, book.sample_audio2.name]
            )
            if book.sample_audio2
            else book.sample_audio1.name
        )
        self.fs_basename = book.basename
        self.fs_filename_c = common_filename
        self.fs_name = str(Path(book.basename) / common_filename)
        self.fs_name_lower = self.fs_name.lower()
        self.fs_year = parse_year(self.fs_name)

        self.title1 = book.id3_title
        self.title2 = sample_audio2_tags.get("title", "")
        self.title_c = find_greatest_common_string([self.title1, self.title2])

        self.album1 = book.id3_album
        self.album2 = sample_audio2_tags.get("album", "")
        self.album_c = find_greatest_common_string([self.album1, self.album2])

        self.sortalbum1 = book.id3_sortalbum
        self.sortalbum2 = sample_audio2_tags.get("sortalbum", "")
        self.sortalbum_c = find_greatest_common_string(
            [self.sortalbum1, self.sortalbum2]
        )

        self.artist1 = book.id3_artist
        self.artist2 = sample_audio2_tags.get("artist", "")
        self.artist_c = find_greatest_common_string([self.artist1, self.artist2])

        self.albumartist1 = book.id3_albumartist
        self.albumartist2 = sample_audio2_tags.get("albumartist", "")
        self.albumartist_c = find_greatest_common_string(
            [self.albumartist1, self.albumartist2]
        )

        self.date = book.id3_date
        self.year = get_year_from_date(self.date)
        self.comment = book.id3_comment
        self.composer = book.id3_composer

        self.author_in_comment = parse_author(self.comment, "comment", default="")
        self.narrator_in_comment = parse_narrator(self.comment, "comment", default="")

        self._t_is_partno, self._t_partno_score, self._t_is_only_part_no = (
            get_title_partno_score(
                self.title1, self.title2, self.album1, self.sortalbum1
            )
        )
        if self._t_is_partno:
            self.title_c = strip_part_number(self.title_c)

        # Title
        self._t1_numbers = ""
        self._t2_numbers = ""
        self._t1_startswith_num = False
        self._t2_startswith_num = False
        self._t1_is_in_fs_name = False
        self._t1_fuzzy_fs_name = 0
        self._t1_eq_t2 = False
        self._t1_is_missing = not self.title1
        if self.title1:
            self._t1_numbers = get_numbers_in_string(self.title1)
            self._t2_numbers = get_numbers_in_string(self.title2)
            self._t1_startswith_num = startswith_num_pattern.match(self.title1)
            self._t2_startswith_num = startswith_num_pattern.match(self.title2)
            self._t1_is_in_fs_name = self.title1.lower() in self.fs_name_lower
            self._t1_fuzzy_fs_name = fuzz.token_sort_ratio(
                self.title1.lower(), self.fs_name_lower
            )
            self._t1_eq_t2 = self.title1 == self.title2

        self._t2_is_in_fs_name = False
        self._t2_is_missing = not self.title2
        if self.title2:
            self._t2_is_in_fs_name = self.title2.lower() in self.fs_name_lower

        # Album
        self._al1_eq_al2 = False
        self._al1_fuzzy_fs_name = 0
        self._al1_is_in_fs_name = False
        self._al1_is_in_title = False
        self._al1_numbers = ""
        self._al1_startswith_num = False
        self._al1_is_missing = not self.album1
        if self.album1:
            self._al1_eq_al2 = self.album1 == self.album2
            self._al1_fuzzy_fs_name = fuzz.token_sort_ratio(
                self.album1.lower(), self.fs_name_lower
            )
            self._al1_is_in_fs_name = self.album1.lower() in self.fs_name_lower
            self._al1_is_in_title = self.album1.lower() in self.title1.lower()
            self._al1_numbers = get_numbers_in_string(self.album1)
            self._al1_startswith_num = startswith_num_pattern.match(self.album1)

        self._al2_is_in_fs_name = False
        self._al2_is_in_title = False
        self._al2_numbers = ""
        self._al2_startswith_num = False
        self._al2_is_missing = not self.album2
        if self.album2:
            self._al2_is_in_fs_name = self.album2.lower() in self.fs_name_lower
            self._al2_is_in_title = self.album2.lower() in self.title2.lower()
            self._al2_numbers = get_numbers_in_string(self.album2)
            self._al2_startswith_num = startswith_num_pattern.match(self.album2)

        # Sort Album
        self._sal1_eq_sal2 = False
        self._sal1_fuzzy_fs_name = 0
        self._sal1_is_in_fs_name = False
        self._sal1_is_in_title = False
        self._sal1_numbers = ""
        self._sal1_startswith_num = False
        self._sal1_is_missing = not self.sortalbum1
        if self.sortalbum1:
            self._sal1_eq_sal2 = self.sortalbum1 == self.sortalbum2
            self._sal1_fuzzy_fs_name = fuzz.token_sort_ratio(
                self.sortalbum1.lower(), self.fs_name_lower
            )
            self._sal1_is_in_fs_name = self.sortalbum1.lower() in self.fs_name_lower
            self._sal1_is_in_title = self.sortalbum1.lower() in self.title1.lower()
            self._sal1_numbers = get_numbers_in_string(self.sortalbum1)
            self._sal1_startswith_num = startswith_num_pattern.match(self.sortalbum1)

        self._sal2_is_in_fs_name = False
        self._sal2_is_in_title = False
        self._sal2_numbers = ""
        self._sal2_startswith_num = False
        self._sal2_is_missing = not self.sortalbum2
        if self.sortalbum2:
            self._sal2_is_in_fs_name = self.sortalbum2.lower() in self.fs_name_lower
            self._sal2_is_in_title = self.sortalbum2.lower() in self.title2.lower()
            self._sal2_numbers = get_numbers_in_string(self.sortalbum2)
            self._sal2_startswith_num = startswith_num_pattern.match(self.sortalbum2)

        # Artist
        self._ar1_is_in_fs_name = False
        self._ar1_fuzzy_fs_name = 0
        self._ar1_is_graphic_audio = False
        self._ar1_is_maybe_narrator = False
        self._ar1_is_maybe_author = False
        self._ar1_eq_comment_narrator = False
        self._ar1_eq_ar2 = False
        self._ar1_is_missing = not self.artist1
        if self.artist1:
            self._ar1_eq_ar2 = self.artist1 == self.artist2
            self._ar1_is_in_fs_name = self.artist1.lower() in self.fs_name_lower
            self._ar1_fuzzy_fs_name = fuzz.token_sort_ratio(
                self.artist1.lower(), self.fs_name_lower
            )
            self._ar1_is_graphic_audio = has_graphic_audio(self.artist1)
            self._ar1_is_maybe_narrator = parse_narrator(self.artist1, "generic")
            self._ar1_is_maybe_author = parse_author(self.artist1, "generic")

        self._ar2_is_in_fs_name = False
        self._ar2_is_graphic_audio = False
        self._ar2_is_missing = not self.artist2
        if self.artist2:
            self._ar2_is_in_fs_name = self.artist2.lower() in self.fs_name_lower
            self._ar2_is_graphic_audio = has_graphic_audio(self.artist2)

        # Album Artist
        self._aar1_is_in_fs_name = False
        self._aar1_fuzzy_fs_name = 0
        self._aar1_is_graphic_audio = False
        self._aar1_is_maybe_narrator = False
        self._aar1_is_maybe_author = False
        self._aar1_eq_aar2 = False
        if self.albumartist1:
            self._aar1_eq_aar2 = self.albumartist1 == self.albumartist2
            self._aar1_is_in_fs_name = self.albumartist1.lower() in self.fs_name_lower
            self._aar1_fuzzy_fs_name = fuzz.token_sort_ratio(
                self.albumartist1.lower(), self.fs_name_lower
            )
            self._aar1_is_graphic_audio = has_graphic_audio(self.albumartist1)
            self._aar1_is_maybe_narrator = parse_narrator(self.albumartist1, "generic")
            self._aar1_is_maybe_author = parse_author(self.albumartist1, "generic")
            if self.narrator_in_comment:
                self._aar1_neq_comment_narrator = (
                    self.narrator_in_comment != self.albumartist1
                )

        self._aar2_is_missing = not self.albumartist2
        if self.albumartist2:
            self._aar2_is_in_fs_name = self.albumartist2.lower() in self.fs_name_lower
            self._aar2_is_graphic_audio = has_graphic_audio(self.albumartist2)

        # Comment
        self._ar1_eq_comment_author = False
        self._ar1_eq_comment_narrator = False
        self._aar1_eq_comment_author = False
        self._aar1_eq_comment_narrator = False
        self._comment_author_eq_comment_narrator = False

        # Complex
        self._ar_eq_aar = bool(
            self.artist1 and self.albumartist1 and self.artist1 == self.albumartist1
        )
        self._ar_but_no_aar = bool(self.artist1 and not self.albumartist1)
        self._aar_but_no_ar = bool(self.albumartist1 and not self.artist1)
        self._ar_has_slash = bool("/" in self.artist1)
        self._aar_has_slash = bool("/" in self.albumartist1)

        if self.author_in_comment:
            self._comment_author_eq_comment_narrator = (
                self.narrator_in_comment == self.author_in_comment
            )
            if self.artist1:
                self._ar1_eq_comment_author = self.author_in_comment == self.artist1
            if self.albumartist1:
                self._aar1_eq_comment_author = (
                    self.author_in_comment == self.albumartist1
                )

        if self.narrator_in_comment:
            if self.artist1:
                self._ar1_eq_comment_narrator = self.narrator_in_comment == self.artist1
            if self.albumartist1:
                self._aar1_eq_comment_narrator = (
                    self.narrator_in_comment == self.albumartist1
                )

        str(self)

    def table(self):
        data = [
            [f" - {k}", v]
            for k, v in [
                (k, getattr(self, k))
                for k in sorted(
                    [k for k in dir(self) if not k.startswith("__")],
                    key=functools.cmp_to_key(custom_sort),
                )
            ]
            if not callable(v)
        ]

        return columnar(
            data,
            headers=["key", "value"],
            terminal_width=1000,
            preformatted_headers=True,
            no_borders=True,
            max_column_width=800,
            wrap_max=0,  # don't wrap
        )

    def __str__(self):

        return f"MetadataScore\n" f"{self.table()}\n"


class MetadataScore:
    def __init__(
        self,
        book: "Audiobook",
        sample_audio2_tags: dict[TagSource | AdditionalTags, str],
    ):

        self.title = TitleScoreCard()
        self.author = AuthorScoreCard()
        self.narrator = NarratorScoreCard()
        self.date = DateScoreCard()

        self._p = MetadataProps(book, sample_audio2_tags)

    def __str__(self):

        return (
            f"MetadataScore\n"
            f" - title is likely:   {self.calc_title_scores()}\n"
            f" - author is likely:  {self.calc_author_scores()}\n"
            f" - narrator is likely:  {self.calc_narrator_scores()}\n"
            f" - date is likely:  {self.calc_date_scores()}\n"
        )

    def __repr__(self):
        return self.__str__()

    def get(
        self,
        key: ScoredProp,
        *,
        from_tag: TagSource | None = None,
        from_best: bool = False,
        fallback: str = "",
    ) -> str:

        getattr(self, f"calc_{key}_scores")()
        if from_best:
            from_tag, _score, _prop = getattr(self, key).is_likely
        if from_tag is None:
            raise ValueError("from_tag must be provided if from_best is False")

        if from_tag == "unknown":
            return fallback

        val: str = ""
        if from_tag == "comment":
            val = getattr(self._p, f"{key}_in_comment")
        elif common_str_pattern.match(from_tag):
            val = getattr(self._p, common_str_pattern.sub("", from_tag) + "_c")
        elif from_tag == "fs":
            if key == "date":
                val = self._p.fs_year
        else:
            try:
                val = getattr(self._p, f"{from_tag}1")
            except AttributeError:
                val = getattr(self._p, from_tag)

        val = clean_string(val if val else fallback)
        match key:
            case "author":
                val = parse_author(val, "generic")
            case "narrator":
                val = parse_narrator(val, "generic")
        return val

    def calc_title_scores(self):

        self.title.reset()

        # Title weights
        self.title.title_is_title += int(self._p._t1_is_in_fs_name)
        self.title.title_is_title += int(self._p._t2_is_in_fs_name)
        self.title.title_is_title += int(self._p._t1_fuzzy_fs_name)
        self.title.title_is_title -= 100 * int(self._p._t1_is_missing)
        self.title.title_is_title -= 10 * int(self._p._t2_is_missing)
        self.title.common_title_is_title = (
            0 if self._p._t2_is_missing else self.title.title_is_title
        )
        self.title.common_title_is_title += int(10 if not self._p._t1_eq_t2 else -10)
        self.title.title_is_title += int(10 if self._p._t1_eq_t2 else -10)

        if self._p._t_is_partno:
            if self._p._t_is_only_part_no:
                self.title.title_is_title -= self._p._t_partno_score * 100
            else:
                title1_contains_partno = contains_partno(self._p.title1)
                title2_contains_partno = contains_partno(self._p.title2)
                if title1_contains_partno or title2_contains_partno:
                    self.title.common_title_is_title = max(
                        self.title.title_is_title,
                        self.title.common_title_is_title,
                    )
                    self.title.title_is_title -= self._p._t_partno_score * 5

        else:
            self.title.title_is_title += self._p._t_partno_score

        # Album weights
        self.title.album_is_title += int(self._p._al1_is_in_fs_name)
        self.title.album_is_title += int(self._p._al2_is_in_fs_name)
        self.title.album_is_title += int(self._p._al1_fuzzy_fs_name)
        self.title.album_is_title += int(self._p._al1_is_in_title)
        self.title.album_is_title += int(self._p._al2_is_in_title)
        self.title.album_is_title -= 10 * int(self._p._al1_is_missing)
        self.title.album_is_title -= int(self._p._al2_is_missing)
        self.title.common_album_is_title = (
            0 if self._p._al2_is_missing else self.title.album_is_title
        )
        self.title.common_album_is_title += int(10 if not self._p._al1_eq_al2 else -10)
        self.title.album_is_title += int(10 if self._p._al1_eq_al2 else -10)

        # Sortalbum weights
        self.title.sortalbum_is_title += int(self._p._sal1_is_in_fs_name)
        self.title.sortalbum_is_title += int(self._p._sal2_is_in_fs_name)
        self.title.sortalbum_is_title += int(self._p._sal1_fuzzy_fs_name)
        self.title.sortalbum_is_title += int(self._p._sal1_is_in_title)
        self.title.sortalbum_is_title += int(self._p._sal2_is_in_title)
        self.title.sortalbum_is_title -= 10 * int(self._p._sal1_is_missing)
        self.title.sortalbum_is_title -= int(self._p._sal2_is_missing)
        self.title.common_sortalbum_is_title = (
            0 if self._p._sal2_is_missing else self.title.sortalbum_is_title
        )
        self.title.common_sortalbum_is_title += int(
            10 if not self._p._sal1_eq_sal2 else -10
        )
        self.title.sortalbum_is_title += int(10 if self._p._sal1_eq_sal2 else -10)

    def calc_author_scores(self):
        self.author.reset()

        artist_is_author = 0
        albumartist_is_author = 0
        common_artist_is_author = 0
        common_albumartist_is_author = 0
        comment_contains_author = 0

        if self._p.comment:
            comment_contains_author += 20 * int(bool(self._p.author_in_comment))

        # Artist weights
        if self._p.artist1:
            artist_is_author += int(self._p._ar1_is_in_fs_name)
            artist_is_author += int(self._p._ar1_fuzzy_fs_name)
            artist_is_author -= 500 * int(self._p._ar1_is_graphic_audio)
            artist_is_author -= int(10 if self._p._ar1_is_maybe_narrator else -10)
            artist_is_author += int(10 if self._p._ar1_is_maybe_author else -10)

            if self._p.author_in_comment:
                artist_is_author += int(
                    fuzz.ratio(self._p.author_in_comment, self._p.artist1)
                )
            if self._p.narrator_in_comment:
                artist_is_author += 10 * int(
                    -1 if self._p._ar1_eq_comment_narrator else 1
                )
        else:
            artist_is_author = -404

        if self._p.artist2:
            artist_is_author += int(self._p._ar2_is_in_fs_name)
            artist_is_author -= 10 * int(self._p._ar2_is_missing)
            artist_is_author -= 250 * int(self._p._ar2_is_graphic_audio)

        if self._p.artist1 and self._p.artist2:
            common_artist_is_author = artist_is_author
            common_artist_is_author += int(10 if not self._p._ar1_eq_ar2 else -10)
            artist_is_author += int(10 if self._p._ar1_eq_ar2 else -10)

        # Album Artist weights
        if self._p.albumartist1:
            albumartist_is_author += int(self._p._aar1_is_in_fs_name)
            albumartist_is_author += int(self._p._aar1_fuzzy_fs_name)
            albumartist_is_author -= 500 * int(self._p._aar1_is_graphic_audio)
            albumartist_is_author -= int(10 if self._p._aar1_is_maybe_narrator else -10)
            albumartist_is_author += int(10 if self._p._aar1_is_maybe_author else -10)

            if self._p.author_in_comment:
                albumartist_is_author += int(
                    fuzz.ratio(self._p.author_in_comment, self._p.albumartist1)
                )

            if self._p.narrator_in_comment:
                albumartist_is_author += 10 * int(
                    -1 if self._p._aar1_eq_comment_narrator else 1
                )
        else:
            albumartist_is_author = -404

        if self._p.albumartist2:
            albumartist_is_author += int(self._p._aar2_is_in_fs_name)
            albumartist_is_author -= 10 * int(self._p._aar2_is_missing)
            albumartist_is_author -= 250 * int(self._p._aar2_is_graphic_audio)

        if self._p.albumartist1 and self._p.albumartist2:
            common_albumartist_is_author = albumartist_is_author
            common_albumartist_is_author += int(
                10 if not self._p._aar1_eq_aar2 else -10
            )
            albumartist_is_author += int(10 if self._p._aar1_eq_aar2 else -10)

        if self._p.artist1 == self._p.albumartist1:
            artist_is_author += 1

        if self._p.artist2 == self._p.albumartist2:
            artist_is_author += 1

        if self._p.author_in_comment and self._p.narrator_in_comment:
            comment_contains_author += 10 * int(
                -1 if self._p._comment_author_eq_comment_narrator else 1
            )

        # Update the scores
        self.author.artist_is_author = artist_is_author
        self.author.albumartist_is_author = albumartist_is_author
        self.author.common_artist_is_author = common_artist_is_author
        self.author.common_albumartist_is_author = common_albumartist_is_author
        self.author.comment_contains_author = comment_contains_author

    def calc_narrator_scores(self):
        self.narrator.reset()

        artist_is_narrator = 0
        albumartist_is_narrator = 0
        composer_is_narrator = 0
        common_artist_is_narrator = 0
        common_albumartist_is_narrator = 0
        comment_contains_narrator = 0

        if self._p.comment:
            comment_contains_narrator += 40 * int(bool(self._p.narrator_in_comment))

        # If artist and album artist are the same, they're probably author, not narrator.
        # If either is missing, then the one that is present is probably the author.

        # Sometimes we get some false positives, where artist is narrator and composer is the author, but
        # we can only pick one.
        if any([self._p._ar_eq_aar, self._p._ar_but_no_aar, self._p._aar_but_no_ar]):
            artist_is_narrator = 7 if self._p._ar_has_slash else -99
            albumartist_is_narrator = 7 if self._p._aar_has_slash else -99

        else:
            # Artist weights
            if self._p.artist1:
                artist_is_narrator += int(self._p._ar1_is_in_fs_name)
                artist_is_narrator += int(self._p._ar1_fuzzy_fs_name)
                artist_is_narrator -= 500 * int(self._p._ar1_is_graphic_audio)
                artist_is_narrator -= int(10 if self._p._ar1_is_maybe_narrator else -10)
                artist_is_narrator += int(10 if self._p._ar1_is_maybe_author else -10)

                if self._p.narrator_in_comment:
                    artist_is_narrator += int(
                        fuzz.ratio(self._p.narrator_in_comment, self._p.artist1)
                    )
                if self._p.author_in_comment:
                    artist_is_narrator += 10 * int(
                        -1 if self._p._ar1_eq_comment_author else 1
                    )

            else:
                artist_is_narrator = -404

            if self._p.artist2:
                artist_is_narrator += int(self._p._ar2_is_in_fs_name)
                artist_is_narrator -= 10 * int(self._p._ar2_is_missing)
                artist_is_narrator -= 250 * int(self._p._ar2_is_graphic_audio)

            if self._p.artist1 and self._p.artist2:
                common_artist_is_narrator = artist_is_narrator
                common_artist_is_narrator += int(10 if not self._p._ar1_eq_ar2 else -10)
                artist_is_narrator += int(10 if self._p._ar1_eq_ar2 else -10)

            # Album Artist weights
            if self._p.albumartist1:
                albumartist_is_narrator += int(self._p._aar1_is_in_fs_name)
                albumartist_is_narrator += int(self._p._aar1_fuzzy_fs_name)
                albumartist_is_narrator -= 500 * int(self._p._aar1_is_graphic_audio)
                albumartist_is_narrator -= int(
                    10 if self._p._aar1_is_maybe_narrator else -10
                )

                if self._p.narrator_in_comment:
                    albumartist_is_narrator += int(
                        fuzz.ratio(self._p.narrator_in_comment, self._p.albumartist1)
                    )
                if self._p.author_in_comment:
                    albumartist_is_narrator += 10 * int(
                        -1 if self._p._aar1_eq_comment_author else 1
                    )
            else:
                albumartist_is_narrator = -404

            if self._p.albumartist2:
                albumartist_is_narrator += int(self._p._aar2_is_in_fs_name)
                albumartist_is_narrator -= 10 * int(self._p._aar2_is_missing)
                albumartist_is_narrator -= 250 * int(self._p._aar2_is_graphic_audio)

            if self._p.albumartist1 and self._p.albumartist2:
                common_albumartist_is_narrator = albumartist_is_narrator
                common_albumartist_is_narrator += int(
                    10 if not self._p._aar1_eq_aar2 else -10
                )
                albumartist_is_narrator += int(10 if self._p._aar1_eq_aar2 else -10)

        if self._p.composer and self._p.composer != self._p.artist1:
            composer_is_narrator = 5 * int(len(to_words(self._p.composer)))

        self.narrator.artist_is_narrator = artist_is_narrator
        self.narrator.albumartist_is_narrator = albumartist_is_narrator
        self.narrator.common_artist_is_narrator = common_artist_is_narrator
        self.narrator.common_albumartist_is_narrator = common_albumartist_is_narrator
        self.narrator.comment_contains_narrator = comment_contains_narrator
        self.narrator.composer_is_narrator = composer_is_narrator

    def calc_date_scores(self):
        self.date.reset()

        date_is_date = 0
        fs_contains_date = 0

        if self._p.date and not self._p.fs_year:
            date_is_date += 10
        elif self._p.fs_year and not self._p.date:
            fs_contains_date += 10
        elif self._p.date and self._p.fs_year:
            if int(self._p.year) < int(self._p.fs_year):
                date_is_date += 1
            else:
                fs_contains_date += 1

        self.date.date_is_date = date_is_date
        self.date.fs_contains_date = fs_contains_date

        # if book.date:
        #     li(f"Date: {book.date}")
        # # extract 4 digits from date
        # book.year = get_year_from_date(book.date)


def extract_metadata(book: "Audiobook", quiet: bool = False) -> "Audiobook":

    if not quiet:
        smart_print(
            f"Sampling [[{book.sample_audio1.name}]] for book metadata and quality info:",
            highlight_color=PATH_COLOR,
        )

    li = print_list_item if not quiet else lambda *_: None

    # read id3 tags of audio file
    sample_audio1_tags = extract_id3_tags(book.sample_audio1)
    sample_audio2_tags = extract_id3_tags(
        book.sample_audio2
        or book.sample_audio1  # if only one audio file, fall back to the same file
    )

    for tag, value in sample_audio1_tags.items():
        if hasattr(book, f"id3_{tag}"):
            setattr(book, f"id3_{tag}", value)

    book.id3_year = get_year_from_date(book.id3_date)
    # Note: only works for mp3 files, will always return None for m4b files
    book.has_id3_cover = bool(sample_audio1_tags.get("cover"))

    id3_score = MetadataScore(book, sample_audio2_tags)

    book.title = id3_score.get("title", from_best=True, fallback=book.fs_title)
    book.album = book.title
    book.sortalbum = strip_leading_articles(book.title)

    book.artist = id3_score.get("author", from_best=True, fallback=book.fs_author)
    book.albumartist = book.artist

    book.narrator = id3_score.get("narrator", from_best=True, fallback=book.fs_narrator)

    li(f"Title: {book.title}")
    li(f"Author: {book.author}")
    if book.narrator:
        li(f"Narrator: {book.narrator}")

        # TODO: Author/Narrator and "Book name by Author" in folder name

        # If comment does not have narrator, but narrator is not empty,
        # pre-pend narrator to comment as "Narrated by <narrator>. <existing comment>"
        if not book.id3_comment:
            book.id3_comment = f"Read by {book.narrator}"
        elif not parse_narrator(book.id3_comment, "comment"):
            book.id3_comment = f"Read by {book.narrator} // {book.id3_comment}"

    book.date = id3_score.get("date", from_best=True, fallback=book.fs_year)
    if book.date:
        li(f"Date: {book.date}")
    # extract 4 digits from date
    book.year = get_year_from_date(book.date)

    # convert bitrate and sample rate to friendly to kbit/s, rounding to nearest tenths, e.g. 44.1 kHz
    li(f"Quality: {book.bitrate_friendly} @ {book.samplerate_friendly}")
    li(f"Duration: {book.duration('inbox', 'human')}")
    if not book.has_id3_cover:
        li(f"No cover art")

    return book
