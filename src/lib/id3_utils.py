import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast, Literal, overload, TYPE_CHECKING

import ffmpeg
from eyed3 import AudioFile
from eyed3.id3 import Tag
from rapidfuzz import fuzz
from tinta import Tinta

from src.lib.cleaners import clean_string, strip_leading_articles
from src.lib.misc import compare_trim, fix_ffprobe, get_numbers_in_string

fix_ffprobe()

from src.lib.parsers import (
    contains_partno,
    find_greatest_common_string,
    get_title_partno_score,
    get_year_from_date,
    has_graphic_audio,
    parse_author,
    parse_narrator,
)
from src.lib.term import (
    nl,
    PATH_COLOR,
    print_debug,
    print_error,
    print_list_item,
    smart_print,
)
from src.lib.typing import BadFileError, ScoredProp, TagSource

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
        audiofile.tag.release_date = date
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
        audiofile.tag.comments.set(comment)  # type: ignore

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


def extract_id3_tags(file: Path | None, *tags: str, throw=False) -> dict[str, str]:

    if not file or not file.exists():
        if throw:
            raise BadFileError(
                f"Error: Cannot extract id3 tags, '{file}' does not exist"
            )
        return {}

    try:
        if ffresult := ffprobe_file(file, throw=throw):
            return {
                tag: ffresult["format"]["tags"].get(tag, "")
                for tag in [tag.lower() for tag in tags]
            }
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
    def is_likely(self) -> tuple[TagSource, int]:
        # put all the scores in a list and return the highest score and its var name
        rep = re.compile(rf"_(is|contains)_{self._prop}$")
        scores = [
            (cast(TagSource, re.sub(rep, "", p)), getattr(self, p))
            for p in dir(self)
            if not p.startswith("_")
            and p.endswith(self._prop)
            and isinstance(getattr(self, p), int)
        ]
        if not scores or all(score <= 0 for _, score in scores):
            return "unknown", 0
        tag, best = max(scores, key=lambda x: x[1])
        # return the highest score and the name of its variable - use inflection or inspect
        return tag, best

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

    props: list[TagSource] = [
        "artist",
        "albumartist",
        "common_artist",
        "common_albumartist",
        "comment",
    ]

    def __str__(self):
        return (
            f"NarratorScoreCard\n"
            f" - artist_is_narrator: {self.artist_is_narrator}\n"
            f" - albumartist_is_narrator: {self.albumartist_is_narrator}\n"
            f" - common_artist_is_narrator: {self.common_artist_is_narrator}\n"
            f" - common_albumartist_is_narrator: {self.common_albumartist_is_narrator}\n"
            f" - comment_contains_narrator: {self.comment_contains_narrator}\n"
        )


class MetadataScore:
    def __init__(
        self,
        book: "Audiobook",
        sample_audio2_tags: dict[str, str],
    ):

        self.title = TitleScoreCard()
        self.author = AuthorScoreCard()
        self.narrator = NarratorScoreCard()

        common_filename = (
            find_greatest_common_string(
                [book.sample_audio1.name, book.sample_audio2.name]
            )
            if book.sample_audio2
            else book.sample_audio1.name
        )
        self._basename = book.basename
        self._filename = common_filename
        self._folder_and_filename = str(Path(book.basename) / common_filename)

        self._title1 = book.id3_title
        self._title2 = sample_audio2_tags.get("title", "")
        self._artist1 = book.id3_artist
        self._artist2 = sample_audio2_tags.get("artist", "")
        self._albumartist1 = book.id3_albumartist
        self._albumartist2 = sample_audio2_tags.get("albumartist", "")
        self._album1 = book.id3_album
        self._album2 = sample_audio2_tags.get("album", "")
        self._sortalbum1 = book.id3_sortalbum
        self._sortalbum2 = sample_audio2_tags.get("sortalbum", "")
        self._comment = book.id3_comment

        self._common_title = find_greatest_common_string([self._title1, self._title2])
        self._common_artist = find_greatest_common_string(
            [self._artist1, self._artist2]
        )
        self._common_albumartist = find_greatest_common_string(
            [self._albumartist1, self._albumartist2]
        )
        self._common_album = find_greatest_common_string([self._album1, self._album2])
        self._common_sortalbum = find_greatest_common_string(
            [self._sortalbum1, self._sortalbum2]
        )

        self._numbers_in_title1 = get_numbers_in_string(self._title1)
        self._numbers_in_title2 = get_numbers_in_string(self._title2)
        self._numbers_in_album1 = get_numbers_in_string(self._album1)
        self._numbers_in_album2 = get_numbers_in_string(self._album2)
        self._numbers_in_sortalbum1 = get_numbers_in_string(self._sortalbum1)
        self._numbers_in_sortalbum2 = get_numbers_in_string(self._sortalbum2)

        self._title1_starts_with_number = re.match(r"^\d+", self._title1)
        self._title2_starts_with_number = re.match(r"^\d+", self._title2)
        self._album1_starts_with_number = re.match(r"^\d+", self._album1)
        self._album2_starts_with_number = re.match(r"^\d+", self._album2)
        self._sortalbum1_starts_with_number = re.match(r"^\d+", self._sortalbum1)
        self._sortalbum2_starts_with_number = re.match(r"^\d+", self._sortalbum2)

        self._author_in_comment = parse_author(self._comment, "tag")
        self._narrator_in_comment = parse_narrator(self._comment)

    def __str__(self):

        return (
            f"MetadataScore\n"
            f" - title 1:           {self._title1}\n"
            f" - title 2:           {self._title2}\n"
            f" - title c:           {self._common_title}\n"
            f" - artist 1:          {self._artist1}\n"
            f" - artist 2:          {self._artist2}\n"
            f" - artist c:          {self._common_artist}\n"
            f" - albumartist 1:     {self._albumartist1}\n"
            f" - albumartist 2:     {self._albumartist2}\n"
            f" - albumartist c:     {self._common_albumartist}\n"
            f" - album 1:           {self._album1}\n"
            f" - album 2:           {self._album2}\n"
            f" - album c:           {self._common_album}\n"
            f" - sortalbum 1:       {self._sortalbum1}\n"
            f" - sortalbum 2:       {self._sortalbum2}\n"
            f" - sortalbum c:       {self._common_sortalbum}\n"
            f" - #s in title 1:     {self._numbers_in_title1}\n"
            f" - #s in title 2:     {self._numbers_in_title2}\n"
            f" - #s in album 1:     {self._numbers_in_album1}\n"
            f" - #s in album 2:     {self._numbers_in_album2}\n"
            f" - #s in sortalbum 1: {self._numbers_in_sortalbum1}\n"
            f" - #s in sortalbum 2: {self._numbers_in_sortalbum2}\n"
            f"\n"
            f" - title is likely:   {self.calc_title_scores()}\n"
            f" - author is likely:  {self.calc_author_scores()}\n"
            f" - narrator is likely:  {self.calc_narrator_scores()}\n"
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
            from_tag, _score = getattr(self, key).is_likely
        if from_tag is None:
            raise ValueError("from_tag must be provided if from_best is False")

        if from_tag == "unknown":
            return fallback

        val: str = ""
        if from_tag == "comment":
            val = getattr(self, f"_{key}_in_comment")
        elif from_tag.startswith("common_"):
            val = getattr(self, f"_{from_tag}")
        else:
            val = getattr(self, f"_{from_tag}1")

        val = clean_string(val if val else fallback)
        match key:
            case "author":
                val = parse_author(val, "tag")
            case "narrator":
                val = parse_narrator(val)
        return val

    def calc_title_scores(self):

        self.title.reset()

        fs_name_lower = self._folder_and_filename.lower()

        # Title weights
        t1_is_in_fs_name = self._title1.lower() in fs_name_lower
        t1_fuzzy_fs_name = fuzz.token_sort_ratio(self._title1.lower(), fs_name_lower)
        t1_is_missing = not self._title1
        t2_is_in_fs_name = self._title2.lower() in fs_name_lower
        t2_is_missing = not self._title2
        t1_eq_t2 = self._title1 == self._title2
        title_is_partno, partno_score, title_is_only_part_no = get_title_partno_score(
            self._title1, self._title2, self._album1, self._sortalbum1
        )

        self.title.title_is_title += int(t1_is_in_fs_name)
        self.title.title_is_title += int(t2_is_in_fs_name)
        self.title.title_is_title += int(t1_fuzzy_fs_name)
        self.title.title_is_title -= 100 * int(t1_is_missing)
        self.title.title_is_title -= 10 * int(t2_is_missing)
        self.title.common_title_is_title = (
            0 if t2_is_missing else self.title.title_is_title
        )
        self.title.common_title_is_title += int(10 if not t1_eq_t2 else -10)
        self.title.title_is_title += int(10 if t1_eq_t2 else -10)

        if title_is_partno:
            if title_is_only_part_no:
                self.title.title_is_title -= partno_score * 100
            else:
                title1_contains_partno = contains_partno(self._title1)
                title2_contains_partno = contains_partno(self._title2)
                if title1_contains_partno or title2_contains_partno:
                    self.title.common_title_is_title = max(
                        self.title.title_is_title,
                        self.title.common_title_is_title,
                    )
                    self.title.title_is_title -= partno_score * 5

        else:
            self.title.title_is_title += partno_score

        # Album weights
        al1_is_in_fs_name = self._album1.lower() in fs_name_lower
        al1_fuzzy_fs_name = fuzz.token_sort_ratio(self._album1.lower(), fs_name_lower)
        al1_is_missing = not self._album1
        al1_is_in_title = self._album1.lower() in self._title1.lower()
        al2_is_in_fs_name = self._album2.lower() in fs_name_lower
        al2_is_missing = not self._album2
        al2_is_in_title = self._album2.lower() in self._title2.lower()
        al1_eq_al2 = self._album1 == self._album2

        self.title.album_is_title += int(al1_is_in_fs_name)
        self.title.album_is_title += int(al2_is_in_fs_name)
        self.title.album_is_title += int(al1_fuzzy_fs_name)
        self.title.album_is_title += int(al1_is_in_title)
        self.title.album_is_title += int(al2_is_in_title)
        self.title.album_is_title -= 10 * int(al1_is_missing)
        self.title.album_is_title -= int(al2_is_missing)
        self.title.common_album_is_title = (
            0 if al2_is_missing else self.title.album_is_title
        )
        self.title.common_album_is_title += int(10 if not al1_eq_al2 else -10)
        self.title.album_is_title += int(10 if al1_eq_al2 else -10)

        # Sortalbum weights
        sal1_is_in_title = self._sortalbum1.lower() in self._title1.lower()
        sal1_is_missing = not self._sortalbum1
        sal1_is_in_fs_name = self._sortalbum1.lower() in fs_name_lower
        sal1_fuzzy_fs_name = fuzz.token_sort_ratio(
            self._sortalbum1.lower(), fs_name_lower
        )
        sal2_is_in_title = self._sortalbum2.lower() in self._title2.lower()
        sal2_is_missing = not self._sortalbum2
        sal2_is_in_fs_name = self._sortalbum2.lower() in fs_name_lower
        sal1_eq_sal2 = self._sortalbum1 == self._sortalbum2

        self.title.sortalbum_is_title += int(sal1_is_in_fs_name)
        self.title.sortalbum_is_title += int(sal2_is_in_fs_name)
        self.title.sortalbum_is_title += int(sal1_fuzzy_fs_name)
        self.title.sortalbum_is_title += int(sal1_is_in_title)
        self.title.sortalbum_is_title += int(sal2_is_in_title)
        self.title.sortalbum_is_title -= 10 * int(sal1_is_missing)
        self.title.sortalbum_is_title -= int(sal2_is_missing)
        self.title.common_sortalbum_is_title = (
            0 if sal2_is_missing else self.title.sortalbum_is_title
        )
        self.title.common_sortalbum_is_title += int(10 if not sal1_eq_sal2 else -10)
        self.title.sortalbum_is_title += int(10 if sal1_eq_sal2 else -10)

    def calc_author_scores(self):
        self.author.reset()

        fs_name_lower = self._folder_and_filename.lower()

        # Artist weights
        a1_is_in_fs_name = self._artist1.lower() in fs_name_lower
        a1_fuzzy_fs_name = fuzz.token_sort_ratio(self._artist1.lower(), fs_name_lower)
        a1_is_maybe_author = parse_author(self._artist1, "tag")
        a1_is_maybe_narrator = bool(parse_narrator(self._artist1))
        a1_is_graphic_audio = has_graphic_audio(self._artist1)
        a1_is_missing = not self._artist1
        a2_is_in_fs_name = self._artist2.lower() in fs_name_lower
        a2_is_missing = not self._artist2
        a1_eq_a2 = self._artist1 == self._artist2

        self.author.artist_is_author += int(a1_is_in_fs_name)
        self.author.artist_is_author += int(a2_is_in_fs_name)
        self.author.artist_is_author += int(a1_fuzzy_fs_name)
        self.author.artist_is_author -= 100 * int(a1_is_missing)
        self.author.artist_is_author -= 100 * int(a1_is_graphic_audio)
        self.author.artist_is_author -= 10 * int(a2_is_missing)
        self.author.artist_is_author -= 10 * int(a1_is_maybe_narrator)
        self.author.common_artist_is_author = (
            0 if a2_is_missing else self.author.artist_is_author
        )
        self.author.common_artist_is_author += int(10 if not a1_eq_a2 else -10)
        self.author.artist_is_author += int(10 if a1_eq_a2 else -10)
        self.author.albumartist_is_author += int(10 if a1_is_maybe_author else -10)

        # Album Artist weights
        aa1_is_in_fs_name = self._albumartist1.lower() in fs_name_lower
        aa1_fuzzy_fs_name = fuzz.token_sort_ratio(
            self._albumartist1.lower(), fs_name_lower
        )
        aa1_is_maybe_author = parse_author(self._albumartist1, "tag")
        aa1_is_maybe_narrator = bool(parse_narrator(self._albumartist1))
        aa1_is_graphic_audio = has_graphic_audio(self._albumartist1)
        aa1_is_missing = not self._albumartist1
        aa2_is_in_fs_name = self._albumartist2.lower() in fs_name_lower
        aa2_is_missing = not self._albumartist2
        aa1_eq_aa2 = self._albumartist1 == self._albumartist2

        self.author.albumartist_is_author += int(aa1_is_in_fs_name)
        self.author.albumartist_is_author += int(aa2_is_in_fs_name)
        self.author.albumartist_is_author += int(aa1_fuzzy_fs_name)
        self.author.albumartist_is_author -= 100 * int(aa1_is_missing)
        self.author.albumartist_is_author -= 100 * int(aa1_is_graphic_audio)
        self.author.albumartist_is_author -= 10 * int(aa2_is_missing)
        self.author.albumartist_is_author -= 10 * int(aa1_is_maybe_narrator)
        self.author.common_albumartist_is_author = (
            0 if aa2_is_missing else self.author.albumartist_is_author
        )
        self.author.common_albumartist_is_author += int(10 if not aa1_eq_aa2 else -10)
        self.author.albumartist_is_author += int(10 if aa1_eq_aa2 else -10)
        self.author.albumartist_is_author += int(10 if aa1_is_maybe_author else -10)

        self._author_in_comment = parse_author(self._comment, "tag")
        self.author.comment_contains_author += 40 * int(bool(self._author_in_comment))
        if self._author_in_comment:
            self.author.albumartist_is_author += (
                10 if self._author_in_comment == self._albumartist1 else 0
            )
            self.author.artist_is_author += (
                10 if self._author_in_comment == self._artist1 else 0
            )

    def calc_narrator_scores(self):
        self.narrator.reset()

        fs_name_lower = self._folder_and_filename.lower()

        # Artist weights
        a1_is_in_fs_name = self._artist1.lower() in fs_name_lower
        a1_fuzzy_fs_name = fuzz.token_sort_ratio(self._artist1.lower(), fs_name_lower)
        a1_is_maybe_narrator = parse_narrator(self._artist1)
        a1_is_missing = not self._artist1
        a2_is_in_fs_name = self._artist2.lower() in fs_name_lower
        a2_is_missing = not self._artist2
        a1_eq_a2 = self._artist1 == self._artist2

        self.narrator.artist_is_narrator += int(a1_is_in_fs_name)
        self.narrator.artist_is_narrator += int(a2_is_in_fs_name)
        self.narrator.artist_is_narrator += int(a1_fuzzy_fs_name)
        self.narrator.artist_is_narrator -= 100 * int(a1_is_missing)
        self.narrator.artist_is_narrator -= 10 * int(a2_is_missing)
        self.narrator.common_artist_is_narrator = (
            0 if a2_is_missing else self.narrator.artist_is_narrator
        )
        self.narrator.common_artist_is_narrator += int(10 if not a1_eq_a2 else -10)
        self.narrator.artist_is_narrator += int(10 if a1_eq_a2 else -10)
        self.narrator.albumartist_is_narrator += int(
            10 if a1_is_maybe_narrator else -10
        )

        # Album Artist weights
        aa1_is_in_fs_name = self._albumartist1.lower() in fs_name_lower
        aa1_fuzzy_fs_name = fuzz.token_sort_ratio(
            self._albumartist1.lower(), fs_name_lower
        )
        aa1_is_maybe_narrator = parse_narrator(self._albumartist1)
        aa1_is_missing = not self._albumartist1
        aa2_is_in_fs_name = self._albumartist2.lower() in fs_name_lower
        aa2_is_missing = not self._albumartist2
        aa1_eq_aa2 = self._albumartist1 == self._albumartist2

        self.narrator.albumartist_is_narrator += int(aa1_is_in_fs_name)
        self.narrator.albumartist_is_narrator += int(aa2_is_in_fs_name)
        self.narrator.albumartist_is_narrator += int(aa1_fuzzy_fs_name)
        self.narrator.albumartist_is_narrator -= 100 * int(aa1_is_missing)
        self.narrator.albumartist_is_narrator -= 10 * int(aa2_is_missing)
        self.narrator.common_albumartist_is_narrator = (
            0 if aa2_is_missing else self.narrator.albumartist_is_narrator
        )
        self.narrator.common_albumartist_is_narrator += int(
            10 if not aa1_eq_aa2 else -10
        )
        self.narrator.albumartist_is_narrator += int(10 if aa1_eq_aa2 else -10)
        self.narrator.albumartist_is_narrator += int(
            10 if aa1_is_maybe_narrator else -10
        )

        self.narrator.comment_contains_narrator += 40 * int(
            bool(self._narrator_in_comment)
        )
        self._narrator_in_comment = parse_narrator(self._comment)
        if self._narrator_in_comment:
            self.narrator.albumartist_is_narrator += (
                10 if self._narrator_in_comment == self._albumartist1 else 0
            )
            self.narrator.artist_is_narrator += (
                10 if self._narrator_in_comment == self._artist1 else 0
            )


def extract_metadata(book: "Audiobook", quiet: bool = False) -> "Audiobook":

    if not quiet:
        smart_print(
            f"Sampling [[{book.sample_audio1.name}]] for book metadata and quality info:",
            highlight_color=PATH_COLOR,
        )

    # read id3 tags of audio file
    sample_audio1_tags = extract_id3_tags(
        book.sample_audio1,
        "title",
        "artist",
        "album",
        "albumartist",
        "sortalbum",
        "date",
        "comment",
        "composer",
        "cover",
    )
    sample_audio2_tags = extract_id3_tags(
        book.sample_audio2
        or book.sample_audio1,  # if only one audio file, fall back to the same file
        "title",
        "artist",
        "album",
        "albumartist",
        "sortalbum",
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

    if not quiet:
        print_list_item(f"Title: {book.title}")
        print_list_item(f"Author: {book.author}")
        if book.narrator:
            print_list_item(f"Narrator: {book.narrator}")

    # TODO: Author/Narrator and "Book name by Author" in folder name

    # narrator_in_id3_artist = parse_narrator(book.id3_artist)
    # narrator_in_id3_albumartist = parse_narrator(book.id3_albumartist)
    # narrator_in_id3_comment = parse_narrator(book.id3_comment)
    # narrator_in_id3_composer = parse_narrator(book.id3_composer)

    # id3_artist_has_slash = "/" in book.id3_artist
    # id3_albumartist_has_slash = "/" in book.id3_albumartist

    # # Narrator
    # if id3_artist_has_slash:
    #     match = narrator_slash_pattern.search(book.id3_artist)
    #     book.narrator = re_group(match, "narrator")
    #     book.artist = re_group(match, "author")
    # elif id3_albumartist_has_slash:
    #     match = narrator_slash_pattern.search(book.id3_albumartist)
    #     book.narrator = re_group(match, "narrator")
    #     book.albumartist = re_group(match, "author")
    # elif bool(narrator_in_id3_artist):
    #     match = narrator_in_artist_pattern.search(book.id3_artist)
    #     book.artist = re_group(match, "author")
    #     book.narrator = re_group(match, "narrator")
    # elif bool(narrator_in_id3_albumartist):
    #     match = narrator_in_artist_pattern.search(book.id3_albumartist)
    #     book.albumartist = re_group(match, "author")
    #     book.narrator = re_group(match, "narrator")
    # elif bool(narrator_in_id3_comment):
    #     book.narrator = narrator_in_id3_comment
    # elif bool(narrator_in_id3_composer):
    #     book.narrator = narrator_in_id3_composer
    # else:
    #     book.narrator = book.fs_narrator

    # # Swap first and last names if a comma is present
    # book.artist = swap_firstname_lastname(book.artist)
    # book.albumartist = swap_firstname_lastname(book.albumartist)
    # book.narrator = swap_firstname_lastname(book.narrator)

    # If comment does not have narrator, but narrator is not empty,
    # pre-pend narrator to comment as "Narrated by <narrator>. <existing comment>"
    if book.narrator:
        if not book.id3_comment:
            book.id3_comment = f"Read by {book.narrator}"
        elif not parse_narrator(book.id3_comment):
            book.id3_comment = f"Read by {book.narrator} // {book.id3_comment}"

    # Date:
    if book.id3_date and not book.fs_year:
        book.date = book.id3_date
    elif book.fs_year and not book.id3_date:
        book.date = book.fs_year
    elif book.id3_date and book.fs_year:
        if int(book.id3_year) < int(book.fs_year):
            book.date = book.id3_date
        else:
            book.date = book.fs_year

    if book.date and not quiet:
        print_list_item(f"Date: {book.date}")
    # extract 4 digits from date
    book.year = get_year_from_date(book.date)

    # convert bitrate and sample rate to friendly to kbit/s, rounding to nearest tenths, e.g. 44.1 kHz
    if not quiet:
        print_list_item(
            f"Quality: {book.bitrate_friendly} @ {book.samplerate_friendly}"
        )
        print_list_item(f"Duration: {book.duration('inbox', 'human')}")
        if not book.has_id3_cover:
            print_list_item(f"No cover art")

    return book
