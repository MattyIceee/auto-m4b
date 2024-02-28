import re

import ffmpeg
import import_debug
from tinta import Tinta

from src.lib.parsers import get_year_from_date, strip_part_number, swap_firstname_lastname

import_debug.bug.push("src/lib/id3_utils.py")
import shutil
import subprocess
from pathlib import Path
from typing import cast, Literal, TYPE_CHECKING

from eyed3 import AudioFile
from eyed3.id3 import Tag

from src.lib.misc import compare_trim, fix_smart_quotes, get_numbers_in_string, re_group
from src.lib.term import (
    PATH_COLOR,
    print_debug,
    print_list,
    smart_print,
)

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


def write_id3_tags_eyed3(file: Path, book: "Audiobook") -> None:
    # uses native python library eyed3 to write id3 tags to file
    try:
        import eyed3
    except ImportError:
        raise MissingApplicationError(
            "Error: eyed3 is not available, please install it with\n\n $ pip install eyed3\n\n...then try again"
        )

    audiofile: AudioFile
    if audiofile := eyed3.load(file):  # type: ignore
        audiofile.tag = cast(Tag, audiofile.tag)
        audiofile.tag.title = book.title
        audiofile.tag.artist = book.artist
        audiofile.tag.album = book.album
        audiofile.tag.album_artist = book.albumartist
        audiofile.tag.composer = book.composer
        audiofile.tag.release_date = book.date
        audiofile.tag.track_num = book.track_num
        if audiofile.tag.comments:
            audiofile.tag.comments.set(book.comment)

        audiofile.tag.save()


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

    smart_print("\nVerifying id3 tags...")

    book_to_check = Audiobook(m4b_to_check).extract_metadata(quiet=True)

    exiftool_args = []

    title_needs_updating = False
    author_needs_updating = False
    date_needs_updating = False
    comment_needs_updating = False

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
        _print_needs_updating("Title", book_to_check.id3_title, book.title)

    if book.author and book_to_check.id3_artist != book.author:
        author_needs_updating = True
        _print_needs_updating("Artist (author)", book_to_check.id3_artist, book.author)

    if book.title and book_to_check.id3_album != book.title:
        title_needs_updating = True
        _print_needs_updating("Album (title)", book_to_check.id3_album, book.title)

    if book.title and book_to_check.id3_sortalbum != book.title:
        title_needs_updating = True
        _print_needs_updating(
            "Sort album (title)", book_to_check.id3_sortalbum, book.title
        )

    if book.author and book_to_check.id3_albumartist != book.author:
        author_needs_updating = True
        _print_needs_updating(
            "Album artist (author)", book_to_check.id3_albumartist, book.author
        )

    if book.date and get_year_from_date(book_to_check.id3_date) != get_year_from_date(
        book.date
    ):
        date_needs_updating = True
        _print_needs_updating("Date", book_to_check.id3_date, book.date)

    if book.comment and compare_trim(book_to_check.id3_comment, book.comment):
        comment_needs_updating = True
        _print_needs_updating("Comment", book_to_check.id3_comment, book.comment)

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
        Tinta.up()
        smart_print(Tinta("Verifying id3 tags...").aqua("✓").to_str())




def extract_id3_tag_py(file: Path | None, tag: str) -> str:
    if file is None:
        return ""
    probe_result = ffmpeg.probe(str(file))
    return probe_result["format"]["tags"].get(tag, "")


def extract_metadata(
    book: "Audiobook", quiet: bool = False) -> "Audiobook":

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

    id3_numbers_in_title = get_numbers_in_string(book.id3_title)
    id3_numbers_in_title_2 = get_numbers_in_string(id3_title_2)
    id3_numbers_in_album = get_numbers_in_string(book.id3_album)
    id3_numbers_in_sortalbum = get_numbers_in_string(book.id3_sortalbum)

    # If title has more numbers in it than the album, it's probably a part number like Part 01 or 01 of 42
    book.title_is_partno = (
        len(id3_numbers_in_title) > len(id3_numbers_in_album)
        and len(id3_numbers_in_title) > len(id3_numbers_in_sortalbum)
        and id3_numbers_in_title != id3_numbers_in_title_2
    )
    album_matches_album_2 = book.id3_album == id3_album_2
    title_matches_title_2 = book.id3_title == id3_title_2

    album_is_in_title = (
        book.id3_album
        and book.id3_title
        and book.id3_album.lower() in book.id3_title.lower()
    )
    sortalbum_is_in_title = (
        book.id3_sortalbum
        and book.id3_title
        and book.id3_sortalbum.lower() in book.id3_title.lower()
    )

    title_is_in_folder_name = (
        book.id3_title and book.id3_title.lower() in book.basename.lower()
    )
    album_is_in_folder_name = (
        book.id3_album and book.id3_album.lower() in book.basename.lower()
    )
    sortalbum_is_in_folder_name = (
        book.id3_sortalbum and book.id3_sortalbum.lower() in book.basename.lower()
    )

    id3_title_is_title = False
    id3_album_is_title = False
    id3_sortalbum_is_title = False

    # Title:
    if not book.id3_title and not book.id3_album and not book.id3_sortalbum:
        # If no id3_title, id3_album, or id3_sortalbum, use the extracted title
        if not quiet:
            print_debug("No id3_title, id3_album, or id3_sortalbum, so use extracted title")
        book.title = book.fs_title
    else:
        # If (sort)album is in title, it's likely that title is something like {book name}, ch. 6
        # So if album is in title, prefer album
        if album_is_in_title:
            if not quiet:
                print_debug("id3_album is in title")
            book.title = book.id3_album
            id3_album_is_title = True
        elif sortalbum_is_in_title:
            if not quiet:
                print_debug("id3_sortalbum is in title")
            book.title = book.id3_sortalbum
            id3_sortalbum_is_title = True
        # If id3_title is in _folder_name, prefer id3_title
        elif title_is_in_folder_name:
            if not quiet:
                print_debug("id3_title is in folder name")
            book.title = book.id3_title
            id3_title_is_title = True
        # If both sample files' album name matches, prefer album
        elif album_matches_album_2:
            if not quiet:
                print_debug("Album matches album2")
            book.title = book.id3_album
            id3_album_is_title = True
        # If both sample files' title name matches, prefer title
        elif title_matches_title_2:
            if not quiet:
                print_debug("id3_title matches sample2 id3_title")
            book.title = book.id3_title
            id3_title_is_title = True
        # If title is a part no., we should use album or sortalbum
        elif book.title_is_partno:
            if not quiet:
                print_debug("Title is partno, so we should use album")
            # If album is in _folder_name or if sortalbum doesn't exist, prefer album
            if album_is_in_folder_name or not book.id3_sortalbum:
                book.title = book.id3_album
                id3_album_is_title = True
            elif sortalbum_is_in_folder_name or not book.id3_album:
                book.title = book.id3_sortalbum
                id3_sortalbum_is_title = True
        if not book.title:
            if not quiet:
                print_debug("Can't figure out what title is, so just use it")
            book.title = book.id3_title
            id3_title_is_title = True

    book.title = strip_part_number(book.title)
    book.title = fix_smart_quotes(book.title)

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
    # print "  Sort album: $sortalbum"

    artist_is_in_folder_name = book.id3_artist.lower() in book.basename.lower()
    albumartist_is_in_folder_name = (
        book.id3_albumartist.lower() in book.basename.lower()
    )

    id3_artist_is_author = False
    id3_albumartist_is_author = False
    id3_albumartist_is_narrator = False

    id3_artist_has_narrator = "narrat" in book.id3_artist.lower() or re.search(
        "read.?by", book.id3_artist.lower()
    )
    id3_albumartist_has_narrator = (
        "narrat" in book.id3_albumartist.lower()
        or re.search("read.?by", book.id3_albumartist.lower())
    )
    id3_comment_has_narrator = "narrat" in book.id3_comment.lower() or re.search(
        "read.?by", book.id3_comment.lower()
    )
    id3_composer_has_narrator = "narrat" in book.id3_composer.lower() or re.search(
        "read.?by", book.id3_composer.lower()
    )

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

    id3_artist_has_slash = "/" in book.id3_artist
    id3_albumartist_has_slash = "/" in book.id3_albumartist

    narrator_slash_pattern = re.compile(r"(?P<author>.*)/(?P<narrator>.*)")
    narrator_pattern = re.compile(r"(?P<narrator>.*)")

    # Narrator
    if id3_artist_has_slash:
        match = narrator_slash_pattern.search(book.id3_artist)
        book.narrator = re_group(match, "narrator")
        book.artist = re_group(match, "author")
    elif id3_albumartist_has_slash:
        match = narrator_slash_pattern.search(book.id3_albumartist)
        book.narrator = re_group(match, "narrator")
        book.albumartist = re_group(match, "author")
    elif id3_comment_has_narrator:
        match = narrator_pattern.search(book.id3_comment)
        book.narrator = re_group(match, "narrator")
    elif id3_artist_has_narrator:
        match = narrator_pattern.search(book.id3_artist)
        book.narrator = re_group(match, "narrator")
        book.artist = ""
    elif id3_albumartist_has_narrator:
        match = narrator_pattern.search(book.id3_albumartist)
        book.narrator = re_group(match, "narrator")
        book.albumartist = ""
    elif id3_albumartist_is_narrator:
        book.narrator = book.id3_albumartist
        book.albumartist = ""
    elif id3_composer_has_narrator:
        match = narrator_pattern.search(book.id3_composer)
        book.narrator = re_group(match, "narrator")
        book.composer = ""
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
        elif not id3_comment_has_narrator:
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
        print_list(f"Duration: {book.duration("inbox", "human")}")
        if not book.has_id3_cover:
            print_list(f"No cover art")

    return book


import_debug.bug.pop("src/lib/id3_utils.py")
