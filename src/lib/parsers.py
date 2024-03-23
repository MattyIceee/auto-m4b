import os
import re
import string
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING

from src.lib.config import cfg
from src.lib.misc import isorted, re_group
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


@dataclass
class romans:
    ones = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]
    tens = ["X", "XX", "XXX", "XL", "L", "LX", "LXX", "LXXX", "XC"]

    @classmethod
    def is_roman_numeral(cls, s: str) -> bool:
        """Test input against all possible valid roman numerals from 1 to 99"""
        s = s.upper()
        for ten in cls.tens:
            for one in cls.ones:
                if s == ten + one or s == ten or s == one:
                    return True
        return False

    @classmethod
    def check(cls, s: str) -> list[re.Match[str]]:
        """Tests a string for possible valid roman numerals from 1 to 99 and returns matches, if found"""
        possible_matches = re.findall(roman_numeral_pattern, s, re.I)
        return [
            p
            for p in possible_matches
            if p and cls.is_roman_numeral(re_group(p, 1, default=""))
        ]

    @classmethod
    def find_all(cls, s: str) -> list[str]:
        """Finds all possible valid roman numerals from 1 to 99 in a string"""
        return [re_group(m, 1) for m in cls.check(s)]

    @classmethod
    def strip(cls, s: str) -> str:
        """Strips roman numerals from a string"""

        # split on word boundaries, and any boundary between lowercase/uppercase or letter/non-letter
        split = re.split(r"(?<=\w)(?=\W)|(?<=\W)(?=\w)|(?<=[a-z])(?=[A-Z])", s)
        return "".join([p for p in split if not cls.is_roman_numeral(p)])


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


def get_roman_numerals_dict(*ss: str) -> dict[str, int]:

    found_roman_numerals = {}

    if len(ss) == 1 and isinstance(ss[0], list):
        ss = ss[0]  # type: ignore

    for s in ss:
        for m in romans.find_all(s):
            found_roman_numerals[m] = found_roman_numerals.get(m, 0) + 1

    return found_roman_numerals


def find_roman_numerals(d: Path) -> dict[str, int]:
    """Makes a dictionary of all the different roman numerals found in the directory"""

    return get_roman_numerals_dict(
        *[
            str(f)
            for f in d.rglob("*")
            if any(f.suffix == ext for ext in cfg.AUDIO_EXTS)
        ]
    )


def count_distinct_roman_numerals(d: Path) -> int:
    """Counts the number of unique roman numerals in a directory, ignoring 'I' to avoid false positives"""
    return len([n for n in find_roman_numerals(d).keys() if n != "I"])


def strip_roman_numerals(d: Path) -> list[Path]:
    """Strips roman numerals from the filenames in a directory and returns
    a list of proposed paths, keeping the original file order"""
    return [f.parent / romans.strip(f.name) for f in d.rglob("*") if f.is_file()]


def roman_numerals_affect_file_order(d: Path) -> bool:
    """Compares the order of files in a directory, both with and without roman numerals.

    Args:
        d (Path): directory to compare

    Returns:
        bool: True if the files are in the same order, False otherwise
    """
    files = [f.stem for f in isorted(d.rglob("*")) if f.is_file()]
    files_no_roman = [romans.strip(f) for f in files]
    files_no_roman_sorted = list(isorted([f.stem for f in strip_roman_numerals(d)]))

    return files_no_roman_sorted != files_no_roman


def get_year_from_date(date: str | None) -> str:
    return re_group(re.search(r"\d{4}", date or ""), default="")


def parse_narrator(s: str) -> str:
    return re_group(re.search(narrator_pattern, s, re.I), "narrator").strip()
