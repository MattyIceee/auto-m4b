import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast, Literal, TYPE_CHECKING

import ffmpeg
from eyed3 import AudioFile
from eyed3.id3 import Tag
from tinta import Tinta

from src.lib.cleaners import clean_string
from src.lib.misc import compare_trim, get_numbers_in_string, re_group
from src.lib.parsers import (
    find_greatest_common_string,
    get_year_from_date,
    parse_narrator,
    strip_part_number,
    swap_firstname_lastname,
)
from src.lib.term import (
    PATH_COLOR,
    print_debug,
    print_error,
    print_list,
    smart_print,
)
from src.lib.typing import BadFileError, TagSource

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
        s.dark_grey("»").aqua(right_value)
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
        sys.stdout.write(Tinta().aqua(" ✓\n").to_str())
        smart_print()

    else:
        [update() for update in updates]
        smart_print(Tinta("Done").aqua("✓").to_str())


def extract_id3_tag_py(file: Path | None, tag: str, *, throw=False) -> str:
    from src.lib.config import cfg

    if file is None:
        return ""

    if file and not file.exists():
        raise FileNotFoundError(
            f"Error: Cannot extract id3 tag, '{file}' does not exist"
        )
    try:
        probe_result = ffmpeg.probe(str(file))
    except ffmpeg.Error as e:
        from src.lib.logger import write_err_file

        write_err_file(file, e, "ffprobe")
        if throw:
            raise BadFileError(
                f"Error: Could not extract id3 tag {tag} from {file}"
            ) from e
        print_error(f"Error: Could not extract id3 tag {tag} from {file}")
        if cfg.DEBUG:
            print_debug(e.stderr)
        return ""
    try:
        return probe_result["format"]["tags"].get(tag, "")
    except KeyError:

        if cfg.DEBUG:
            print_debug(
                f"Could not read '{tag}' from {file}'s id3 tags, it probably doesn't exist"
            )
    return ""


class ScoreCard:
    title_is_title: int = 0
    album_is_title: int = 0
    sortalbum_is_title: int = 0
    common_title_is_title: int = 0
    common_album_is_title: int = 0
    common_sortalbum_is_title: int = 0

    def __str__(self):
        return (
            f"ScoreCard\n"
            f" - title_is_title: {self.title_is_title}\n"
            f" - album_is_title: {self.album_is_title}\n"
            f" - sortalbum_is_title: {self.sortalbum_is_title}\n"
            f" - common_title_is_title: {self.common_title_is_title}\n"
            f" - common_album_is_title: {self.common_album_is_title}\n"
            f" - common_sortalbum_is_title: {self.common_sortalbum_is_title}\n"
        )

    def __repr__(self):
        return self.__str__()

    def _is_likely(self, prop: str) -> tuple[TagSource, int]:
        # put all the scores in a list and return the highest score and its var name
        props: list[TagSource] = [
            "title",
            "album",
            "sortalbum",
            "common_title",
            "common_album",
            "common_sortalbum",
        ]
        scores = [getattr(self, f"{p}_is_{prop}") for p in props]
        if not scores or all(score <= 0 for score in scores):
            return "unknown", 0
        best = max(scores)
        # return the highest score and the name of its variable - use inflection or inspect
        return props[scores.index(best)], best

    @property
    def title_is_likely(self):
        return self._is_likely("title")


class MetadataScore:
    def __init__(
        self,
        book: "Audiobook",
        title_1: str,
        title_2: str,
        album_1: str,
        album_2: str,
        sortalbum_1: str,
        sortalbum_2: str,
    ):

        self.score = ScoreCard()

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
        self._title_1 = title_1
        self._title_2 = title_2
        self._album_1 = album_1
        self._album_2 = album_2
        self._sortalbum_1 = sortalbum_1
        self._sortalbum_2 = sortalbum_2

        self._common_title = find_greatest_common_string([self._title_1, self._title_2])
        self._common_album = find_greatest_common_string([self._album_1, self._album_2])
        self._common_sortalbum = find_greatest_common_string(
            [self._sortalbum_1, self._sortalbum_2]
        )

        self._numbers_in_title_1 = get_numbers_in_string(title_1)
        self._numbers_in_title_2 = get_numbers_in_string(title_2)
        self._numbers_in_album_1 = get_numbers_in_string(album_1)
        self._numbers_in_album_2 = get_numbers_in_string(album_2)
        self._numbers_in_sortalbum_1 = get_numbers_in_string(sortalbum_1)
        self._numbers_in_sortalbum_2 = get_numbers_in_string(sortalbum_2)

        self._title_1_starts_with_number = re.match(r"^\d+", title_1)
        self._title_2_starts_with_number = re.match(r"^\d+", title_2)
        self._album_1_starts_with_number = re.match(r"^\d+", album_1)
        self._album_2_starts_with_number = re.match(r"^\d+", album_2)
        self._sortalbum_1_starts_with_number = re.match(r"^\d+", sortalbum_1)
        self._sortalbum_2_starts_with_number = re.match(r"^\d+", sortalbum_2)

    def __str__(self):

        return (
            f"MetadataScore\n"
            f" - title 1:           {self._title_1}\n"
            f" - title 2:           {self._title_2}\n"
            f" - title c:           {self._common_title}\n"
            f" - album 1:           {self._album_1}\n"
            f" - album 2:           {self._album_2}\n"
            f" - album c:           {self._common_album}\n"
            f" - sortalbum 1:       {self._sortalbum_1}\n"
            f" - sortalbum 2:       {self._sortalbum_2}\n"
            f" - sortalbum c:       {self._common_sortalbum}\n"
            f" - #s in title 1:     {self._numbers_in_title_1}\n"
            f" - #s in title 2:     {self._numbers_in_title_2}\n"
            f" - #s in album 1:     {self._numbers_in_album_1}\n"
            f" - #s in album 2:     {self._numbers_in_album_2}\n"
            f" - #s in sortalbum 1: {self._numbers_in_sortalbum_1}\n"
            f" - #s in sortalbum 2: {self._numbers_in_sortalbum_2}\n"
            f"\n"
            f" - title is likely:   {self.get_score('title')}\n"
        )

    def __repr__(self):
        return self.__str__()

    def get_score(
        self,
        tag: TagSource,
    ) -> tuple[TagSource, int]:

        self.score = ScoreCard()
        # get all attributes in this class that start with "{tag}_" and add them up
        [
            getattr(self, attr)
            for attr in dir(self)
            if ("title" in attr or "album" in attr) and not attr.startswith("_")
        ]

        return getattr(self.score, f"{tag}_is_likely")

    @property
    def album_is_in_title(self):
        # If (sort)album is in title, it's likely that title is something like {book name}, ch. 6
        # So if album is in title, prefer album

        score = 0

        if self._album_1.lower() in self._title_1.lower():
            score += 1

        if self._album_2.lower() in self._title_2.lower():
            score += 1

        self.score.album_is_title += score
        return score > 0

    @property
    def album_is_in_fs_name(self):
        # If album is in folder_name/filename or if sortalbum doesn't exist, prefer album
        score = 0
        if self._album_1.lower() in self._folder_and_filename.lower():
            score += 1

        if self._album_2.lower() in self._folder_and_filename.lower():
            score += 1

        self.score.album_is_title += score
        return score > 0

    @property
    def sortalbum_is_missing(self):
        check = not self._sortalbum_1 and not self._sortalbum_2
        if check:
            self.score.sortalbum_is_title -= 100
        return check

    @property
    def album_1_matches_album_2(self):
        """If all things are equal, album is still the better choice"""
        check = self._album_1 == self._album_2
        if check:
            self.score.album_is_title += 9
        return check

    @property
    def common_title_is_in_fs_name(self):
        # If common_title is in fs name, prefer common_title
        # Weighted at double the regular title, because
        check = self._common_title.lower() in self._folder_and_filename.lower()
        if check:
            self.score.common_title_is_title += 2
        return check

    @property
    def common_title_is_empty(self):
        if not self._common_title:
            self.score.common_title_is_title -= 100
        return not self._common_title

    @property
    def sortalbum_1_matches_sortalbum_2(self):
        """If all equal but album is missing, sortalbum is still the better choice"""
        check = self._sortalbum_1 == self._sortalbum_2
        if check:
            self.score.sortalbum_is_title += 6
        return check

    @property
    def sortalbum_is_in_title(self):
        score = 0
        if self._sortalbum_1.lower() in self._title_1.lower():
            score += 1

        if self._sortalbum_2.lower() in self._title_2.lower():
            score += 1

        self.score.sortalbum_is_title += score
        return score

    @property
    def sortalbum_is_in_fs_name(self):
        # If sortalbum is in folder_name/filename or if album doesn't exist, prefer sortalbum
        score = 0
        if self._sortalbum_1.lower() in self._folder_and_filename.lower():
            score += 1

        if self._sortalbum_2.lower() in self._folder_and_filename.lower():
            score += 1

        self.score.sortalbum_is_title += score
        return score

    @property
    def album_is_missing(self):
        check = not self._album_1 and not self._album_2
        if check:
            self.score.album_is_title -= 100
        return check

    @property
    def title_is_in_fs_name(self):
        # If id3_title is in fs name, prefer id3_title
        score = 0
        if self._title_1.lower() in self._folder_and_filename.lower():
            score += 1

        if self._title_2.lower() in self._folder_and_filename.lower():
            score += 1

        self.score.title_is_title += score
        return score > 0

    @property
    def title_is_missing(self):
        check = not self._title_1 and not self._title_2
        if check:
            self.score.title_is_title -= 100
        return check

    @property
    def title_is_partno(self):
        score = 0
        t1 = get_numbers_in_string(self._title_1)
        t2 = get_numbers_in_string(self._title_2)
        a1 = get_numbers_in_string(self._album_1)
        sa1 = get_numbers_in_string(self._sortalbum_1)

        if len(t1) > len(a1):
            score -= 1

        if len(t1) > len(sa1):
            score -= 1

        if t1 != t2:
            score -= 1
        else:
            # if the numbers in both titles match, it's likely that the number is part of the book's name
            score += 1

        self.score.title_is_title -= score
        return score > 0

    @property
    def title_1_matches_title_2(self):
        """If all things are equal, but no (sort)album, title is still the better choice"""
        check = self._title_1 == self._title_2
        if check:
            self.score.title_is_title += 9
        return check


def extract_metadata(book: "Audiobook", quiet: bool = False) -> "Audiobook":

    from .parsers import narrator_pattern

    if not quiet:
        smart_print(
            f"Sampling {{{{{book.sample_audio1.name}}}}} for book metadata and quality info:",
            highlight_color=PATH_COLOR,
        )

    # read id3 tags of audio file
    book.id3_title = extract_id3_tag_py(book.sample_audio1, "title")
    book.id3_artist = extract_id3_tag_py(book.sample_audio1, "artist")
    book.id3_albumartist = extract_id3_tag_py(book.sample_audio1, "album_artist")
    book.id3_album = extract_id3_tag_py(book.sample_audio1, "album")
    book.id3_sortalbum = extract_id3_tag_py(book.sample_audio1, "sort_album")
    book.id3_date = extract_id3_tag_py(book.sample_audio1, "date")
    book.id3_year = get_year_from_date(book.id3_date)
    book.id3_comment = extract_id3_tag_py(book.sample_audio1, "comment")
    book.id3_composer = extract_id3_tag_py(book.sample_audio1, "composer")
    book.has_id3_cover = bool(extract_id3_tag_py(book.sample_audio1, "cover"))

    # second file
    id3_title_2 = extract_id3_tag_py(book.sample_audio2, "title")
    id3_album_2 = extract_id3_tag_py(book.sample_audio2, "album")
    id3_sortalbum_2 = extract_id3_tag_py(book.sample_audio2, "sort_album")

    id3_score = MetadataScore(
        book,
        book.id3_title,
        id3_title_2,
        book.id3_album,
        id3_album_2,
        book.id3_sortalbum,
        id3_sortalbum_2,
    )

    book.title_is_partno = id3_score.title_is_partno

    title_source = id3_score.get_score("title")[0]
    title_attr = f"id3_{title_source}"
    if hasattr(book, title_attr):
        book.title = getattr(book, f"id3_{title_source}")
    else:
        book.title = book.fs_title

    if title_source == "title" and book.title_is_partno:
        book.title = strip_part_number(book.title)
    book.title = clean_string(book.title)
    book.album = clean_string(book.album)
    book.albumartist = clean_string(book.albumartist)
    book.artist = clean_string(book.artist)

    if not quiet:
        print_list(f"Title: {book.title}")

    # Album:
    book.album = book.title
    if not quiet:
        print_list(f"Album: {book.album}")

    if book.id3_sortalbum:
        book.sortalbum = book.id3_sortalbum
    elif book.id3_album:
        book.sortalbum = book.id3_album
    else:
        book.sortalbum = book.album

    artist_is_in_folder_name = book.id3_artist.lower() in book.basename.lower()
    albumartist_is_in_folder_name = (
        book.id3_albumartist.lower() in book.basename.lower()
    )

    id3_artist_is_author = False
    id3_albumartist_is_author = False
    id3_albumartist_is_narrator = False

    # Artist:
    if (
        book.id3_albumartist
        and book.id3_artist
        and book.id3_albumartist != book.id3_artist
    ):
        # Artist and Album Artist are different
        if artist_is_in_folder_name == albumartist_is_in_folder_name:
            # if both or neither are in the folder name, use artist for author and album artist for narrator
            book.artist = book.id3_artist
            book.albumartist = book.id3_albumartist
        elif artist_is_in_folder_name:
            # if only artist is in the folder name, use it for both
            book.artist = book.id3_artist
            book.albumartist = book.id3_artist
        elif albumartist_is_in_folder_name:
            # if only albumartist is in the folder name, use it for both
            book.artist = book.id3_albumartist
            book.albumartist = book.id3_albumartist

        book.artist = book.id3_artist
        book.albumartist = book.id3_artist
        book.narrator = book.id3_albumartist

        id3_artist_is_author = True
        id3_albumartist_is_narrator = True

    elif book.id3_albumartist and not book.id3_artist:
        # Only Album Artist is set, using it for both
        book.artist = book.id3_albumartist
        book.albumartist = book.id3_albumartist

        id3_albumartist_is_author = True
    elif book.id3_artist:
        # Artist is set, prefer it
        book.artist = book.id3_artist
        book.albumartist = book.id3_artist

        id3_artist_is_author = True
    else:
        # Neither Artist nor Album Artist is set, use folder Author for both
        book.artist = book.fs_author
        book.albumartist = book.fs_author

    # TODO: Author/Narrator and "Book name by Author" in folder name

    narrator_in_id3_artist = parse_narrator(book.id3_artist)
    narrator_in_id3_albumartist = parse_narrator(book.id3_albumartist)
    narrator_in_id3_comment = parse_narrator(book.id3_comment)
    narrator_in_id3_composer = parse_narrator(book.id3_composer)

    id3_artist_has_slash = "/" in book.id3_artist
    id3_albumartist_has_slash = "/" in book.id3_albumartist

    narrator_slash_pattern = re.compile(r"(?P<author>.*)/(?P<narrator>.*)")
    narrator_in_artist_pattern = re.compile(rf"(?P<author>.*)\W+{narrator_pattern}")

    # Narrator
    if id3_artist_has_slash:
        match = narrator_slash_pattern.search(book.id3_artist)
        book.narrator = re_group(match, "narrator")
        book.artist = re_group(match, "author")
    elif id3_albumartist_has_slash:
        match = narrator_slash_pattern.search(book.id3_albumartist)
        book.narrator = re_group(match, "narrator")
        book.albumartist = re_group(match, "author")
    elif bool(narrator_in_id3_artist):
        match = narrator_in_artist_pattern.search(book.id3_artist)
        book.artist = re_group(match, "author")
        book.narrator = re_group(match, "narrator")
    elif bool(narrator_in_id3_albumartist):
        match = narrator_in_artist_pattern.search(book.id3_albumartist)
        book.albumartist = re_group(match, "author")
        book.narrator = re_group(match, "narrator")
    elif bool(narrator_in_id3_comment):
        book.narrator = narrator_in_id3_comment
    elif bool(narrator_in_id3_composer):
        book.narrator = narrator_in_id3_composer
    else:
        book.narrator = book.fs_narrator

    # Swap first and last names if a comma is present
    book.artist = swap_firstname_lastname(book.artist)
    book.albumartist = swap_firstname_lastname(book.albumartist)
    book.narrator = swap_firstname_lastname(book.narrator)

    # If comment does not have narrator, but narrator is not empty,
    # pre-pend narrator to comment as "Narrated by <narrator>. <existing comment>"
    if book.narrator:
        if not book.id3_comment:
            book.id3_comment = f"Read by {book.narrator}"
        elif not narrator_in_id3_comment:
            book.id3_comment = f"Read by {book.narrator} // {book.id3_comment}"

    if not quiet:
        print_list(f"Author: {book.artist}")
    if book.narrator and not quiet:
        print_list(f"Narrator: {book.narrator}")

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
        print_list(f"Date: {book.date}")
    # extract 4 digits from date
    book.year = get_year_from_date(book.date)

    # convert bitrate and sample rate to friendly to kbit/s, rounding to nearest tenths, e.g. 44.1 kHz
    if not quiet:
        print_list(f"Quality: {book.bitrate_friendly} @ {book.samplerate_friendly}")
        print_list(f"Duration: {book.duration('inbox', 'human')}")
        if not book.has_id3_cover:
            print_list(f"No cover art")

    return book
