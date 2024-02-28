import import_debug
from tinta import Tinta

from src.lib.parsers import get_year_from_date

import_debug.bug.push("src/lib/id3_utils.py")
import shutil
import subprocess
from pathlib import Path
from typing import cast, Literal, TYPE_CHECKING

from eyed3 import AudioFile
from eyed3.id3 import Tag

from src.lib.misc import compare_trim
from src.lib.term import (
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


import_debug.bug.pop("src/lib/id3_utils.py")
