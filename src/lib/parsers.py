import os
import re
import string
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING

import cachetools
import cachetools.func
import regex as rex

from src.lib.misc import get_numbers_in_string, isorted, re_group
from src.lib.term import print_debug
from src.lib.typing import AuthorNarrator, MEMO_TTL, NameParserTarget

# TODO: Add test coverage for narrator with /
# fmt: off
_titlecase_word = r"[A-Z][\p{Ll}\.'-]*"
_author_prefixes = r"[Ww]ritten.?[Bb]y|[Aa]uthor"
_narrator_prefixes = r"(?:[Rr]ead|[Nn]arrated|[Pp]erformed).?[Bb]y|[Nn]arrator"
def _name_substr(ignore_if_trailing: str = '', max_l_of_comma: int = 4, max_r_of_comma: int = 4):
    if ignore_if_trailing:
        ignore_if_trailing = f"(?!{ignore_if_trailing})"
    # (?:[Ww]ritten.?[Bb]y|[Pp]erformed.?[Bb]y|[Rr]ead.?[Bb]y)\W+(?P<name>(?:(?:(?<= )(?: ?[A-Z][a-z\.-]*){1,4})),? ?(?:(?: ?[A-Z][a-z\.-]*){1,4}(?!Performed by)))
    return rf"(?:(?:(?:^|(?<= ))(?: ?{_titlecase_word}){{1,{max_l_of_comma}}})),? ?(?:(?: ?{_titlecase_word}){{1,{max_r_of_comma}}}{ignore_if_trailing})"
_div = r"[-_–—.\s]*?"
wordsplit_pat = re.compile(r"[\s_.]")

author_fs_pattern = re.compile(r"^(?P<author>.*?)[\W\s]*[-_–—\(]", re.I)
author_comment_pattern = rex.compile(rf"(?:{_author_prefixes})\W+(?P<author>{_name_substr(_narrator_prefixes)})", rex.V1)
author_generic_pattern = rex.compile(rf"(?P<author>{_name_substr()})", rex.V1)
narrator_comment_pattern = rex.compile(rf"(?:{_narrator_prefixes})\W+(?P<narrator>{_name_substr(_author_prefixes)})", rex.V1)
narrator_generic_pattern = rex.compile(rf"(?P<narrator>{_name_substr()})", rex.V1)
narrator_slash_pattern = re.compile(r"(?P<author>.+)\/(?P<narrator>.+)", re.I)
narrator_in_artist_pattern = re.compile(rf"(?P<author>.*)\W+{narrator_comment_pattern}", re.I)
graphic_audio_pattern = re.compile(r"graphic\s*audio", re.I)
lastname_firstname_pattern = re.compile(r"^(?P<lastname>.*?), (?P<firstname>.*)$", re.I)
firstname_lastname_pattern = re.compile(r"^(?P<firstname>.*?).*\s(?P<lastname>\S+)$", re.I)

book_title_pattern = re.compile(r"(?<=[-_–—])[\W\s]*(?P<book_title>[\w\s]+?)\s*(?=\d{4}|\(|\[|$)", re.I)
part_number_pattern = re.compile(rf",?{_div}(?:part|ch(?:\.|apter))?{_div}\W*(\d+)(?:$|{_div}(?:of|-){_div}(\d+)\W*$)", re.I)
part_number_ignore_pattern = re.compile(r"(?:\bbook\b|\bvol(?:ume)?)\s*\d+$", re.I)
path_junk_pattern = re.compile(r"^[ \,.\)\}\]_-]*|[ \,.\)\}\]_-]*$", re.I)
path_garbage_pattern = re.compile(r"^[ \,.\)\}\]]*", re.I)
path_strip_l_t_alphanum_pattern = re.compile(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", re.I)
roman_numeral_pattern = re.compile(r"((?:^|(?<=[\W_]))[IVXLCDM]+(?:$|(?=[\W_])))", re.I)
roman_strip_pattern = re.compile(r"(?<=\w)(?=[\W_.-])|(?<=[\W_.-])(?=\w)|(?<=[a-z])(?=[A-Z])")

year_pattern = re.compile(r"(?P<year>\d{4})", re.I)

multi_disc_pattern = re.compile(r"(?:^|(?<=[\W_-]))(dis[ck]|cd)(\b|\s|[_.-])*#?(\b|\s|[_.-])*(?:\b|[\W_-])*(\d+)", re.I)
book_series_pattern = re.compile(r"(^\d+|(?:^|(?<=[\W_-]))(bo{0,2}k|vol(?:ume)?|#)(?:\b|[\W_-])*(\d+)|(?<=[\W_-])Series.*/.+)", re.I)
multi_part_pattern = re.compile(r"(?:^|(?<=[\W_-]))(pa?r?t|ch(?:\.|apter))(?:\b|[\W_-])*(\d+)", re.I)
# fmt: on


@dataclass
class romans:
    ones = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]
    tens = ["X", "XX", "XXX", "XL", "L", "LX", "LXX", "LXXX", "XC"]

    @classmethod
    def is_roman_numeral(cls, s: str) -> bool:
        """Test input against all possible valid roman numerals from 1 to 99"""
        s = str(s).upper()
        for ten in cls.tens:
            for one in cls.ones:
                if s == ten + one or s == ten or s == one:
                    return True
        return False

    @classmethod
    def find_all(cls, s: str) -> list[str]:
        """Finds all possible valid roman numerals from 1 to 99 in a string"""
        possible_matches: list[str] = roman_numeral_pattern.findall(s)
        return [p for p in possible_matches if p and cls.is_roman_numeral(p)]

    @classmethod
    def strip(cls, s: str) -> str:
        """Strips roman numerals from a string"""

        # split on word boundaries, and any boundary between lowercase/uppercase or letter/non-letter
        split = roman_strip_pattern.split(s)
        return "".join([p for p in split if not cls.is_roman_numeral(p)])


if TYPE_CHECKING:
    from src.lib.audiobook import Audiobook


def to_words(s: str) -> list[str]:
    return [w.strip() for w in re.split(r"[\s_.]", s) if w.strip()]


def swap_firstname_lastname(name: str) -> str:
    lastname = ""
    firstname = ""

    if name.count(",") > 1 or name.count(" ") == 0 or len(to_words(name)) > 4:
        # ignore false negatives
        return name

    m = lastname_firstname_pattern.match(name)

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


def contains_partno(s: str) -> bool:
    matches_part_number = part_number_pattern.search(s)
    matches_ignore_if = part_number_ignore_pattern.search(s)

    return bool(matches_part_number and not matches_ignore_if)


def strip_part_number(s: str) -> str:

    # if it matches both the part number and ignore, return original string
    if contains_partno(s):
        return part_number_pattern.sub("", s)
    else:
        return s


def extract_path_info(book: "Audiobook", quiet: bool = False) -> "Audiobook":
    # Replace single occurrences of . with spaces

    dir_author = swap_firstname_lastname(
        re_group(author_fs_pattern.search(book.basename), "author")
    )

    dir_title = re_group(book_title_pattern.search(book.basename), "book_title")
    dir_year = re_group(year_pattern.search(book.basename), "year")
    dir_narrator = parse_narrator(book.basename)

    # remove suffix/extension from files
    files = [f.stem for f in Path(book.inbox_dir).iterdir() if f.is_file()]

    # Get filename common text
    orig_file_name = find_greatest_common_string(files)

    orig_file_name = strip_part_number(orig_file_name)
    # TODO: dupe? Probably remove
    # orig_file_name = re.sub(r"(part|chapter|ch\.)\s*$", "", orig_file_name, flags=re.I)
    orig_file_name = orig_file_name.rstrip().rstrip(string.punctuation)

    # strip underscores
    orig_file_name = orig_file_name.replace("_", " ")

    # strip leading and trailing -._ spaces and punctuation
    orig_file_name = path_junk_pattern.sub("", orig_file_name)

    file_author = parse_author(orig_file_name, "fs")
    file_title = re_group(book_title_pattern.search(orig_file_name), "book_title")
    file_year = re_group(year_pattern.search(orig_file_name), "year")

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
        try:
            return path_garbage_pattern.sub(
                "", re.sub(path, "", book.basename, flags=re.I)
            )
        except re.error as e:
            print_debug(f"Error calling strip_garbage_chars: {e}")
            return path

    # everything else in the dir name after removing author, title, year, and narrator
    for f, d in zip(
        [file_author, file_title, file_year], [dir_author, dir_title, dir_year]
    ):
        book.dir_extra_junk = strip_garbage_chars(d)
        book.file_extra_junk = strip_garbage_chars(f)

    book.orig_file_name = path_strip_l_t_alphanum_pattern.sub("", orig_file_name)

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
    from src.lib.fs_utils import only_audio_files

    return get_roman_numerals_dict(*(str(f) for f in only_audio_files(d.rglob("*"))))


def count_distinct_roman_numerals(d: Path) -> int:
    """Counts the number of unique roman numerals in a directory, ignoring 'I' to avoid false positives"""
    return len([n for n in find_roman_numerals(d).keys() if n != "I"])


def strip_roman_numerals(d: Path) -> list[Path]:
    """Strips roman numerals from the filenames in a directory and returns
    a list of proposed paths, keeping the original file order"""
    return [
        f.parent / romans.strip(f.name) for f in isorted(d.rglob("*")) if f.is_file()
    ]


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


def get_name_from_str(s: str, max_words=6) -> str:
    if len(to_words(s)) > max_words:
        s = " ".join(to_words(s)[:max_words])
    if s.count(","):
        # drop the second comma and anything after it
        s = ",".join(s.split(",")[:2])
    # remove parens and anything inside them
    s = re.sub(r"\(.*?\)", "", s)
    return s.strip()


def parse_names(
    s: str, target: NameParserTarget, *, default: str | None = None
) -> AuthorNarrator:
    if default is None:
        default = s
    if not s or graphic_audio_pattern.search(s):
        return AuthorNarrator(default, default)
    author = s
    narrator = s
    if any([w for w in to_words(s)[:6] if "/" in w]):
        m = narrator_slash_pattern.search(s)
        author = re_group(m, "author")
        narrator = re_group(m, "narrator")

    match target:
        case "generic":
            author_pattern = author_generic_pattern
            narrator_pattern = narrator_generic_pattern
        case "fs":
            author_pattern = author_fs_pattern
            narrator_pattern = narrator_generic_pattern
        case "comment":
            author_pattern = author_comment_pattern
            narrator_pattern = narrator_comment_pattern

    author_default = (
        default if not re_group(narrator_pattern.search(narrator), "narrator") else ""
    )
    narrator_default = (
        default if not re_group(author_pattern.search(author), "author") else ""
    )

    author = re_group(
        author_pattern.search(author), "author", default=author_default
    ).strip()
    narrator = re_group(
        narrator_pattern.search(narrator), "narrator", default=narrator_default
    ).strip()

    if not author and not narrator:
        return AuthorNarrator(default, default)

    if author and author in narrator:
        narrator = re.sub(author, "", narrator)
    elif narrator and narrator in author:
        author = re.sub(narrator, "", author)

    author = get_name_from_str(author)
    narrator = get_name_from_str(narrator)

    return AuthorNarrator(
        author=swap_firstname_lastname(author),
        narrator=swap_firstname_lastname(narrator),
    )


def parse_author(
    s: str, target: NameParserTarget, *, default: str | None = None
) -> str:
    return parse_names(s, target, default=default).author


def has_graphic_audio(s: str) -> bool:
    return bool(graphic_audio_pattern.search(s))


def parse_narrator(
    s: str, target: NameParserTarget, *, default: str | None = None
) -> str:
    return parse_names(s, target, default=default).narrator or default or ""


def get_title_partno_score(
    title_1: str, title_2: str, album_1: str, sortalbum_1: str
) -> tuple[bool, int, bool]:
    score = 0
    t1_part = contains_partno(title_1)
    t2_part = contains_partno(title_2)
    t1 = get_numbers_in_string(title_1)
    t2 = get_numbers_in_string(title_2)
    a1 = get_numbers_in_string(album_1)
    sa1 = get_numbers_in_string(sortalbum_1)

    if len(t1) > len(a1):
        score -= 1

    if len(t1) > len(sa1):
        score -= 1

    if t1 != t2:
        score -= 1
        if t1_part:
            score -= 1
        if t2_part:
            score -= 1
    else:
        # if the numbers in both titles match, it's likely that the number is part of the book's name
        score += 1
        if not t1_part and not t2_part:
            score += 2

    contains_only_part = (
        strip_part_number(title_1) == "" and strip_part_number(title_2) == ""
    )

    return score > 0, score, contains_only_part


@cachetools.func.ttl_cache(maxsize=32, ttl=MEMO_TTL)
def is_maybe_multi_book_or_series(s: str) -> bool:
    return not is_maybe_multi_disc(s) and bool(book_series_pattern.search(s))


@cachetools.func.ttl_cache(maxsize=32, ttl=MEMO_TTL)
def is_maybe_multi_disc(s: str) -> bool:
    return bool(multi_disc_pattern.search(s))


@cachetools.func.ttl_cache(maxsize=32, ttl=MEMO_TTL)
def is_maybe_multi_part(s: str) -> bool:
    return (
        not is_maybe_multi_disc(s)
        and not is_maybe_multi_book_or_series(s)
        and bool(multi_part_pattern.search(s))
    )
