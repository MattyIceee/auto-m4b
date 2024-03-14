import os
import re
import string
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING

from src.lib.config import cfg
from src.lib.misc import re_group
from src.lib.term import print_debug

author_pattern = r"^(?P<author>.*?)[\W\s]*[-_–—\(]"
book_title_pattern = r"(?<=[-_–—])[\W\s]*(?P<book_title>[\w\s]+?)\s*(?=\d{4}|\(|\[|$)"
year_pattern = r"(?P<year>\d{4})"
narrator_pattern = r"(?:read.?by|narrated.?by|narrator)\W+(?P<narrator>(?:[\w'\.,-]+\s(?:(?!=\s)|$)){1,})"
narrator_slash_pattern = r"(?P<author>.+)\/(?P<narrator>.+)"
lastname_firstname_pattern = r"^(?P<lastname>.*?), (?P<firstname>.*)$"
firstname_lastname_pattern = r"^(?P<firstname>.*?).*\s(?P<lastname>\S+)$"
part_number_pattern = r",?[-_–—.\s]*?(?:part|ch(?:\.|apter))?[-_–—.\s]*?\W*(\d+)(?:$|[-_–—.\s]*?(?:of|-)[-_–—.\s]*?(\d+)\W*$)"
part_number_ignore_pattern = r"(?:\bbook\b|\bvol(?:ume)?)\s*\d+$"
roman_numeral_pattern = r"((?:^|(?<=[\W_]))[IVXLCDM]+(?:$|(?=[\W_])))"

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


def extract_path_info(book: "Audiobook", quiet: bool = False) -> "Audiobook":
    # Replace single occurrences of . with spaces

    dir_author = swap_firstname_lastname(
        re_group(re.search(author_pattern, book.basename), "author")
    )

    dir_title = re_group(re.search(book_title_pattern, book.basename), "book_title")
    dir_year = re_group(re.search(year_pattern, book.basename), "year")
    dir_narrator = parse_narrator(book.basename)

    # remove suffix/extension from files
    files = [f.stem for f in Path(book.inbox_dir).iterdir() if f.is_file()]

    # Get filename common text
    orig_file_name = find_greatest_common_string(files)

    orig_file_name = strip_part_number(orig_file_name)
    orig_file_name = re.sub(r"(part|chapter|ch\.)\s*$", "", orig_file_name, flags=re.I)
    orig_file_name = orig_file_name.rstrip().rstrip(string.punctuation)

    # strip underscores
    orig_file_name = orig_file_name.replace("_", " ")

    # strip leading and trailing -._ spaces and punctuation
    orig_file_name = re.sub(r"^[ \,.\)\}\]_-]*|[ \,.\)\}\]_-]*$", "", orig_file_name)

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
            print_debug(
                f"{o}: file name '{f}' is longer than dir name '{d}', prefer file name"
            )
            meta[o] = f

    book.fs_author = meta["author"]
    book.fs_title = meta["title"]
    book.fs_year = meta["year"]
    book.fs_narrator = meta["narrator"]

    def strip_garbage_chars(path: str) -> str:
        return re.sub(
            r"^[ \,.\)\}\]]*", "", re.sub(path, "", book.basename, flags=re.I)
        )

    # everything else in the dir name after removing author, title, year, and narrator
    for f, d in zip(
        [file_author, file_title, file_year], [dir_author, dir_title, dir_year]
    ):
        book.dir_extra_junk = strip_garbage_chars(d)
        book.file_extra_junk = strip_garbage_chars(f)

    book.orig_file_name = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", orig_file_name)

    return book


def get_roman_numerals_dict(d: Path) -> dict[str, int]:
    """Makes a dictionary of all the different roman numerals found in the directory"""
    roman_numerals = {}

    for file in d.rglob("*"):
        if any(file.suffix == ext for ext in cfg.AUDIO_EXTS):
            match = re_group(re.search(roman_numeral_pattern, str(file), re.I), 1)
            if match:
                roman_numerals[match.upper()] = roman_numerals.get(match, 0) + 1

    return roman_numerals


def count_roman_numerals(d: Path) -> int:
    """Counts the number of roman numerals in a directory"""
    return sum(get_roman_numerals_dict(d).values())


def roman_numerals_affect_file_order(d: Path) -> bool:
    """Compares the order of files in a directory, both with and without roman numerals.

    Args:
        d (Path): directory to compare

    Returns:
        bool: True if the files are in the same order, False otherwise
    """
    files = [f.stem for f in d.rglob("*") if f.is_file()]
    files_no_roman = [re.sub(roman_numeral_pattern, "", f) for f in files]
    sorted_no_roman = list(sorted(files_no_roman))

    return sorted_no_roman != files_no_roman


def get_year_from_date(date: str | None) -> str:
    return re_group(re.search(r"\d{4}", date or ""), default="")


def parse_narrator(s: str) -> str:
    return re_group(re.search(narrator_pattern, s, re.I), "narrator").strip()
