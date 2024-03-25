import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from tinta import Tinta

from src.lib.audiobook import Audiobook
from src.lib.config import AUDIO_EXTS, cfg
from src.lib.ffmpeg_utils import build_id3_tags_args
from src.lib.formatters import friendly_date, human_elapsed_time, log_date, pluralize
from src.lib.fs_utils import *
from src.lib.id3_utils import verify_and_update_id3_tags
from src.lib.logger import log_global_results
from src.lib.misc import BOOK_ASCII, dockerize_volume, re_group
from src.lib.parsers import (
    count_distinct_roman_numerals,
    roman_numerals_affect_file_order,
)
from src.lib.strings import MULTI_ERR, ROMAN_ERR
from src.lib.term import (
    AMBER_COLOR,
    border,
    divider,
    fmt_linebreak_path,
    nl,
    print_aqua,
    print_dark_grey,
    print_debug,
    print_error,
    print_grey,
    print_list,
    print_notice,
    print_orange,
    print_warning,
    smart_print,
    tint_light_grey,
    tint_path,
    tint_warning,
    tinted_file,
    tinted_m4b,
    vline,
)
from src.lib.typing import BookHashesDict, FailedBooksDict

FAILED_BOOKS: FailedBooksDict = {}
INBOX_HASH: str = ""
INBOX_BOOK_HASHES: BookHashesDict = {}
LAST_UPDATED: float = 0
if os.getenv("FAILED_BOOKS"):
    FAILED_BOOKS = {
        k: float(v) for k, v in json.loads(os.getenv("FAILED_BOOKS", "{}")).items()
    }


def flush_inbox_hash():
    global INBOX_HASH
    INBOX_HASH = ""


def print_launch_and_set_running():
    if cfg.SLEEPTIME and not cfg.TEST:
        time.sleep(min(2, cfg.SLEEPTIME / 2))
    if not cfg.PID_FILE.is_file():
        cfg.PID_FILE.touch()
        current_local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with cfg.PID_FILE.open("a") as f:
            f.write(
                f"auto-m4b started at {current_local_time}, watching {cfg.inbox_dir}\n"
            )
        print_aqua("\nStarting auto-m4b...")
        print_grey(f"{cfg.info_str}\n")


def process_standalone_files():
    """Move single audio files into their own folders"""

    # get all standalone audio files in inbox - i.e., audio files that are directl in the inbox not a subfolder
    standalone_audio_files = [
        file
        for ext in AUDIO_EXTS
        for file in cfg.inbox_dir.glob(f"*{ext}")
        if len(file.parts) == 1
    ]
    for audio_file in standalone_audio_files:
        # Extract base name without extension
        file_name = audio_file.name
        folder_name = audio_file.stem
        ext = audio_file.suffix

        # If the file is an m4b, we can send it straight to the output folder.
        # if a file of the same name exists, rename the incoming file to prevent data loss using (copy), (copy 1), (copy 2) etc.
        if ext == ".m4b":
            unique_target = cfg.converted_dir / file_name
            smart_print("This book is already an m4b")
            smart_print(f"Moving directly to converted books folder → {unique_target}")

            if unique_target.exists():
                smart_print(
                    "(A file with the same name already exists in the output dir, this one will be renamed to prevent data loss)"
                )

                # using a loop, first try to rename the file to append (copy) to the end of the file name.
                # if that fails, try (copy 1), (copy 2) etc. until it succeeds
                i = 0
                # first try to rename to (copy)
                unique_target = cfg.converted_dir / f"{folder_name} (copy){ext}"
                while unique_target.exists():
                    i += 1
                    unique_target = cfg.converted_dir / f"{folder_name} (copy {i}){ext}"

            shutil.move(str(audio_file), str(unique_target))

            if unique_target.exists():
                smart_print(f"Successfully moved to {unique_target}")
        else:
            smart_print(f"Moving book into its own folder → {folder_name}/")
            new_folder = cfg.inbox_dir / folder_name
            new_folder.mkdir(exist_ok=True)
            shutil.move(str(audio_file), str(new_folder))


class m4btool:
    _cmd: list[Any]

    def __init__(self, book: Audiobook):
        def _(*new_arg: str | tuple[str, Any]):
            if isinstance(new_arg, tuple):
                self._cmd.extend(new_arg)
            else:
                self._cmd.append(new_arg)

        self.book = book
        self._cmd = cfg._m4b_tool + [
            "merge",
            dockerize_volume(book.merge_dir),
            "-n",
        ]

        _("--debug" if cfg.DEBUG == "Y" else "-q")

        if self.should_copy:
            _(("--audio-codec", "copy"))
        else:
            _((f"--audio-codec", "libfdk_aac"))
            _((f"--audio-bitrate", book.bitrate_target))
            _((f"--audio-samplerate", book.samplerate))

        _(("--jobs", cfg.CPU_CORES))
        _(("--output-file", dockerize_volume(book.build_file)))
        _(("--logfile", dockerize_volume(book.log_file)))
        _("--no-chapter-reindexing")

        if cfg.SKIP_COVERS:
            _("--no-cover-image")
        elif not book.has_id3_cover and book.cover_art:
            _(("--cover", dockerize_volume(book.cover_art)))

        if cfg.USE_FILENAMES_AS_CHAPTERS:
            _("--use-filenames-as-chapters")

        if chapters_files := list(
            dockerize_volume(self.book.merge_dir).glob("*chapters.txt")
        ):
            chapters_file = chapters_files[0]
            _(f'--chapters-file="{chapters_file}"')
            smart_print(
                f"Found {len(chapters_files)} chapters {pluralize(len(chapters_files), 'file')}, setting chapters from {tinted_file(chapters_file.name)}"
            )

        _(*build_id3_tags_args(book.title, book.author, book.year, book.comment))

    def cmd(self, quotify: bool = False) -> list[str]:
        out = []
        for arg in self._cmd:
            if isinstance(arg, tuple):
                k, v = arg
                if quotify and " " in str(v):
                    v = f'"{v}"'
                out.append(f"{k}={v}")
            else:
                out.append(str(arg))
        return out

    def esc_cmd(self) -> str:
        cmd = self.cmd(quotify=True)
        if cfg.USE_DOCKER:
            cmd.insert(2, "-it")
        cmd = [c for c in cmd if c != "-q"]
        return " ".join(cmd)

    @property
    def should_copy(self):
        return self.book.orig_file_type in ["m4a", "m4b"]

    def msg(self):
        starttime_friendly = friendly_date()
        if self.should_copy:
            smart_print(
                f"Starting merge/passthrough → {tinted_m4b()} at {tint_light_grey(starttime_friendly)}..."
            )
        else:
            smart_print(
                f"Starting {tinted_file(self.book.orig_file_type)} → {tinted_m4b()} conversion at {tint_light_grey(starttime_friendly)}..."
            )


# glasses 1: ⌐◒-◒
# glasses 2: ᒡ◯ᴖ◯ᒢ


def banner(verb: str = "Checking"):
    global INBOX_HASH
    if hash_inbox() == INBOX_HASH:
        return

    if not INBOX_HASH:
        verb = "Watching"
    else:
        verb = "Checking"

    current_local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    dash = "-" * 24

    print_aqua(f"{dash}  ⌐◒-◒  auto-m4b • {current_local_time}  -{dash}")

    print_grey(f"{verb} for new books in {{{{{cfg.inbox_dir}}}}} ꨄ︎")

    if not INBOX_HASH:
        print_debug(f"First run, banner should say 'watching'")
        nl()


def fail_book(book: Audiobook):
    """Adds the book's path to the failed books dict with a value of the last modified date of of the book"""
    global FAILED_BOOKS
    if book.basename in FAILED_BOOKS:
        return
    FAILED_BOOKS[book.basename] = book.last_updated_at()


def unfail_book(book: Audiobook | str, updated_broken_books: list[str] = []):
    """Removes the book's path from the failed books dict"""
    global FAILED_BOOKS
    book_name = book.basename if isinstance(book, Audiobook) else book
    if book_name in FAILED_BOOKS:
        FAILED_BOOKS.pop(book_name)
        os.environ["FAILED_BOOKS"] = json.dumps(FAILED_BOOKS)

        if not book_name in updated_broken_books:
            updated_broken_books.append(book_name)

    return updated_broken_books


def do_backup(book: Audiobook):
    # Copy files to backup destination
    if not cfg.MAKE_BACKUP:
        print_dark_grey("Not backing up (backups are disabled)")
    elif dir_is_empty_ignoring_hidden_files(book.inbox_dir):
        print_dark_grey("Skipping backup (folder is empty)")
    else:
        smart_print(f"Making a backup copy → {tint_path(book.backup_dir)}")
        cp_dir(book.inbox_dir, cfg.backup_dir, overwrite_mode="skip-silent")

        # Check that files count and folder size match
        orig_files_count = book.num_files("inbox")
        orig_size_b = book.size("inbox", "bytes")
        orig_size_human = book.size("inbox", "human")
        orig_plural = pluralize(orig_files_count, "file")

        backup_files_count = book.num_files("backup")
        backup_size_b = book.size("backup", "bytes")
        backup_size_human = book.size("backup", "human")
        backup_plural = pluralize(backup_files_count, "file")

        file_count_matches = orig_files_count == backup_files_count
        size_matches = orig_size_b == backup_size_b
        size_fuzzy_matches = abs(orig_size_b - backup_size_b) < 1000

        expected = f"{orig_files_count} {orig_plural} ({orig_size_human})"
        found = f"{backup_files_count} {backup_plural} ({backup_size_human})"

        if file_count_matches and size_matches:
            print_grey(
                f"Backup successful - {backup_files_count} {orig_plural} ({backup_size_human})"
            )
        elif orig_files_count < backup_files_count or orig_size_b < backup_size_b:
            print_grey(
                f"Backup successful, but extra data found in backup dir - expected {expected}, found {found}"
            )
            print_grey("Assuming this is a previous backup and continuing")
        elif file_count_matches and size_fuzzy_matches:
            print_grey(
                f"Backup successful, but sizes aren't exactly the same - expected {expected}, found {found}"
            )
            print_grey("Assuming this is a previous backup and continuing")
        else:
            # for each audio file in left, find it in right, and compare size of each.
            # if the size is the same, remove it from the list of files to check.
            left_right_files = compare_dirs_by_files(book.inbox_dir, book.backup_dir)
            # if None in the 3rd column of left_right_files, a file is missing from the backup
            missing_files = [f for f in left_right_files if f[2] is None]
            if missing_files:
                print_error(
                    f"Backup failed - {len(missing_files)} {pluralize(len(missing_files), 'file')} missing from backup"
                )
                smart_print("Skipping this book\n")
                return False
            # compare the size of each file in the list of files to check
            for left, l_size, _, r_size in left_right_files:
                if l_size != r_size:
                    l_human_size = human_size(l_size)
                    r_human_size = human_size(r_size)
                    print_error(
                        f"Backup failed - size mismatch for {left} - original is {l_human_size}, but backup is {r_human_size}"
                    )
                    smart_print("Skipping this book\n")
                    return False
            if expected != found:
                print_error(f"Backup failed - expected {expected}, found {found}")
                smart_print("Skipping this book\n")
                return False

    return True


def process_inbox(first_run: bool = False):
    global FAILED_BOOKS, INBOX_HASH, INBOX_BOOK_HASHES, LAST_UPDATED

    audiobooks_count = count_audio_files_in_inbox()
    # compare last_touched to inbox dir's mtime - if inbox dir has not been modified since last run, skip
    # recently_updated= find_recently_modified_files_and_dirs(cfg.inbox_dir, 10, only_file_exts=cfg.AUDIO_EXTS)
    if audiobooks_count == 0:
        if first_run:
            banner()
        print_debug(
            f"No audio files found in {cfg.inbox_dir}, last updated at {inbox_last_updated_at()}, next check in {cfg.sleeptime_friendly}"
        )
        return

    banner()

    waited_while_copying = 0
    while inbox_was_recently_modified():
        if (INBOX_HASH != hash_inbox()) and not waited_while_copying:
            print_notice(
                "The inbox folder was recently modified, waiting in case files are still being copied or moved...\n"
            )
            print_debug(f"Hashes: last {INBOX_HASH} / curr {hash_inbox()}")
        waited_while_copying += 1
        time.sleep(0.5)

    if waited_while_copying:
        print_debug("Done waiting for inbox to be modified")

    if hash_inbox() == INBOX_HASH:
        if inbox_last_updated_at() != LAST_UPDATED:
            print_debug(
                f"Skipping this loop, inbox hash is the same (was last touched {friendly_date(inbox_last_updated_at())})"
            )
            LAST_UPDATED = inbox_last_updated_at()
        return

    print_debug(f"Last updated: {friendly_date(inbox_last_updated_at(), ms=True)}")

    standalone_count = count_standalone_books_in_inbox()
    if standalone_count:
        process_standalone_files()

    # Find directories containing audio files, handling single quote if present
    audio_dirs = find_book_dirs_in_inbox()

    total_books_count = len(audio_dirs)
    failed_books_count = len(FAILED_BOOKS)
    filtered_books_count = 0
    books_count = total_books_count

    if cfg.MATCH_NAME:
        audio_dirs = [
            d
            for d in audio_dirs
            if name_matches(d.relative_to(cfg.inbox_dir), cfg.MATCH_NAME)
        ]
        books_count = len(audio_dirs)
        filtered_books_count = total_books_count - books_count

    updated_broken_books: list[str] = []

    if FAILED_BOOKS:
        print_debug(f"Found failed books: {[k for k in FAILED_BOOKS.keys()]}")
        for book_name, last_modified in FAILED_BOOKS.copy().items():
            # ensure last_modified is a float
            last_modified = float(last_modified)
            was_modified = (
                last_updated_at(
                    cfg.inbox_dir / book_name, only_file_exts=cfg.AUDIO_EXTS
                )
                > last_modified
            )
            hash_changed = hash_dir_audio_files(
                cfg.inbox_dir / book_name
            ) != INBOX_BOOK_HASHES.get(book_name, None)
            if was_modified:
                print_debug(
                    f"Book has been modified since it failed last, checking if hash has changed"
                )
            if hash_changed:
                print_debug(
                    f"Book hash changed since it failed last, removing it from failed books\n        was {INBOX_BOOK_HASHES.get(book_name)}\n        now {hash_dir_audio_files(cfg.inbox_dir / book_name)}"
                )
                updated_broken_books = unfail_book(book_name, updated_broken_books)
            else:
                print_debug(f"Book hash is the same, keeping it in failed books")
        audio_dirs = [d for d in audio_dirs if d.name not in FAILED_BOOKS.keys()]
        # books_count = len(audio_dirs) # disabling for now, better to have the total count and display skip count
        failed_books_count = len(FAILED_BOOKS)

    INBOX_HASH = hash_inbox()
    INBOX_BOOK_HASHES = hash_inbox_books(audio_dirs)

    # If no books to convert, print, sleep, and exit
    if total_books_count == 0:  # replace 'books_count' with your variable
        smart_print(f"No books to convert, next check in {cfg.sleeptime_friendly}\n")
        return
    elif books_count == 0:
        if cfg.MATCH_NAME and filtered_books_count:
            smart_print(
                f"Found {filtered_books_count} {pluralize(filtered_books_count, 'book')} in the inbox, but none match [[{cfg.MATCH_NAME}]]",
                highlight_color=AMBER_COLOR,
            )
        elif failed_books_count:
            smart_print(
                f"Found {failed_books_count} {pluralize(failed_books_count, 'book')} in the inbox that failed to convert - waiting for them to be fixed",
                highlight_color=AMBER_COLOR,
            )
        return

    elif books_count != total_books_count:
        skipping = (
            f"skipping {failed_books_count} that previously failed"
            if failed_books_count
            else ""
        )
        if cfg.MATCH_NAME and filtered_books_count:
            skipping = f", {skipping}" if skipping else ""
            smart_print(
                f"Found {books_count} {pluralize(books_count, 'book')} in the inbox matching [[{cfg.MATCH_NAME}]] ({total_books_count} total{skipping})\n",
                highlight_color=AMBER_COLOR,
            )
        elif failed_books_count:
            smart_print(
                f"Found {books_count} {pluralize(books_count, 'book')} to convert ({skipping})\n",
                highlight_color=AMBER_COLOR,
            )
    else:
        smart_print(
            f"Found {books_count} {pluralize(books_count, 'book')} to convert\n"
        )

    for b, book_full_path in enumerate(audio_dirs):
        book = Audiobook(book_full_path)
        m4b_count = count_audio_files_in_dir(book.inbox_dir, only_file_exts=["m4b"])

        border(len(book.basename))
        smart_print(
            Tinta().dark_grey(vline).aqua(book.basename).dark_grey(vline).to_str()
        )
        border(len(book.basename))

        roman_numerals_count = count_distinct_roman_numerals(book.inbox_dir)

        # check if the current dir was modified in the last 1m and skip if so
        if was_recently_modified(book.inbox_dir):
            print_notice(
                "Skipping this book, it was recently updated and may still be copying"
            )
            continue

        if book.basename in updated_broken_books:
            nl()
            smart_print(
                f"This book previously failed, but it has been updated – trying again"
            )

        # can't modify the inbox dir until we check whether it was modified recently
        book.log_file.unlink(missing_ok=True)

        if not book.num_files("inbox"):
            print_notice(
                f"{book.inbox_dir} does not contain any known audio files, skipping"
            )
            book.write_log("No audio files found in this folder")
            fail_book(book)
            continue

        if m4b_count == 1:
            smart_print("This book is already an m4b")
            smart_print(
                f"Moving directly to converted books folder → {book.converted_dir}"
            )
            mv_dir_contents(book.inbox_dir, book.converted_dir)
            continue

        # Check if a copy of this book is in fix_dir and bail
        if (cfg.fix_dir / book.basename).exists():
            print_error(
                "A copy of this book is in the fix folder, please fix it and try again"
            )
            fail_book(book)
            continue

        needs_fixing = False

        if book.structure.startswith("multi") or book.structure == "mixed":
            needs_fixing = True

            help_msg = f"Please organize the files in a single folder and rename them so they sort alphabetically\nin the correct order"
            match book.structure:
                case "multi_disc":
                    if cfg.FLATTEN_MULTI_DISC_BOOKS:
                        smart_print(
                            "\nThis folder appears to be a multi-disc book, attempting to flatten it...",
                            end="",
                        )
                        if flattening_files_in_dir_affects_order(book.inbox_dir):
                            print_error(
                                "Flattening this book would affect the file order, cannot proceed"
                            )
                            smart_print(f"{help_msg}\n")
                            book.write_log(
                                "This book appears to be a multi-disc book, but flattening it would affect the file order - it will need to be fixed manually by renaming the files so they sort alphabetically in the correct order"
                            )
                        else:
                            flatten_files_in_dir(book.inbox_dir)
                            book = Audiobook(book.inbox_dir)
                            needs_fixing = False
                            print_aqua(" ✓\n")
                            print_debug(
                                "New file structure:\n".join(
                                    [str(f) for f in book.inbox_dir.glob("*")]
                                )
                            )
                    else:
                        print_error(f"{MULTI_ERR}, maybe this is a multi-disc book?")
                        smart_print(
                            f"{help_msg}, or set FLATTEN_MULTI_DISC_BOOKS=Y to have auto-m4b flatten\nmulti-disc books automatically\n"
                        )
                        book.write_log(f"{MULTI_ERR} (multi-disc book) - {help_msg}")
                case "multi_book":
                    print_error(f"{MULTI_ERR}, maybe this contains multiple books?")
                    help_msg = "To convert these books, move each book folder to the root of the inbox"
                    smart_print(f"{help_msg}\n")
                    book.write_log(f"{MULTI_ERR} (multiple books found) - {help_msg}")
                case _:
                    print_error(f"{MULTI_ERR}, cannot determine book structure")
                    smart_print(f"{help_msg}\n")
                    book.write_log(f"{MULTI_ERR} (structure unknown) - {help_msg}")

        if roman_numerals_count > 1:
            if roman_numerals_affect_file_order(book.inbox_dir):
                print_error(ROMAN_ERR)
                help_msg = "Roman numerals do not sort in alphabetical order; please rename them so they sort alphabetically in the correct order"
                smart_print(f"{help_msg}\n")
                book.write_log(f"{ROMAN_ERR} - {help_msg}")
                needs_fixing = True
            else:
                print_debug(
                    f"Found {roman_numerals_count} roman numeral(s) in {book.basename}, but they don't affect file order"
                )

        if needs_fixing:
            mv_to_fix_dir(book, fail_book)
            continue

        # if nested_audio_dirs_count == 1:
        if book.structure == "flat_nested":
            smart_print(
                f"Audio files for this book are a subfolder, moving them to the book's root folder...",
                end="",
            )
            flatten_files_in_dir(book.inbox_dir)
            print_aqua(" ✓\n")

        smart_print("\nFile/folder info:")

        print_list(f"Output folder: {book.converted_dir}")
        print_list(f"File type: {book.orig_file_type}")
        print_list(f"Audio files: {book.num_files('inbox')}")
        print_list(f"Total size: {book.size('inbox', 'human')}")
        if book.cover_art:
            print_list(f"Cover art: {book.cover_art.name}")

        nl()

        if do_backup(book) is False:
            continue

        if book.converted_file.is_file():
            if cfg.OVERWRITE_MODE == "skip":
                if book.archive_dir.exists():
                    print_notice(
                        f"Found a copy of this book in {tint_path(cfg.archive_dir)}, it has probably already been converted"
                    )
                    print_notice(
                        "Skipping this book because OVERWRITE_EXISTING is not enabled"
                    )
                    continue
                elif book.size("converted", "bytes") > 0:
                    print_notice(
                        f"Output file already exists and OVERWRITE_EXISTING is not enabled, skipping this book"
                    )
                    continue
            else:
                print_warning(
                    "Warning: Output file already exists, it and any other {{.m4b}} files will be overwritten"
                )

        # Move from inbox to merge folder
        smart_print("\nCopying files to working folder...", end="")
        cp_dir(book.inbox_dir, cfg.merge_dir, overwrite_mode="overwrite-silent")
        print_aqua(f" ✓\n")

        book.extract_path_info()
        book.extract_metadata()

        # Pre-create tempdir for m4b-tool in "$buildfolder$book-tmpfiles" and ensure writable
        clean_dir(book.build_dir)
        clean_dir(book.build_tmp_dir)
        rm_all_empty_dirs(cfg.merge_dir)

        book.set_active_dir("build")

        starttime = time.time()

        m4b_tool = m4btool(book)

        nl()

        book.write_description_txt()

        err: Literal[False] | str = False

        cmd = m4b_tool.cmd()

        m4b_tool.msg()

        if cfg.DEBUG:
            print_dark_grey(m4b_tool.esc_cmd())

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.stderr:
            book.write_log(proc.stderr.decode())
            nl()
            raise RuntimeError(proc.stderr.decode())
        else:
            stdout = proc.stdout.decode()

        if cfg.DEBUG:
            smart_print(stdout)

        endtime_log = log_date()
        elapsedtime = int(time.time() - starttime)
        elapsedtime_friendly = human_elapsed_time(elapsedtime)

        if re.search(r"error", stdout, re.I):
            # ignorable errors:
            ###################
            # an error occured, that has not been caught:
            # Array
            # (
            #     [type] => 8192
            #     [message] => Implicit conversion from float 9082109.64 to int loses precision
            #     [file] => phar:///usr/local/bin/m4b-tool/src/library/M4bTool/Parser/SilenceParser.php
            #     [line] => 61
            # )
            ###################
            # regex: an error occured[\s\S]*?Array[\s\S]*?Implicit conversion from float[\s\S]*?\)
            ###################

            err_blocks = [r"an error occured[\s\S]*?Array[\s\S]*?\)"]

            ignorable_errors = [
                r"failed to save key",
                r"implicit conversion from float",
                r"ffmpeg version .* or higher is .* likely to cause errors",
            ]

            # if any of the err_blocks do not match any of the ignorable errors, then it's a valid error
            err = (
                re_group(
                    re.search(
                        rf"PHP (?:Warning|Fatal error):  ([\s\S]*?)Stack trace",
                        stdout,
                        re.I | re.M,
                    ),
                    1,
                )
                .replace("\n", "\n     ")
                .strip()
            )
            if not err:
                for block in [
                    re_group(re.search(err, stdout, re.I)) for err in err_blocks
                ]:
                    if block and not any(
                        re.search(err, block) for err in ignorable_errors
                    ):
                        err = re_group(
                            re.search(rf"\[message\] => (.*$)", block, re.I | re.M), 1
                        )
            print_error(f"m4b-tool Error: {err}")
            smart_print(
                f"See log file in {tint_light_grey(book.fix_dir)} for details\n"
            )
        elif not book.build_file.exists():
            print_error(
                f"Error: m4b-tool failed to convert [[{book}]], no output .m4b file was found"
            )
            err = f"m4b-tool failed to convert {book}, no output .m4b file was found"

        if err:
            stderr = proc.stderr.decode() if proc.stderr else ""
            book.write_log(f"{err}\n{stderr}")
            mv_to_fix_dir(book, fail_book)
            log_global_results(book, "FAILED", 0)
            continue
        else:
            book.write_log(
                f"{endtime_log}  {book}  Converted in {elapsedtime_friendly}\n"
            )

        book.converted_dir.mkdir(parents=True, exist_ok=True)

        # m4b_num_parts=1 # hardcode for now, until we know if we need to split parts

        did_remove_old_desc = False
        for d in [book.build_dir, book.merge_dir, book.converted_dir]:
            desc_files = list(Path(d).rglob(f"{book} [*kHz*].txt"))
            for f in desc_files:
                f.unlink()
                did_remove_old_desc = True

        if did_remove_old_desc:
            print_notice(
                f"Removed old description {pluralize(len(desc_files), 'file')}"
            )

        mv_file_to_dir(
            book.merge_desc_file,
            book.final_desc_file.parent,
            new_filename=book.final_desc_file.name,
            overwrite_mode="overwrite-silent",
        )

        log_global_results(book, "SUCCESS", elapsedtime)

        # TODO: Only handles single m4b output file, not multiple files.
        verify_and_update_id3_tags(book, "build")

        nl()

        smart_print(
            f"Moving to converted books folder → {tint_path(fmt_linebreak_path(book.converted_file, 80, 35))}"
        )

        # Copy other jpg, png, and txt files from mergefolder to output folder
        mv_dir_contents(
            book.merge_dir,
            book.converted_dir,
            only_file_exts=cfg.OTHER_EXTS,
            overwrite_mode="overwrite-silent",
        )

        # Copy log file to output folder as $buildfolder$book/m4b-tool.$book.log
        mv_file_to_dir(
            book.log_file,
            book.converted_dir,
            new_filename=f"m4b-tool.{book}.log",
            overwrite_mode="overwrite-silent",
        )
        book.set_active_dir("converted")

        rm_all_empty_dirs(book.build_dir)

        # Move all built audio files to output folder
        mv_dir_contents(
            book.build_dir,
            book.converted_dir,
            only_file_exts=AUDIO_EXTS,
            silent_files=[book.build_file.name],
        )

        if not book.converted_file.is_file():
            print_error(
                f"Error: The output file does not exist, something went wrong during the conversion\n     Expected it to be at {book.converted_file}"
            )
            mv_to_fix_dir(book, fail_book)
            continue

        # Remove description.txt from output folder if "$book [$desc_quality].txt" exists
        if book.final_desc_file.is_file():
            (book.converted_dir / "description.txt").unlink(missing_ok=True)
        else:
            print_notice(
                "The description.txt is missing (reason unknown), trying to save a new one"
            )
            book.write_description_txt(book.final_desc_file)

        # Remove temp copies in build and merge if it's still there
        shutil.rmtree(book.build_dir, ignore_errors=True)
        shutil.rmtree(book.merge_dir, ignore_errors=True)

        if cfg.on_complete == "move":
            smart_print("Archiving original from inbox...")
            mv_dir_contents(
                book.inbox_dir,
                book.archive_dir,
                overwrite_mode="overwrite-silent",
            )

            if book.inbox_dir.exists():
                print_warning(
                    f"Warning: {tint_warning(book)} is still in the inbox folder, it should have been archived"
                )
                print_orange(
                    "     To prevent this book from being converted again, move it out of the inbox folder"
                )

        elif cfg.on_complete == "delete":
            smart_print("Deleting original from inbox...")
            if is_ok_to_delete(book.inbox_dir):
                shutil.rmtree(book.inbox_dir, ignore_errors=True)
            else:
                print_notice(
                    "Notice: The original folder is not empty, it will not be deleted"
                )
        elif cfg.on_complete == "test_do_nothing":
            print_notice("Test mode: The original folder will not be moved or deleted")

        smart_print(
            Tinta("\nConverted")
            .aqua(book.basename)
            .clear(f"in {elapsedtime_friendly} 🐾✨🥞")
            .to_str()
        )

        divider("\n")
        if b < books_count - 1:
            nl()

    # clear the folders
    clean_dir(cfg.merge_dir)
    clean_dir(cfg.build_dir)
    clean_dir(cfg.trash_dir)

    if books_count >= 1:
        print_grey(
            f"Finished converting all available books, waiting for more to be added to the inbox"
        )
        if not cfg.NO_ASCII:
            print_dark_grey(BOOK_ASCII)
    else:
        print_dark_grey(f"Waiting for books to be added to the inbox...")

    divider()
    nl()
