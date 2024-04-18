from collections.abc import Callable
from pathlib import Path

import pytest

from src.lib.audiobook import Audiobook
from src.lib.ffmpeg_utils import get_bitrate_py, is_variable_bitrate
from src.lib.formatters import human_bitrate
from src.lib.id3_utils import extract_id3_tags, write_id3_tags_eyed3
from src.lib.parsers import (
    extract_path_info,
    has_graphic_audio,
    parse_author,
    parse_narrator,
    romans,
)
from src.lib.typing import BadFileError
from src.tests.helpers.pytest_utils import testutils


def test_extract_path_info(benedict_society__mp3):

    assert (
        extract_path_info(benedict_society__mp3).fs_title
        == "The Mysterious Benedict Society"
    )


def test_eyed3_load_fails_for_non_audio_file(not_an_audio_file: Audiobook):

    with pytest.raises(BadFileError):
        write_id3_tags_eyed3(not_an_audio_file.sample_audio1, {})


def test_id3_extract_fails_for_corrupt_file(corrupt_audiobook: Audiobook):

    with pytest.raises(BadFileError):
        extract_id3_tags(corrupt_audiobook.sample_audio1, "title", throw=True)


@pytest.mark.parametrize(
    "test_dict, expected",
    [
        (
            {
                "comment": "Written by Sarah J. Maas - Performed by Melody Muze as Feyre, Anthony Palmini as Rhysand, Colleen Delany as Narrator; Jon Vertullo as Cassian, and Amanda Forstrom as Morrigan; with Shawn K. Jain, Nora Achrati, Karenna Foley, Gabriel Michael, Natalie Van Sistine, Eva Wilhelm, Henry W. Kramer, Bianca Bryan, Renee Dorian, Matthew Bassett, Rob McFadyen, Ryan Carlo Dalusung, Yasmin Tuazon, Matthew Schleigh, Nanette Savard, Dan Delgado, Michael John Casey, Alejandro Ruiz, and Samantha Cooper"
            },
            {
                "author": "Sarah J. Maas",
                "narrator": "Full Cast",
            },
        ),
    ],
)
def test_parse_id3_tags(test_dict: dict[str, str], expected: dict[str, str]):

    for tag, test_str in test_dict.items():
        if "narrator" in expected:
            assert parse_narrator(test_str) == expected["narrator"]
        if "author" in expected:
            assert parse_author(test_str, target="tag") == expected["author"]


def test_ignore_graphic_audio(
    graphic_audio__single_m4b: Audiobook, capfd: pytest.CaptureFixture
):

    b = graphic_audio__single_m4b
    b.extract_metadata()
    for prop in [
        "author",
        "artist",
        "albumartist",
        "narrator",
        "title",
        "album",
        "sortalbum",
        "composer",
    ]:
        assert not has_graphic_audio(getattr(b, prop))

    assert b.title == "A Court of Thorns and Roses: A Court of Frost and Starlight"
    assert b.album == b.title
    assert b.sortalbum == b.title.removeprefix("A ")
    assert b.author == "Sarah J. Maas"
    assert b.artist == b.author
    assert b.albumartist == b.author
    assert b.narrator == "Full Cast"

    assert """Sampling A Court Of Thorns And Roses [03.1] A Court Of Frost And Starlight.m4b for book metadata and quality info:
- Title: A Court of Thorns and Roses: A Court of Frost and Starlight
- Author: Sarah J. Maas
- Narrator: Full Cast
- Date: 2023
- Quality: 64 kb/s @ 44.1 kHz
- Duration: 0h:00m:33s
- No cover art""" in testutils.get_stdout(
        capfd
    )


@pytest.mark.parametrize(
    "test_dict, expected_author",
    [
        (
            {
                "comment": "Written by Sarah J. Maas - Performed by Melody Muze as Feyre, Anthony Palmini as Rhysand"
            },
            "Sarah J. Maas",
        ),
        (
            {
                "artist": "GraphicAudio LLC",
                "comment": "Written by Sarah J. Maas - Performed by Melody Muze as Feyre, Anthony Palmini as Rhysand",
            },
            "Sarah J. Maas",
        ),
        (
            {
                "artist": "Sarah J. Maas",
                "comment": "Performed by Melody Muze as Feyre, Anthony Palmini as Rhysand",
            },
            "Sarah J. Maas",
        ),
        (
            {
                "albumartist": "Sarah J. Maas",
                "comment": "Performed by Melody Muze as Feyre, Anthony Palmini as Rhysand",
            },
            "Sarah J. Maas",
        ),
        (
            {
                "artist": "Melody Muze",
                "albumartist": "Sarah J. Maas",
                "comment": "Performed by Melody Muze as Feyre, Anthony Palmini as Rhysand",
            },
            "Sarah J. Maas",
        ),
        (
            {
                "comment": "When we rescued the first fluffy-eared princess, I didn't realize how lucky we’d been. She was a kind soul, and gentle-everything you’d imagine a sweet princess to be. Though atop the second tower, the next stripey-tailed princess bore a rage as wild as the sun. Her body burned hot like a furnace. But it was our job to help her return to normal-well, not our main job. Our journey took us from cold mountains to wild seas on a pirate ship. Our quest? To save the third-and last-princess, so we could halt The Witch King in his tracks."
            },
            "",
        ),
        (
            {"artist": "Melody Muze", "albumartist": "Sarah J. Maas", "comment": ""},
            "Sarah J. Maas",
        ),
        (
            {"artist": "Sarah J. Maas", "albumartist": "Melody Muze", "comment": ""},
            "Melody Muze",
        ),
        (
            {
                "artist": "James Allen/Andrew Farell (Narrator)",
                "comment": "",
            },
            "James Allen",
        ),
    ],
)
def test_parse_id3_author(
    test_dict: dict[str, str],
    expected_author: str,
    blank_audiobook: Audiobook,
    mock_id3_tags: Callable[..., list[dict[str, str]]],
):

    _got_tags = mock_id3_tags(
        (blank_audiobook.sample_audio1, test_dict),
        (blank_audiobook.sample_audio2, test_dict),
    )

    book = Audiobook(blank_audiobook.sample_audio1).extract_metadata()
    assert book.author == expected_author


@pytest.mark.parametrize(
    "test_dict, expected_narrator",
    [
        (
            {
                "comment": "Mysterious Benedict Society#1    Read by Del Roy                           Unabridged  13 hrs 17 min           Listening Library/Random House Audio"
            },
            "Del Roy",
        ),
        ({"comment": "Read by Nicola Barber; Unabr"}, "Nicola Barber"),
        (
            {"artist": "Melody Muze", "albumartist": "Sarah J. Maas", "comment": ""},
            "Melody Muze",
        ),
        (
            {"artist": "Sarah J. Maas", "albumartist": "Melody Muze", "comment": ""},
            "Sarah J. Maas",
        ),
        (
            {
                "artist": "H. D. Carlton",
                "comment": "Death walks alongside me...but the reaper is no match for me. I'm trapped in a world full of monsters dressed as men, and those who aren't as they seem. They won't keep me forever. I no longer recognize the person I've become.",
                "composer": "Teddy Hamilton, Michelle Sparks",
            },
            "Teddy Hamilton, Michelle Sparks",
        ),
        (
            {
                "artist": "James Allen/Andrew Farell (Narrator)",
                "comment": "",
            },
            "Andrew Farell",
        ),
    ],
)
def test_parse_id3_narrator(
    test_dict: dict[str, str],
    expected_narrator: str,
    blank_audiobook: Audiobook,
    mock_id3_tags: Callable[..., list[dict[str, str]]],
):

    _got_tags = mock_id3_tags(
        (blank_audiobook.sample_audio1, test_dict),
        (blank_audiobook.sample_audio2, test_dict),
    )

    book = Audiobook(blank_audiobook.sample_audio1).extract_metadata()
    assert book.narrator == expected_narrator


def test_bitrate_vbr(bitrate_vbr__mp3: Audiobook):

    vbr_file = bitrate_vbr__mp3.sample_audio1

    std_bitrate, actual = get_bitrate_py(vbr_file)
    assert std_bitrate == 48000
    assert actual == 45567

    assert is_variable_bitrate(vbr_file)

    assert human_bitrate(vbr_file) == "~46 kb/s"


def test_bitrate_cbr(bitrate_cbr__mp3: Audiobook):

    cbr_file = bitrate_cbr__mp3.sample_audio1

    std_bitrate, actual = get_bitrate_py(cbr_file)
    assert std_bitrate == 128000
    assert actual == 128000

    assert not is_variable_bitrate(cbr_file)

    assert human_bitrate(cbr_file) == "128 kb/s"


@pytest.mark.parametrize(
    "input, expected",
    [
        ("A", {}),
        ("B", {}),
        ("8", {}),
        ("I", {"I": 1}),
        ("II", {"II": 1}),
        ("III", {"III": 1}),
        ("IV", {"IV": 1}),
        ("V", {"V": 1}),
        ("VI", {"VI": 1}),
        ("VII", {"VII": 1}),
        ("VIII", {"VIII": 1}),
        ("IX", {"IX": 1}),
        ("X", {"X": 1}),
        (["Star Wars", "Episode", "IV", "A New Hope"], {"IV": 1}),
        (["Star Wars", "Episode", "V", "The Empire Strikes Back"], {"V": 1}),
        (["Star Wars", "Episode", "VI", "Return of the Jedi"], {"VI": 1}),
        (["Star Wars", "Episode", "VII", "The Force Awakens"], {"VII": 1}),
        (["Star Wars", "Episode", "VIII", "The Last Jedi"], {"VIII": 1}),
        (["Star Wars", "Episode", "IX", "The Rise of Skywalker"], {"IX": 1}),
        (["Star Trek III: The Search for Spock"], {"III": 1}),
        (
            ["Chapter I", "Chapter II", "Chapter III", "Chapter IV"],
            {"I": 1, "II": 1, "III": 1, "IV": 1},
        ),
    ],
)
def test_get_roman_numerals_dict(input, expected):

    from src.lib.parsers import get_roman_numerals_dict

    assert get_roman_numerals_dict(input) == expected


rotk_romans = [
    "1_ Book V - Chapter 01 - Minas Tirith.mp3",
    "1_ Book V - Chapter 02 - The Passing of the Grey Company.mp3",
    "1_ Book V - Chapter 03 - The Muster of Rohan.mp3",
    "1_ Book V - Chapter 04 - The Siege of Gondor.mp3",
    "1_ Book V - Chapter 05 - The Ride of the Rohirrim.mp3",
    "1_ Book V - Chapter 06 - The Battle of Pelennor Fields.mp3",
    "1_ Book V - Chapter 07 - The Pyre of Denethor.mp3",
    "1_ Book V - Chapter 08 - The Houses of Healing.mp3",
    "1_ Book V - Chapter 09 - The Last Debate.mp3",
    "1_ Book V - Chapter 10 - The Black Gate Opens.mp3",
    "2_ Book VI - Chapter 01 - The Tower of Cirith Ungol.mp3",
    "2_ Book VI - Chapter 02 - The Land of Shadow.mp3",
    "2_ Book VI - Chapter 03 - Mount Doom.mp3",
    "2_ Book VI - Chapter 04 - The Field of Cormallen.mp3",
    "2_ Book VI - Chapter 05 - The Steward & The King.mp3",
    "2_ Book VI - Chapter 06 - Many Partings.mp3",
    "2_ Book VI - Chapter 07 - Homeward Bound.mp3",
    "2_ Book VI - Chapter 08 - The Scouring of the Shire.mp3",
    "2_ Book VI - Chapter 09 - The Grey Havens.mp3",
    "3_ Appendix A - Annals of the Kings and Rulers.mp3",
    "3_ Appendix B - The House of Eorl.mp3",
    "3_ Appendix C - Durin's Folk.mp3",
]

rotk_no_romans = [
    "1_ Book  - Chapter 01 - Minas Tirith.mp3",
    "1_ Book  - Chapter 02 - The Passing of the Grey Company.mp3",
    "1_ Book  - Chapter 03 - The Muster of Rohan.mp3",
    "1_ Book  - Chapter 04 - The Siege of Gondor.mp3",
    "1_ Book  - Chapter 05 - The Ride of the Rohirrim.mp3",
    "1_ Book  - Chapter 06 - The Battle of Pelennor Fields.mp3",
    "1_ Book  - Chapter 07 - The Pyre of Denethor.mp3",
    "1_ Book  - Chapter 08 - The Houses of Healing.mp3",
    "1_ Book  - Chapter 09 - The Last Debate.mp3",
    "1_ Book  - Chapter 10 - The Black Gate Opens.mp3",
    "2_ Book  - Chapter 01 - The Tower of Cirith Ungol.mp3",
    "2_ Book  - Chapter 02 - The Land of Shadow.mp3",
    "2_ Book  - Chapter 03 - Mount Doom.mp3",
    "2_ Book  - Chapter 04 - The Field of Cormallen.mp3",
    "2_ Book  - Chapter 05 - The Steward & The King.mp3",
    "2_ Book  - Chapter 06 - Many Partings.mp3",
    "2_ Book  - Chapter 07 - Homeward Bound.mp3",
    "2_ Book  - Chapter 08 - The Scouring of the Shire.mp3",
    "2_ Book  - Chapter 09 - The Grey Havens.mp3",
    "3_ Appendix A - Annals of the Kings and Rulers.mp3",
    "3_ Appendix B - The House of Eorl.mp3",
    "3_ Appendix C - Durin's Folk.mp3",
]

part_romans = [
    "Part I - Prologue.mp3",
    "Part II - A Long-expected Party.mp3",
    "Part III - Shadow of the Past.mp3",
    "Part IV - Riddles in the Dark.mp3",
    "Part V - The Army of Storms.mp3",
    "Part VI - Epilogue.mp3",
]

part_no_romans = [
    "Part  - Prologue.mp3",
    "Part  - A Long-expected Party.mp3",
    "Part  - Shadow of the Past.mp3",
    "Part  - Riddles in the Dark.mp3",
    "Part  - The Army of Storms.mp3",
    "Part  - Epilogue.mp3",
]


@pytest.mark.parametrize(
    "test_files, expected",
    [
        (
            rotk_romans,
            rotk_no_romans,
        ),
        (
            part_romans,
            part_no_romans,
        ),
    ],
)
def test_strip_roman_numerals(
    test_files: list[str], expected: list[str], tmp_path: Path
):

    from src.lib.parsers import strip_roman_numerals

    d = testutils.make_tmp_files(tmp_path, test_files)

    assert [f.name for f in strip_roman_numerals(d)] == expected


@pytest.mark.parametrize(
    "test_files, expected",
    [
        (
            rotk_romans,
            False,
        ),
        (
            part_romans,
            True,
        ),
    ],
)
def test_roman_numerals_affect_file_order(
    test_files: list[str], expected, tmp_path: Path
):

    from src.lib.parsers import roman_numerals_affect_file_order

    d = testutils.make_tmp_files(tmp_path, test_files)

    assert roman_numerals_affect_file_order(d) == expected


@pytest.mark.parametrize(
    "test_case, expected",
    [
        ("A", False),
        ("B", False),
        ("8", False),
        ("I", True),
        ("II", True),
        ("III", True),
        ("IV", True),
        ("V", True),
        ("VI", True),
        ("VII", True),
        ("VIII", True),
        ("IX", True),
        ("X", True),
        ("XI", True),
        ("XII", True),
        ("XIII", True),
        ("XIV", True),
        ("XV", True),
        ("XVI", True),
        ("XVII", True),
        ("XVIII", True),
        ("XIX", True),
        ("XX", True),
        ("XXI", True),
        ("XXII", True),
        ("XXIII", True),
        ("XXIV", True),
        ("XXV", True),
        ("XXVI", True),
        ("XXVII", True),
        ("XXVIII", True),
        ("XXIX", True),
        ("XXX", True),
        ("XXXI", True),
        ("XXXII", True),
        ("XXXIII", True),
        ("XXXIV", True),
        ("XXXV", True),
        ("XXXVI", True),
        ("XXXVII", True),
        ("XXXVIII", True),
        ("XXXIX", True),
        ("XL", True),
        ("XLI", True),
        ("XLII", True),
        ("XLIII", True),
        ("XLIV", True),
        ("XLV", True),
        ("XLVI", True),
        ("XLVII", True),
        ("XLVIII", True),
        ("XLIX", True),
        ("L", True),
        ("LI", True),
        ("LII", True),
        ("LIII", True),
        ("LIV", True),
        ("LV", True),
        ("LVI", True),
        ("LVII", True),
        ("LVIII", True),
        ("LIX", True),
        ("LX", True),
        ("LXI", True),
        ("LXII", True),
        ("LXIII", True),
        ("LXIV", True),
        ("LXV", True),
        ("LXVI", True),
        ("LXVII", True),
        ("LXVIII", True),
        ("LXIX", True),
        ("LXX", True),
    ],
)
def test_romans_is_roman_numeral(test_case, expected):

    assert romans.is_roman_numeral(test_case) == expected


@pytest.mark.parametrize(
    "test_case, expected",
    [
        ("A", []),
        ("B", []),
        ("8", []),
        ("I", ["I"]),
        ("II", ["II"]),
        ("Chapter III", ["III"]),
        ("Chapter IV", ["IV"]),
        ("Chapter V", ["V"]),
        ("Chapter VI", ["VI"]),
        ("Chapter VII", ["VII"]),
        ("Chapter VIII", ["VIII"]),
        ("Chapter IX", ["IX"]),
        ("Chapter X", ["X"]),
        ("Chapter XI", ["XI"]),
        ("Chapter XII", ["XII"]),
        ("Chapter XIII", ["XIII"]),
        ("Star Wars Episode IV: A New Hope", ["IV"]),
        ("Star Wars Episode V: The Empire Strikes Back", ["V"]),
        ("Star Wars Episode VI: Return of the Jedi", ["VI"]),
        ("Star Wars Episode VII: The Force Awakens", ["VII"]),
        ("Star Wars Episode VIII: The Last Jedi", ["VIII"]),
        ("Star Wars Episode IX: The Rise of Skywalker", ["IX"]),
        ("Star Trek III: The Search for Spock", ["III"]),
        ("Dune: Parts II & III - Muad'Dib & The Prophet", ["II", "III"]),
    ],
)
def test_romans_find_all(test_case, expected):

    assert romans.find_all(test_case) == expected


@pytest.mark.parametrize(
    "test_case, expected",
    [
        ("A", "A"),
        ("B", "B"),
        ("8", "8"),
        ("I", ""),
        ("II", ""),
        ("III", ""),
        ("IV", ""),
        ("V", ""),
        ("VI", ""),
        ("VII", ""),
        ("VIII", ""),
        ("IX", ""),
        ("X", ""),
        ("XI", ""),
        ("XII", ""),
        ("XIII", ""),
        ("Roman_Numeral_Book_I - Part_0", "Roman_Numeral_Book_ - Part_0"),
        ("Roman_Numeral_Book_II - Part_1", "Roman_Numeral_Book_ - Part_1"),
        ("Roman_Numeral_Book_III - Part_2", "Roman_Numeral_Book_ - Part_2"),
        ("Roman_Numeral_Book_IV - Part_3", "Roman_Numeral_Book_ - Part_3"),
        ("Star Wars Episode IV: A New Hope", "Star Wars Episode : A New Hope"),
        (
            "Star Wars Episode V: The Empire Strikes Back",
            "Star Wars Episode : The Empire Strikes Back",
        ),
        (
            "Star Wars Episode VI: Return of the Jedi",
            "Star Wars Episode : Return of the Jedi",
        ),
        (
            "Star Wars EpisodeVII: The Force Awakens",
            "Star Wars Episode: The Force Awakens",
        ),
        (
            "Star Wars EpisodeVIII: The Last Jedi",
            "Star Wars Episode: The Last Jedi",
        ),
        (
            "Star Wars Episodeix: The Rise of Skywalker",
            "Star Wars Episodeix: The Rise of Skywalker",
        ),
        ("Star.Trek.III.The.Search.for.Spock", "Star.Trek..The.Search.for.Spock"),
    ],
)
def test_romans_strip(test_case, expected):

    assert romans.strip(test_case) == expected


@pytest.mark.parametrize(
    "test_case, expected",
    [
        ("Bk1", False),
        ("Bk-1", False),
        ("Book1", False),
        ("Book-1", False),
        ("Book.1", False),
        ("Book_1", False),
        ("Book 1", False),
        ("Book 1 - The Fellowship of the Ring", False),
        ("CD1", True),
        ("CD-1", True),
        ("cd1", True),
        ("Disc-1", True),
        ("Disk.1", True),
        ("Disc_1", True),
        ("CD 1", True),
        ("Disc 1 - The Fellowship of the Ring", True),
        ("The Fellowship of the Ring - CD 1", True),
        ("Disk", False),
        ("Disc", False),
        ("CD", False),
        ("The Fellowship of the Ring", False),
        ("The Fellowship of the Ring - CD", False),
        ("The Fellowship of the Ring - Disc", False),
        ("The Fellowship of the Ring - Disc #3", True),
        ("The Fellowship of the Ring - Disc # 3", True),
        ("The Fellowship of the Ring - Disc.3", True),
        ("The Fellowship of the Ring - Disc.#3", True),
        ("#", False),
        ("#1", False),
        ("#-1", False),
        ("#1", False),
        ("#-1", False),
        ("#1", False),
        ("#1", False),
        ("# 1", False),
        ("Aleron Kong - The Land Alliances (Chaos Seeds #3)", False),
        ("# 3 (Chaos Seeds) - Aleron Kong - The Land Alliances", False),
        ("The Land Alliances (Chaos Seeds #3) - Aleron Kong", False),
        ("#The Land Alliances (Chaos Seeds)", False),
        ("The Land Alliances (Chaos Seeds) - #", False),
        ("The Land Alliances (Disc #1)", True),
    ],
)
def test_is_maybe_multi_disc(test_case, expected):

    from src.lib.parsers import is_maybe_multi_disc

    assert is_maybe_multi_disc(test_case) == expected
    assert is_maybe_multi_disc(test_case.lower()) == expected
    assert is_maybe_multi_disc(test_case.title()) == expected
    assert is_maybe_multi_disc(test_case.capitalize()) == expected
    assert is_maybe_multi_disc(test_case.upper()) == expected


@pytest.mark.parametrize(
    "test_case, expected",
    [
        ("Pt1", True),
        ("part1", True),
        ("part_1", True),
        ("Pt8", True),
        ("Pt-8", True),
        ("Part8", True),
        ("Part-8", True),
        ("Part.8", True),
        ("Part_8", True),
        ("Part 8", True),
        ("Part 8 - Quest for the Spark", True),
        ("Quest for the Spark - Pt 8", True),
        ("Part", False),
        ("Quest for the Spark", False),
        ("Quest for the Spark - Pt", False),
    ],
)
def test_is_maybe_multi_part(test_case, expected):

    from src.lib.parsers import is_maybe_multi_part

    assert is_maybe_multi_part(test_case) == expected
    assert is_maybe_multi_part(test_case.lower()) == expected
    assert is_maybe_multi_part(test_case.title()) == expected
    assert is_maybe_multi_part(test_case.capitalize()) == expected
    assert is_maybe_multi_part(test_case.upper()) == expected


@pytest.mark.parametrize(
    "test_case, expected",
    [
        ("Bk1", True),
        ("Bk-1", True),
        ("Book1", True),
        ("Book-1", True),
        ("Book.1", True),
        ("Book_1", True),
        ("Book 1", True),
        ("Book 1 - The Fellowship of the Ring", True),
        ("The Fellowship of the Ring - Bk 1", True),
        ("Book", False),
        ("The Fellowship of the Ring", False),
        ("The Fellowship of the Ring - Bk", False),
        ("#1", True),
        ("#-1", True),
        ("#1", True),
        ("#-1", True),
        ("#1", True),
        ("#1", True),
        ("# 1", True),
        ("01 - Pride Of Chanur", True),
        ("Old Man's War Series/Old Man's War - John Scalzi", True),
        ("Aleron Kong - The Land Alliances (Chaos Seeds #3)", True),
        ("# 3 (Chaos Seeds) - Aleron Kong - The Land Alliances", True),
        ("The Land Alliances (Chaos Seeds #3) - Aleron Kong", True),
        ("#", False),
        ("#The Land Alliances (Chaos Seeds)", False),
        ("The Land Alliances (Chaos Seeds) - #", False),
        ("The Land Alliances (Disc #1)", False),
    ],
)
def test_is_maybe_multi_book_or_series(test_case, expected):

    from src.lib.parsers import is_maybe_multi_book_or_series

    assert is_maybe_multi_book_or_series(test_case) == expected
    assert is_maybe_multi_book_or_series(test_case.lower()) == expected
    assert is_maybe_multi_book_or_series(test_case.title()) == expected
    assert is_maybe_multi_book_or_series(test_case.capitalize()) == expected
    assert is_maybe_multi_book_or_series(test_case.upper()) == expected
