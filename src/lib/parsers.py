import import_debug

import_debug.bug.push("src/lib/parsers.py")
import os
import re
import string
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING

from src.lib.config import cfg
from src.lib.ffmpeg_utils import extract_id3_tag_py, get_bitrate_py, get_samplerate_py
from src.lib.misc import count_numbers_in_string, fix_smart_quotes, re_group
from src.lib.term import PATH_COLOR, print_light_grey, print_list

author_pattern = r"^(?P<author>.*?)[\W\s]*[-_–—\(]"
book_title_pattern = r"(?<=[-_–—])[\W\s]*(?P<book_title>[\w\s]+?)\s*(?=\d{4}|\(|\[|$)"
year_pattern = r"(?P<year>\d{4})"
narrator_pattern = r"(?:read by|narrated by|narrator)\W+(?P<narrator>(?:\w+(?:\s\w+\.?\s)?[\w-]+))(?:\W|$)"
narrator_slash_pattern = r"(?P<author>.+)\/(?P<narrator>.+)"
lastname_firstname_pattern = r"^(?P<lastname>.*?), (?P<firstname>.*)$"
firstname_lastname_pattern = r"^(?P<firstname>.*?).*\s(?P<lastname>\S+)$"
part_number_pattern = r",?[-_–—.\s]*?(?:part|ch(?:\.|apter))?[-_–—.\s]*?(\d+)(?:$|[-_–—.\s]*?(?:of|-)[-_–—.\s]*?(\d+)$)"
part_number_ignore_pattern = r"(?:\bbook\b|\bvol(?:ume)?)\s*\d+$"

if TYPE_CHECKING:
    from src.lib.audiobook import Audiobook


def swap_firstname_lastname(name: str) -> str:
    lastname = ""
    firstname = ""

    if "," in name:
        m = re.match(lastname_firstname_pattern, name)
    else:
        m = re.match(firstname_lastname_pattern, name)

    if m:
        lastname = m.group("lastname")
        firstname = m.group("firstname")

    # If there is a given name, swap the first and last name and return it
    if firstname and lastname:
        return f"{firstname} {lastname}"
    else:
        # Otherwise, return the original name
        return name


def find_greatest_common_string(s: list[str]) -> str:
    if not s:
        return ""

    common_prefixes = set()

    for file1, file2 in combinations(s, 2):
        prefix = os.path.commonprefix([file1, file2])
        common_prefixes.add(prefix)

    valid_prefixes = [
        prefix for prefix in common_prefixes if any(f.startswith(prefix) for f in s)
    ]

    return max(valid_prefixes, key=len, default="")


def strip_part_number(string: str) -> str:

    matches_part_number = re.search(part_number_pattern, string, re.I)
    matches_ignore_if = re.search(part_number_ignore_pattern, string, re.I)

    # if it matches both the part number and ignore, return original string
    if matches_part_number and not matches_ignore_if:
        return re.sub(part_number_pattern, "", string, flags=re.I)
    else:
        return string


def extract_path_info(
    book: "Audiobook",
) -> "Audiobook":
    # Replace single occurrences of . with spaces

    dir_author = swap_firstname_lastname(
        re_group(re.search(author_pattern, book.dir_name), "author")
    )

    dir_title = re_group(re.search(book_title_pattern, book.dir_name), "book_title")
    dir_year = re_group(re.search(year_pattern, book.dir_name), "year")
    dir_narrator = re_group(
        re.search(narrator_pattern, book.dir_name, re.I), "narrator"
    )

    files = [f.name for f in Path(book.inbox_dir).iterdir() if f.is_file()]

    # Get filename common text
    orig_file_name = find_greatest_common_string(files)
    orig_file_name = strip_part_number(orig_file_name)
    orig_file_name = re.sub(r"(part|chapter|ch\.)\s*$", "", orig_file_name, flags=re.I)
    orig_file_name = re.sub(r"\s*$", "", orig_file_name)

    orig_file_name = orig_file_name.rstrip().rstrip(string.punctuation)

    file_author = swap_firstname_lastname(
        re_group(re.search(author_pattern, orig_file_name), "author")
    )
    file_title = re_group(re.search(book_title_pattern, orig_file_name), "book_title")
    file_year = re_group(re.search(year_pattern, orig_file_name), "year")

    meta = {
        "author": dir_author,
        "narrator": dir_narrator,
        "year": dir_year,
        "title": dir_title,
    }

    for d, f, o in zip(
        [dir_author, dir_title, dir_year],
        [file_author, file_title, file_year],
        ["author", "title", "year"],
    ):
        if len(f) > len(d):
            print(f"file_{f} is longer than {f}, setting {f} to {d}")
            meta[o] = f

    book.fs_author = meta["author"]
    book.fs_title = meta["title"]
    book.fs_year = meta["year"]
    book.fs_narrator = meta["narrator"]

    # everything else in the dir name after removing author, title, year, and narrator
    for f, d in zip(
        [file_author, file_title, file_year], [dir_author, dir_title, dir_year]
    ):
        book.dir_extra_junk = re.sub(
            r"^[ \,.\)\}\]]*", "", re.sub(d, "", book.dir_name, flags=re.I)
        )
        book.file_extra_junk = re.sub(
            r"^[ \,.\)\}\]]*", "", re.sub(f, "", orig_file_name, flags=re.I)
        )

    book.orig_file_name = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", orig_file_name)

    return book


def extract_metadata(
    book: "Audiobook",
):

    print_light_grey(
        f"Sampling {{{{{book.sample_audio1.relative_to(book.inbox_dir)}}}}} for id3 tags and quality information...",
        highlight_color=PATH_COLOR,
    )

    book.bitrate = get_bitrate_py(book.sample_audio1)
    book.samplerate = get_samplerate_py(book.sample_audio1)

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

    # second file
    id3_title_2 = extract_id3_tag_py(book.sample_audio2, "title")
    id3_album_2 = extract_id3_tag_py(book.sample_audio2, "album")

    id3_title_numbers = count_numbers_in_string(book.id3_title)
    id3_album_numbers = count_numbers_in_string(book.id3_album)
    id3_sortalbum_numbers = count_numbers_in_string(book.id3_sortalbum)

    # If title has more numbers in it than the album, it's probably a part number like Part 01 or 01 of 42
    book.title_is_partno = (
        id3_title_numbers > id3_album_numbers
        and id3_title_numbers > id3_sortalbum_numbers
    )
    album_matches_album2 = book.id3_album == id3_album_2
    title_matches_title2 = book.id3_title == id3_title_2

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
        book.id3_title and book.id3_title.lower() in book.dir_name.lower()
    )
    album_is_in_folder_name = (
        book.id3_album and book.id3_album.lower() in book.dir_name.lower()
    )
    sortalbum_is_in_folder_name = (
        book.id3_sortalbum and book.id3_sortalbum.lower() in book.dir_name.lower()
    )

    id3_title_is_title = False
    id3_album_is_title = False
    id3_sortalbum_is_title = False

    # Title:
    if not book.id3_title and not book.id3_album and not book.id3_sortalbum:
        # If no id3_title, id3_album, or id3_sortalbum, use the extracted title
        print("No id3_title, id3_album, or id3_sortalbum, so use extracted title")
        book.title = book.fs_title
    else:
        # If (sort)album is in title, it's likely that title is something like {book name}, ch. 6
        # So if album is in title, prefer album
        if album_is_in_title:
            print("id3_album is in title")
            book.title = book.id3_album
            id3_album_is_title = True
        elif sortalbum_is_in_title:
            print("id3_sortalbum is in title")
            book.title = book.id3_sortalbum
            id3_sortalbum_is_title = True
        # If id3_title is in _folder_name, prefer id3_title
        elif title_is_in_folder_name:
            print("id3_title is in folder name")
            book.title = book.id3_title
            id3_title_is_title = True
        # If both sample files' album name matches, prefer album
        elif album_matches_album2:
            print("Album matches album2")
            book.title = book.id3_album
            id3_album_is_title = True
        # If both sample files' title name matches, prefer title
        elif title_matches_title2:
            print("id3_title matches sample2 id3_title")
            book.title = book.id3_title
            id3_title_is_title = True
        # If title is a part no., we should use album or sortalbum
        elif book.title_is_partno:
            print("Title is partno, so we should use album")
            # If album is in _folder_name or if sortalbum doesn't exist, prefer album
            if album_is_in_folder_name or not book.id3_sortalbum:
                book.title = book.id3_album
                id3_album_is_title = True
            elif sortalbum_is_in_folder_name or not book.id3_album:
                book.title = book.id3_sortalbum
                id3_sortalbum_is_title = True
        if not book.title:
            print("Can't figure out what title is, so just use it")
            book.title = book.id3_title
            id3_title_is_title = True

    book.title = strip_part_number(book.title)
    book.title = fix_smart_quotes(book.title)

    print_list(f"Title: {book.title}")

    # Album:
    book.album = book.title
    print_list(f"Album: {book.album}")

    if book.id3_sortalbum:
        book.sortalbum = book.id3_sortalbum
    elif book.id3_album:
        book.sortalbum = book.id3_album
    else:
        book.sortalbum = book.album
    # print "  Sort album: $sortalbum"

    artist_is_in_folder_name = book.id3_artist.lower() in book.dir_name.lower()
    albumartist_is_in_folder_name = (
        book.id3_albumartist.lower() in book.dir_name.lower()
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

    print_list(f"Author: {book.artist}")
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

    print_list(f"Date: {book.date}")
    # extract 4 digits from date
    book.year = re_group(re.search(r"\d{4}", book.date)) if book.date else None

    # convert bitrate and sample rate to friendly to kbit/s, rounding to nearest tenths, e.g. 44.1 kHz
    print_list(f"Quality: {book.bitrate_friendly} @ {book.samplerate_friendly}")

    return book


def count_roman_numerals(d: Path) -> int:
    roman_numeral_pattern = r"(?:part|ch(?:\.|apter))[-_.\s]*[IVXLCDM]+"
    roman_numerals = set()

    for file in d.rglob("*"):
        if any(file.suffix == ext for ext in cfg.AUDIO_EXTS):
            match = re.search(roman_numeral_pattern, str(file), re.I)
            if match:
                roman_numerals.add(match.group())

    return len(roman_numerals)


def get_year_from_date(date: str | None) -> str:
    return re_group(re.search(r"\d{4}", date or ""), default="")


import_debug.bug.pop("src/lib/parsers.py")
