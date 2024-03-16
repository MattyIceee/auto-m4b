import os
import shutil
import sys
from pathlib import Path

import dotenv
import pytest

from src.lib.typing import ENV_DIRS

sys.path.append(str(Path(__file__).parent.parent))

from src.lib.audiobook import Audiobook
from src.lib.misc import get_git_root, load_env

GIT_ROOT = get_git_root()
SRC_ROOT = Path(__file__).parent.parent
TESTS_ROOT = Path(__file__).parent
TESTS_TMP_ROOT = TESTS_ROOT / "tmp"
FIXTURES_ROOT = TESTS_ROOT / "fixtures"

TEST_INBOX = TESTS_TMP_ROOT / "inbox"
TEST_CONVERTED = TESTS_TMP_ROOT / "converted"
TEST_ARCHIVE = TESTS_TMP_ROOT / "archive"
TEST_FIX = TESTS_TMP_ROOT / "fix"
TEST_BACKUP = TESTS_TMP_ROOT / "backup"
TEST_WORKING = TESTS_TMP_ROOT / "working"


def make_mock_file(path: Path, size: int = 1024 * 5):
    if not path.is_absolute():
        path = TEST_INBOX / path
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write("a" * size)


def rm(p: Path):
    shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)


@pytest.fixture(autouse=True, scope="session")
def setup():
    # self.inbox_dir = Path(os.getenv("INBOX_FOLDER", "/media/Downloads/#done/#books/#convert/inbox/"))
    # self.converted_dir = Path(os.getenv("CONVERTED_FOLDER", "/media/Books/Audiobooks/_Updated plex copies/"))
    # self.archive_dir = Path(os.getenv("ARCHIVE_FOLDER", "/media/Downloads/#done/#books/#convert/processed/"))
    # self.fix_dir = Path(os.getenv("FIX_FOLDER", "/media/Downloads/#done/#books/#convert/fix/"))
    # self.backup_dir = Path(os.getenv("BACKUP_FOLDER", "/media/Downloads/#done/#books/#convert/backup/"))
    # self.build_dir = Path(os.getenv("BUILD_FOLDER", "/tmp/auto-m4b/build/"))
    # self.merge_dir = Path(os.getenv("MERGE_FOLDER", "/tmp/auto-m4b/merge/"))
    # self.trash_dir = Path(os.getenv("TRASH_FOLDER", "/tmp/auto-m4b/delete/"))
    # self.is_running_pid_file = Path("/tmp/auto-m4b/running")

    # set all ENV vars to __file__/tmp/{dirname}

    os.environ["TEST"] = "Y"
    os.environ["SLEEPTIME"] = "0.1"

    for env in get_git_root().glob(".env.local*"):
        dotenv.load_dotenv(env)

    load_env(TESTS_ROOT / ".env.test", clean_working_dirs=True)


@pytest.fixture(scope="function", autouse=True)
def clear_match_name():
    yield
    os.environ.pop("MATCH_NAME", None)


def load_test_fixture(
    name: str, *, exclusive: bool = False, override_name: str | None = None
):
    src = FIXTURES_ROOT / name
    if not src.exists():
        raise FileNotFoundError(
            f"Fixture {name} not found. Does it exist in {FIXTURES_ROOT}?"
        )
    dst = TEST_INBOX / (override_name or name)
    dst.mkdir(parents=True, exist_ok=True)

    for f in src.glob("**/*"):
        dst_f = dst / f.relative_to(src)
        if f.is_file() and not dst_f.exists():
            shutil.copy(f, dst_f)

    if exclusive:
        os.environ["MATCH_NAME"] = name

    converted_dir = TEST_CONVERTED / (override_name or name)
    shutil.rmtree(converted_dir, ignore_errors=True)

    return Audiobook(dst)


@pytest.fixture(scope="function")
def tower_treasure__flat_mp3():
    return load_test_fixture("tower_treasure__flat_mp3", exclusive=True)


@pytest.fixture(scope="function")
def house_on_the_cliff__flat_mp3():
    return load_test_fixture("house_on_the_cliff__flat_mp3", exclusive=True)


@pytest.fixture(scope="function")
def tower_treasure__multidisc_mp3():
    return load_test_fixture("tower_treasure__multidisc_mp3", exclusive=True)


@pytest.fixture(scope="function")
def tower_treasure__nested_mp3():
    return load_test_fixture("tower_treasure__nested_mp3", exclusive=True)


@pytest.fixture(scope="function")
def tower_treasure__all():
    return [
        load_test_fixture("tower_treasure__flat_mp3"),
        load_test_fixture("tower_treasure__multidisc_mp3"),
        load_test_fixture("tower_treasure__nested_mp3"),
    ]


@pytest.fixture(scope="function")
def hardy_boys__flat_mp3():
    return [
        load_test_fixture("tower_treasure__flat_mp3"),
        load_test_fixture("house_on_the_cliff__flat_mp3"),
    ]


@pytest.fixture(scope="function")
def the_crusades_through_arab_eyes__flat_mp3():
    return load_test_fixture("the_crusades_through_arab_eyes__flat_mp3", exclusive=True)


@pytest.fixture(scope="function")
def the_sunlit_man__flat_mp3():
    return load_test_fixture("the_sunlit_man__flat_mp3", exclusive=True)


@pytest.fixture(scope="function")
def conspiracy_theories__flat_mp3():
    return load_test_fixture(
        "conspiracy_theories__flat_mp3",
        exclusive=True,
        override_name="The Great Courses - Conspiracies & Conspiracy Theories What We Should and Shouldn't Believe - and Why",
    )


@pytest.fixture(scope="function", autouse=False)
def benedict_society__mp3():

    dir_name = TEST_INBOX / "01 - The Mysterious Benedict Society"

    def _path(i: int) -> Path:
        return (
            dir_name
            / f"Trenton_Lee_Stewart_-_MBS1_-_The_Mysterious_Benedict_Society_({i:02}of11).mp3"
        )

    for i in range(1, 12):
        make_mock_file(_path(i))

    os.environ["MATCH_NAME"] = "Benedict"

    yield Audiobook(dir_name)

    os.environ.pop("MATCH_NAME", None)

    shutil.rmtree(dir_name, ignore_errors=True)


@pytest.fixture(scope="function", autouse=False)
def roman_numeral__mp3():
    dir_name = TEST_INBOX / "Roman Numeral Book"

    def _path(i: int, n: str) -> Path:
        return dir_name / f"Roman_Numeral_Book_{n} - Part_{i}.mp3"

    for i, n in enumerate(
        ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
    ):
        make_mock_file(_path(i, n))

    os.environ["MATCH_NAME"] = "Roman Numeral Book"

    yield Audiobook(dir_name)

    os.environ.pop("MATCH_NAME", None)

    shutil.rmtree(dir_name, ignore_errors=True)


@pytest.fixture(scope="function", autouse=False)
def blank_audiobook():
    """Create a fake mp3 audiobook with one completely valid audiofile that plays a tone A4 for 2 seconds."""
    book = TEST_INBOX / "blank_audiobook"
    book.mkdir(parents=True, exist_ok=True)

    # write a completely valid audiofile that plays a tone A4 for 2 seconds
    with open(book / f"blank_audiobook.mp3", "wb") as f:
        f.write(
            b'ID3\x03\x00\x00\x00\x00\x00mTXXX\x00\x00\x00 \x00\x00\x00Encoded by\x00LAME in FL Studio 20TXXX\x00\x00\x00\x1b\x00\x00\x00BPM (beats per minute)\x00120TYER\x00\x00\x00\x05\x00\x00\x002018TDRC\x00\x00\x00\x05\x00\x00\x002018\xff\xfb\x90d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00Xing\x00\x00\x00\x0f\x00\x00\x06J\x00\x0b1V\x00\x03\x05\x07\t\n\x0c\x0e\x10\x12\x13\x16\x18\x1a\x1b\x1d\x1f!#$\'),.1369;=@CEGJMORTWY\\^`cegjlnqsuxz}\x7f\x81\x85\x89\x8c\x8f\x91\x94\x97\x9a\x9d\xa0\xa4\xa7\xaa\xad\xb0\xb3\xb6\xb9\xbb\xbf\xc3\xc5\xc8\xcb\xce\xd0\xd3\xd5\xd8\xdc\xdf\xe2\xe5\xe7\xea\xed\xef\xf2\xf5\xf9\xfc\xfe\x00\x00\x00PLAME3.100\x04\xb9\x00\x00\x00\x00\x00\x00\x00\x005 $\x06(M\x00\x01\xe0\x00\x0b1V\xa5v\x7fh\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xfb\xa0D\x00\x030\x00\x00\x7f\x80\x00\x00\x08\x00\x00\x0f\xf0\x00\x00\x01\x01\x18\x03\x11\x14\x10\x00(#\x00b"\x82\x00\x05DH\x00\x0e\x0f~\x07\xe0!\x11 \x008=\xf8\x1f\x80\x85\x00\x00\x00#\x948b\x85H\xd7\xd8\x1b\x05\x02@\x00\x02\x15f\x1b rc\xce\xfb&\xf6b\xd2`\x86i\xe6\x1dB\xbca\x04\x0b\xc9\x14`\n\x1b\xe6\x02\xa0``\x12\x04\xbb0 \x02`0\x1a\x11\x04\x99\x81p+\xbd\x10X\x88#IcNb%\xe2<:\x02\x00\x10j,`"[\xa6oC\x8f\x04\x84BAe\x15\xe1\x88\x99n\x98\x98 ]\xe3\x87\x0b\xb8[E\xe8\x8a\x89\x10\x8fM,\x10\x1b\x02|w\xcf\xfe\xc0\x8b\xb1\x96H\x19c\xb8\xa01(%\x86\xd6\x8e\xff\xff\xff\xe1\x18\xb1\xc9e\x8e;9L\xc6{3\x19\xff\xff\xff\xfc9\xf8s\xf0\xff\xfa\xb4\xbfV\xcf\xd5\xc7\xcaN"\xe2\xae\r.w\xff\xe8\xb5\x1e\x01\x80\x1aaj\x00\xa0\x0e\x03`\x00\x00\x00\x00\x00\x0e,\x0f p\x02 \t\x06`j\x0f\x8d\xcd\xe1\xf1\xbauK\x86\xb57\x96C\xfc\xeb\x11H\x00\x0b\xf4\x9f\x7f\xac\x00\x000Y\x181\x06\xd9\x87\x90t\x1c2\x10)\x80\xa0\x03\x18"\x03\x19\x81\xd0\x07\x97D.\x01HB`\x02\x00\x00\x90\x00\x1e\x00o\xe7\xeb{k\xb0\xad+6/E:\x8fZ\xc9\x12\x0c\x89G)\x0c\xbcZ\xc7\x07\x96\xf4s`\x03\xe8\x00\x01\xff\x00\x00,\xc0NXL\xd9\xd3Z\xec3<\xdf\xff\x8f4r"`\xa2G\x1f\x14\x10\x83\x04\x95\x00\x05\xbd\xb3_\xf0\x00\x00`\x8cs\x0ea\x02\x0b\x87&$.a\xde\x01A\xc0\xc2D\x02\xca\xd0\x8el\xac\x80\x00\x99\x8c\xd7;N\xef]\t\xda\xbcM\xc2:\x07\xc6j\xf0\x9c}\xdf\x80\x04C\x80\x00\x00\x01\xc0\x00\x00\x85-\t\xd0N\xd4\xa2\x08M\xd6A\xff\xffJ_*\x00\x04\xed\x08\xa8\xfb\xfa\x0c\n\x804\xc0\\\n\x0c\x19\x04$\xde\x01Q\x0e\xf9\x04\xc8\xc2\x0cX\x14\xbaCE#\xa0\x05\xfdX\xcc\xb6\xe7\xd3\xb6\xbc\xb6\x0e\xd5\x19\x90\xd6K\x19\xef69\xd5\xf5\xff\xfb\x80d\xea\x00\x05\xab:\xcc~{$\x80+@\xe9\xff\xcc\x80\x12\t8])\xbd\xe1\x00 \x83\x82\xa57\xb2\x00\x04\x82o\xc0\x03\xc0\x19\xc1\xd8\x12SD>.\x00\x03D\x87\x85{\xf8\x00\x00\x00\x00,`\x10\t\xe6\x07#4h\xf2\xfdg\xcfA\x8c*`Q\x15\x05\x88\x80/\xc5jsZt\xb2\xec\x0fOa\xe9eF\xe4M\'\xcda\x81h\xc5\x87\xe5\xf9\x87\xb1T\xe8\xa6\x06\xd8\xc5`\x00\xe0\xa8\xf3pR\xc4\x92\xb2\x83\xf6Fo<\xfcW\x90\x08\x11\xaaffb\x02\xa0 R\r\x80\xaa\x0e\xcb\x01\x03!\n\x15LF\xd24\xff1\xd8V\x94\xd0\xe4N\xb2_k\xc0Q,\xab\xa5\x08y\xaa\x89\xa9\x91\x18\x1eb\xe2\x8d`\xbf%\xde\x90\x17\x8d\x10Q\xa1\x9b\xb5\xd67,\xaa}E\xde!$#\xd1\xc0@\xee*C\xddl\x9a\x8e\x807\xd5I\xca\x8e\'\x01\x97m\xa3(8\xf3\x16 \xae\x1e\xaa6\x9fhl>\x99\x8d\x1e7\x1b\xce\xa1F\xb2\x1aI\x93\x88\xf3\xd8\xe2\x95Q"Q~\x82\xa7\xc1\xec\xf1\xcb\x85Aq!\xc1\x1d\xe9\\\xea\t\xca\x08\x83\xdfo\xb7\xc5I\xa1\xc0\x84\xe3\xdd"<2\xba\xd9h\x11\x19\xa2t\x06\x06z\x85_V\xf4\xdd\xb3\x07]\x0b$=\xb7K\x01\xc480bP\xa1\x93<u\xc2J\x0c$\xb2M\xeb`Z\xff\xfbPD\xf2\x83\x11\x8c\x10J\xfb\tc\x081\xa1\xe9_c\t\'\x05h?+\xcc1\xea\xa8\xc8\x08\xe5}\x87\xa5\x15\x9fDY\x10\xa1\x97\x86L\x12D\x98\x04(\xb0$\xa0\xec\x91\x00\xa6D\xa1+\x12\xdc\x86\x1c\xef\xad\x1a \x00\x00\x1e\x16\xe6\x15\x80m`&\x11\x98\x19\x96\x99\xa8\xe8\x8e\xb2\xbc\x93\x00\x00\x01q\x07\x08\n\x98\n\xde\xb2\xda@\x0b\x03!\x0b\x07\x81\xacELAME3.100UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUULAME3.100UUUUUUUUUUUUUUUUUUUUUU\xff\xfbPD\xe8\x031]\x0eK{\x0f1\xaa/"\t_a\xecCD\xe89+\xcc=eh\x96\x87%\xf9\x84\xa1\x8dUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU\xff\xfbPd\xea\x031-\x0fG#Xx8\x1e\xa1\xb8\xd4d#c\x04(7"\x8c1&\xa8v\x06\xa3\x91\x97\x8c\x9cUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU\xff\xfb\x10D\xfe\x030\xa6\x07F#\x0f@\x98\x16\xe0\xf8xb\x0c\x01\x01x\r\r\x0c0@ &\x01"\x94\xc4\x80\x06UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU\xff\xfb\x10d\xdd\x8f\xf0\x00\x00\x7f\x80\x00\x00\x08\x00\x00\x0f\xf0\x00\x00\x01\x00\x00\x01\xa4\x00\x00\x00 \x00\x004\x80\x00\x00\x04UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU'
        )

    yield Audiobook(book)
    shutil.rmtree(book, ignore_errors=True)
    shutil.rmtree(TEST_WORKING / "build" / "blank_audiobook", ignore_errors=True)
    shutil.rmtree(TEST_WORKING / "fix" / "blank_audiobook", ignore_errors=True)
    shutil.rmtree(TEST_WORKING / "merge" / "blank_audiobook", ignore_errors=True)


@pytest.fixture(scope="function", autouse=False)
def corrupt_audiobook():
    """Create a fake mp3 audiobook with a corrupt file."""
    book = TEST_INBOX / "corrupt_audiobook"
    book.mkdir(parents=True, exist_ok=True)
    with open(book / f"corrupt_audiobook.mp3", "wb") as f:
        f.write(b"\xff\xfb\xd6\x04")
        # write 20kb of random data, but the first 4 bytes are corrupt
        f.write(os.urandom(1024 * 20))
    yield Audiobook(book)
    shutil.rmtree(book, ignore_errors=True)
    shutil.rmtree(TEST_WORKING / "build" / "corrupt_audiobook", ignore_errors=True)
    shutil.rmtree(TEST_WORKING / "fix" / "corrupt_audiobook", ignore_errors=True)
    shutil.rmtree(TEST_WORKING / "merge" / "corrupt_audiobook", ignore_errors=True)


@pytest.fixture(scope="function", autouse=False)
def not_an_audio_file():
    """Create a fake mp3 audiobook with a corrupt file."""
    book = TEST_INBOX / "not_an_audio_file"
    book.mkdir(parents=True, exist_ok=True)
    with open(book / f"not_an_audio_file.mp3", "w") as f:
        f.write("This is not an audio file")
        f.write("a" * 1024 * 5)
    yield Audiobook(book)
    shutil.rmtree(book, ignore_errors=True)
    shutil.rmtree(TEST_WORKING / "build" / "not_an_audio_file", ignore_errors=True)
    shutil.rmtree(TEST_WORKING / "fix" / "not_an_audio_file", ignore_errors=True)
    shutil.rmtree(TEST_WORKING / "merge" / "not_an_audio_file", ignore_errors=True)


def purge_all():
    for folder in ENV_DIRS:
        if folder := os.getenv(folder):
            shutil.rmtree(folder, ignore_errors=True)


@pytest.fixture(scope="function", autouse=False)
def cleanup():
    yield
    purge_all()


@pytest.fixture(scope="function", autouse=False)
def mock_inbox(setup):
    """Populate INBOX_FOLDER with mocked sample audiobooks."""

    backup_inbox = Path(f"{TEST_INBOX}_backup")
    # if inbox exists, move it to a backup folder
    if TEST_INBOX.exists():
        shutil.rmtree(backup_inbox, ignore_errors=True)
        shutil.move(TEST_INBOX, backup_inbox)

    TEST_INBOX.mkdir(parents=True, exist_ok=True)

    # make 4 sample audiobooks using nealy empty txt files (~5kb) as pretend mp3 files.
    for i in range(1, 5):
        book = TEST_INBOX / f"mock_book_{i}"
        book.mkdir(parents=True, exist_ok=True)
        for j in range(1, 4):
            make_mock_file(book / f"mock_book_{i} - part_{j}.mp3")

    # make a book with a single nested folder
    nested = TEST_INBOX / "mock_book_nested" / "inner_dir"
    nested.mkdir(parents=True, exist_ok=True)
    for i in range(1, 4):
        make_mock_file(nested / f"mock_book_nested - part_{i}.mp3")

    # make a multi-disc book
    multi_disc = TEST_INBOX / "mock_book_multi_disc"
    multi_disc.mkdir(parents=True, exist_ok=True)
    for d in range(1, 5):
        disc = multi_disc / f"Disc {d} of 4"
        disc.mkdir(parents=True, exist_ok=True)
        for i in range(1, 3):
            make_mock_file(disc / f"mock_book_multi_disc - part_{i}.mp3")

    # make a multi-series directory
    multi_series = TEST_INBOX / "mock_book_multi_series"
    multi_series.mkdir(parents=True, exist_ok=True)
    for s in ["A", "B", "C"]:
        series = multi_series / f"Series {s}"
        series.mkdir(parents=True, exist_ok=True)
        for i in range(1, 3):
            make_mock_file(series / f"mock_book_multi_series - part_{i}.mp3")

    # make 2 top-level mp3 files
    for t in ["a", "b"]:
        make_mock_file(TEST_INBOX / f"mock_book_standalone_file_{t}.mp3")

    yield TEST_INBOX

    # restore contents of inbox if it was moved to a backup folder
    if backup_inbox.exists():
        for f in backup_inbox.glob("*"):
            # if dst exists, remove src instead
            if (TEST_INBOX / f.name).exists():
                rm(f)
            else:
                shutil.move(f, TEST_INBOX)
        shutil.rmtree(backup_inbox, ignore_errors=True)

    # remove everything in the inbox that starts with `mock_book_`
    for f in TEST_INBOX.glob("mock_book_*"):
        rm(f)


@pytest.fixture(scope="function", autouse=False)
def global_test_log():
    orig_log = FIXTURES_ROOT / "sample-auto-m4b.log"
    test_log = TEST_CONVERTED / "auto-m4b.log"
    test_log.unlink(missing_ok=True)
    shutil.copy2(orig_log, test_log)
    yield test_log
    test_log.unlink(missing_ok=True)
