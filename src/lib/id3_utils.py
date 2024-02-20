import shutil
import subprocess
from pathlib import Path
from typing import cast, Literal, TYPE_CHECKING

from eyed3 import AudioFile
from eyed3.id3 import Tag

from src.lib.misc import compare_trim
from src.lib.term import smart_print

MissingApplicationError = ValueError

if TYPE_CHECKING:
    from src.lib.audiobook import Audiobook


def write_id3_tags(file: Path, exiftool_args: list[str]) -> None:
    api_opts = ["-api", 'filter="s/ \\(approx\\)//"']  # remove (approx) from output

    # if file doesn't exist, throw error
    if not file.is_file():
        raise RuntimeError(f"Error: Cannot write id3 tags, {file} does not exist")

    # make sure the exiftool command exists
    if not shutil.which("exiftool"):
        raise RuntimeError(
            "Error: exiftool is not available, please install it with (apt-get install exiftool) and try again"
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
            "Error: eyed3 is not available, please install it with (pip install eyed3) and try again"
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

    m4b_to_check = book.converted_file if in_dir == "converted" else book.build_file

    book_to_check = Audiobook(m4b_to_check)

    exiftool_args = []

    title_needs_updating = False
    author_needs_updating = False
    date_needs_updating = False
    comment_needs_updating = False

    if book.title and book_to_check.id3_title != book.title:
        title_needs_updating = True
        smart_print(
            f"Title needs updating: {book_to_check.id3_title if book_to_check.id3_title else '(Missing)'} » {book.title}"
        )

    if book.author and book_to_check.id3_artist != book.author:
        author_needs_updating = True
        smart_print(
            f"Artist (author) needs updating: {book_to_check.id3_artist if book_to_check.id3_artist else '(Missing)'} » {book.author}"
        )

    if book.title and book_to_check.id3_album != book.title:
        title_needs_updating = True
        smart_print(
            f"Album (title) needs updating: {book_to_check.id3_album if book_to_check.id3_album else '(Missing)'} » {book.title}"
        )

    if book.title and book_to_check.id3_sortalbum != book.title:
        title_needs_updating = True
        smart_print(
            f"Sort album (title) needs updating: {book_to_check.id3_sortalbum if book_to_check.id3_sortalbum else '(Missing)'} » {book.title}"
        )

    if book.author and book_to_check.id3_albumartist != book.author:
        author_needs_updating = True
        smart_print(
            f"Album artist (author) needs updating: {book_to_check.id3_albumartist if book_to_check.id3_albumartist else '(Missing)'} » {book.author}"
        )

    if book.date and book_to_check.id3_date != book.date:
        date_needs_updating = True
        smart_print(
            f"Date needs updating: {book_to_check.id3_date if book_to_check.id3_date else '(Missing)'} » {book.date}"
        )

    if book.comment and compare_trim(book_to_check.id3_comment, book.comment):
        comment_needs_updating = True
        smart_print(
            f"Comment needs updating: {book_to_check.id3_comment if book_to_check.id3_comment else '(Missing)'} » {book.comment}"
        )

    # for each of the id3 tags that need updating, write the id3 tags
    if title_needs_updating:
        exiftool_args.extend(
            ["-Title=" + book.title, "-Album=" + book.title, "-SortAlbum=" + book.title]
        )

    if author_needs_updating:
        exiftool_args.extend(["-Artist=" + book.author, "-SortArtist=" + book.author])

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
        write_id3_tags(m4b_to_check, exiftool_args)
