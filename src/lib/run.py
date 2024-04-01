import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from tinta import Tinta

from src.lib.audiobook import Audiobook
from src.lib.config import cfg
from src.lib.formatters import (
    human_elapsed_time,
    log_date,
    log_format_elapsed_time,
    pluralize,
    pluralize_with_count,
)
from src.lib.fs_utils import *
from src.lib.id3_utils import verify_and_update_id3_tags
from src.lib.inbox_state import InboxState
from src.lib.logger import log_global_results
from src.lib.m4btool import m4btool
from src.lib.misc import re_group
from src.lib.parsers import (
    roman_numerals_affect_file_order,
)
from src.lib.strings import en
from src.lib.term import (
    AMBER_COLOR,
    BOOK_ASCII,
    border,
    divider,
    fmt_linebreak_path,
    max_term_width,
    nl,
    print_aqua,
    print_dark_grey,
    print_debug,
    print_error,
    print_grey,
    print_list,
    print_notice,
    print_orange,
    smart_print,
    tint_light_grey,
    tint_path,
    tint_warning,
    vline,
)


def print_launch():
    if cfg.SLEEP_TIME and not cfg.TEST:
        time.sleep(min(2, cfg.SLEEP_TIME / 2))
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
    inbox = InboxState()

    if not inbox.num_standalone_files:
        return

    # get all standalone audio files in inbox - i.e., audio files that are directl in the inbox not a subfolder
    for audio_file in inbox.book_dirs:
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

        inbox.set_ok(folder_name)


# glasses 1: ⌐◒-◒
# glasses 2: ᒡ◯ᴖ◯ᒢ


def print_banner():
    inbox = InboxState()

    if inbox.ready and any([not inbox.changed_since_last_run, inbox.banner_printed]):
        return

    current_local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    dash = "-" * 24

    print_aqua(f"{dash}  ⌐◒-◒  auto-m4b • {current_local_time}  -{dash}")

    print_grey(f"Watching for new books in {{{{{cfg.inbox_dir}}}}} ꨄ︎")

    if not inbox.ready:
        nl()

    if inbox.dir_was_recently_modified:
        print_notice(f"{en.INBOX_RECENTLY_MODIFIED}\n")

    time.sleep(1 if not cfg.TEST else 0)

    inbox.banner_printed = True


def print_book_header(book: Audiobook):
    border(len(book.basename))
    smart_print(Tinta().dark_grey(vline).aqua(book.basename).dark_grey(vline).to_str())
    border(len(book.basename))


def print_book_done(b: int, book: Audiobook, elapsedtime: int):
    inbox = InboxState()
    smart_print(
        Tinta("\nConverted")
        .aqua(book.basename)
        .clear(f"in {human_elapsed_time(elapsedtime, relative=False)} 🐾✨🥞")
        .to_str()
    )

    divider("\n")
    if b < inbox.num_books - 1:
        nl()


def print_footer():
    inbox = InboxState()
    if inbox.num_books >= 1:
        print_grey(en.DONE_CONVERTING)
        if not cfg.NO_ASCII:
            print_dark_grey(BOOK_ASCII)
    else:
        print_dark_grey(f"Waiting for books to be added to the inbox...")

    divider()
    nl()


def audio_files_found():
    inbox = InboxState()
    if inbox.num_audio_files_deep == 0:
        print_banner()
        print_debug(
            f"No audio files found in {cfg.inbox_dir}\n        Last updated at {inbox_last_updated_at(friendly=True)}, next check in {cfg.sleeptime_friendly}",
            only_once=True,
        )
        inbox.scan()
        inbox.ready = True
        return False
    return True


def fail_book(book: Audiobook, reason: str = "unknown"):
    """Adds the book's path to the failed books dict with a value of the last modified date of of the book"""
    inbox = InboxState()
    if book.basename in inbox.failed_books:
        return
    inbox.set_failed(book.basename, reason)

    book.write_log(reason)
    book.set_active_dir("inbox")
    if (build_log := book.build_dir / book.log_filename) and build_log.exists():
        if book.log_file.exists():
            # update inbox log with build dir log, preceded by a \n
            with open(build_log, "r") as f:
                log = f.read()
            with open(book.log_file, "a") as f:
                f.write(f"\n{log}")
        else:
            # move build dir log to inbox dir
            shutil.move(build_log, book.log_file)


def backup_ok(book: Audiobook):
    # Copy files to backup destination
    if not cfg.BACKUP:
        print_dark_grey("Not backing up (backups are disabled)")
    elif dir_is_empty_ignoring_hidden_files(book.inbox_dir):
        print_dark_grey("Skipping backup (folder is empty)")
    else:
        ln = "Making a backup copy → "
        smart_print(
            f"{ln}{tint_path(fmt_linebreak_path(book.backup_dir, max_term_width(len(ln)), len(ln)))}"
        )
        cp_dir(book.inbox_dir, cfg.backup_dir, overwrite_mode="skip-silent")

        fuzzy = 1000

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
        size_fuzzy_matches = abs(orig_size_b - backup_size_b) < fuzzy

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
        elif file_count_matches and backup_size_b < orig_size_b - fuzzy:

            if too_small_files := find_too_small_files(book.inbox_dir, book.backup_dir):
                print_debug(
                    f"Found {len(too_small_files)} files in backup that are smaller than the original, trying to re-copy them"
                )

                # re-copy the files that are too small
                for f in too_small_files:
                    cp_file_to_dir(
                        f, book.backup_dir, overwrite_mode="overwrite-silent"
                    )

                # re-check the size of the backup
                if too_small_files := find_too_small_files(
                    book.inbox_dir, book.backup_dir
                ):
                    print_error(
                        f"Backup failed - expected {orig_size_human}, but backup is only {backup_size_human} (found {len(too_small_files)} files that are smaller than the original)"
                    )
                    smart_print("Skipping this book\n")
                    return False
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


def ok_to_overwrite(book: Audiobook):
    if book.converted_file.is_file():
        if cfg.OVERWRITE_MODE == "skip":
            if book.archive_dir.exists():
                print_notice(
                    f"Found a copy of this book in {tint_path(cfg.archive_dir)}, it has probably already been converted"
                )
                print_notice(
                    "Skipping this book because OVERWRITE_EXISTING is not enabled"
                )
                return False
            elif book.size("converted", "bytes") > 0:
                print_notice(
                    f"Output file already exists and OVERWRITE_EXISTING is not enabled, skipping this book"
                )
                return False
        else:
            print_warning(
                "Warning: Output file already exists, it and any other {{.m4b}} files will be overwritten"
            )

    return True


def check_failed_books():
    inbox = InboxState()
    if not inbox.failed_books:
        return
    print_debug(f"Found failed books: {[k for k in inbox.failed_books.keys()]}")
    for book_name, item in inbox.failed_books.items():
        # ensure last_modified is a float
        failed_book = Audiobook(cfg.inbox_dir / book_name)
        was_modified = (
            last_updated_at(failed_book.inbox_dir, only_file_exts=cfg.AUDIO_EXTS)
            > item.last_updated
        )
        if was_modified:
            print_debug(
                f"{book_name} has been modified since it failed last, checking if hash has changed"
            )
        last_book_hash = item._curr_hash
        curr_book_hash = failed_book.hash()
        if last_book_hash is None:
            raise ValueError(
                f"Book {failed_book.inbox_dir} was in failed books but no hash was found for it, this should not happen\ncurr: {curr_book_hash}"
            )
        hash_changed = last_book_hash != curr_book_hash
        if hash_changed:
            print_debug(
                f"{book_name} hash changed since it failed last, removing it from failed books\n        was {last_book_hash}\n        now {curr_book_hash}"
            )
            inbox.set_needs_retry(book_name)
        else:
            print_debug(f"Book hash is the same, keeping it in failed books")


def copy_to_working_dir(book: Audiobook):
    # Move from inbox to merge folder
    smart_print("\nCopying files to working folder...", end="")
    cp_dir(book.inbox_dir, cfg.merge_dir, overwrite_mode="overwrite-silent")
    # copy book.cover_art to merge folder
    if book.cover_art and not book.cover_art.exists():
        cp_file_to_dir(
            book.cover_art, book.merge_dir, overwrite_mode="overwrite-silent"
        )
    print_aqua(" ✓\n")
    book.set_active_dir("merge")


def has_books_to_process():

    inbox = InboxState()

    # If no books to convert, print, sleep, and exit
    if inbox.num_books == 0:  # replace 'books_count' with your variable
        smart_print(f"No books to convert, next check in {cfg.sleeptime_friendly}\n")
        return False

    if inbox.match_filter and not inbox.matched_books:
        smart_print(
            f"Found {pluralize_with_count(inbox.num_books, 'book')} in the inbox, but none match [[{inbox.match_filter}]]",
            highlight_color=AMBER_COLOR,
        )
        return False

    if not inbox.ok_books and inbox.num_failed:
        smart_print(
            f"Found {pluralize_with_count(inbox.num_failed, 'book')} in the inbox that failed to convert - waiting for {pluralize(inbox.num_failed, 'it', 'them')} to be fixed",
            highlight_color=AMBER_COLOR,
        )
        return False

    skipping = (
        f"skipping {inbox.num_failed} that previously failed"
        if inbox.num_failed
        else ""
    )

    if inbox.match_filter and (inbox.all_books_failed):
        s = (
            f"all {pluralize_with_count(inbox.num_matched, 'book')}"
            if inbox.num_matched > 1
            else "1 book"
        )
        smart_print(
            f"Failed to convert {s} in the inbox matching [[{inbox.match_filter}]] (ignoring {inbox.num_filtered})",
            highlight_color=AMBER_COLOR,
        )
        return False

    if inbox.match_filter and inbox.matched_books:
        skipping = f", {skipping}" if skipping else ""
        smart_print(
            f"Found {pluralize_with_count(inbox.num_matched, 'book')} in the inbox matching [[{inbox.match_filter}]] (ignoring {inbox.num_filtered}{skipping})\n",
            highlight_color=AMBER_COLOR,
        )
    elif inbox.failed_books:
        smart_print(
            f"Found {pluralize_with_count(inbox.num_ok, 'book')} to convert ({skipping})\n",
            highlight_color=AMBER_COLOR,
        )
    else:
        smart_print(f"Found {pluralize_with_count(inbox.num_ok, 'book')} to convert\n")

    return True


def can_process_multi_dir(book: Audiobook):
    inbox = InboxState()
    if book.structure.startswith("multi") or book.structure == "mixed":
        help_msg = f"Please organize the files in a single folder and rename them so they sort alphabetically\nin the correct order"
        match book.structure:
            case "multi_disc":
                if cfg.FLATTEN_MULTI_DISC_BOOKS:
                    smart_print(
                        "\nThis folder appears to be a multi-disc book, attempting to flatten it...",
                        end="",
                    )
                    if flattening_files_in_dir_affects_order(book.inbox_dir):
                        nl(2)
                        print_error(
                            "Flattening this book would affect the file order, cannot proceed"
                        )
                        smart_print(f"{help_msg}\n")
                        fail_book(
                            book,
                            "This book appears to be a multi-disc book, but flattening it would affect the file order - it will need to be fixed manually by renaming the files so they sort alphabetically in the correct order",
                        )
                        return False
                    else:
                        flatten_files_in_dir(book.inbox_dir)
                        book = Audiobook(book.inbox_dir)
                        print_aqua(" ✓\n")
                        files = "\n".join([str(f) for f in book.inbox_dir.glob("*")])
                        print_debug(f"New file structure:\n{files}")
                        inbox.set_ok(book.basename)
                else:
                    print_error(f"{en.MULTI_ERR}, maybe this is a multi-disc book?")
                    smart_print(
                        f"{help_msg}, or set FLATTEN_MULTI_DISC_BOOKS=Y to have auto-m4b flatten\nmulti-disc books automatically\n"
                    )
                    fail_book(book, f"{en.MULTI_ERR} (multi-disc book) - {help_msg}")
                    return False
            case "multi_book":
                print_error(f"{en.MULTI_ERR}, maybe this contains multiple books?")
                help_msg = "To convert these books, move each book folder to the root of the inbox"
                smart_print(f"{help_msg}\n")
                fail_book(book, f"{en.MULTI_ERR} (multiple books found) - {help_msg}")
                return False
            case _:
                print_error(f"{en.MULTI_ERR}, cannot determine book structure")
                smart_print(f"{help_msg}\n")
                fail_book(book, f"{en.MULTI_ERR} (structure unknown) - {help_msg}")
                return False

    return True


def can_process_roman_numeral_book(book: Audiobook):
    if book.num_roman_numerals > 1:
        if roman_numerals_affect_file_order(book.inbox_dir):
            print_error(en.ROMAN_ERR)
            help_msg = "Roman numerals do not sort in alphabetical order; please rename them so they sort alphabetically in the correct order"
            smart_print(f"{help_msg}\n")
            fail_book(book, f"{en.ROMAN_ERR} - {help_msg}")
            return False
        else:
            print_debug(
                f"Found {book.num_roman_numerals} roman numeral(s) in {book.basename}, but they don't affect file order"
            )
    return True


def is_already_m4b(book: Audiobook):
    m4b_count = count_audio_files_in_dir(book.inbox_dir, only_file_exts=["m4b"])
    if m4b_count == 1:
        smart_print("This book is already an m4b")
        smart_print(f"Moving directly to converted books folder → {book.converted_dir}")
        mv_dir_contents(book.inbox_dir, book.converted_dir)
        return True
    return False


def has_audio_files(book: Audiobook):
    if not book.num_files("inbox"):
        print_notice(
            f"{book.inbox_dir} does not contain any known audio files, skipping"
        )
        fail_book(book, "No audio files found in this folder")
        return False
    return True


def flatten_nested_book(book: Audiobook):
    if book.structure == "flat_nested":
        smart_print(
            f"Audio files for this book are a subfolder, moving them to the book's root folder...",
            end="",
        )
        flatten_files_in_dir(book.inbox_dir)
        print_aqua(" ✓\n")


def print_book_info(book):
    smart_print("\nFile/folder info:")

    print_list(f"Source folder: {book.inbox_dir}")
    print_list(f"Output folder: {book.converted_dir}")
    print_list(f"File type: {book.orig_file_type}")
    print_list(f"Audio files: {book.num_files('inbox')}")
    print_list(f"Total size: {book.size('inbox', 'human')}")
    if book.cover_art:
        print_list(f"Cover art: {book.cover_art.name}")

    nl()


def convert_book(book: Audiobook):
    starttime = time.time()
    m4b_tool = m4btool(book)

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
            for block in [re_group(re.search(err, stdout, re.I)) for err in err_blocks]:
                if block and not any(re.search(err, block) for err in ignorable_errors):
                    err = re_group(
                        re.search(rf"\[message\] => (.*$)", block, re.I | re.M), 1
                    )
        print_error(f"m4b-tool Error: {err}")
        smart_print(f"See log file in {tint_light_grey(book.inbox_dir)} for details\n")
    elif not book.build_file.exists():
        print_error(
            f"Error: m4b-tool failed to convert [[{book}]], no output .m4b file was found"
        )
        err = f"m4b-tool failed to convert {book}, no output .m4b file was found"

    if err:
        stderr = proc.stderr.decode() if proc.stderr else ""
        book.write_log(f"{err}\n{stderr}")
        fail_book(book)
        log_global_results(book, "FAILED", 0)
        return False
    else:
        book.write_log(
            f"{endtime_log}  {book}  Converted in {log_format_elapsed_time(elapsedtime)}\n"
        )

    return elapsedtime


def move_desc_file(book: Audiobook):
    did_remove_old_desc = False
    for d in [book.build_dir, book.merge_dir, book.converted_dir]:
        desc_files = list(Path(d).rglob(f"{book} [*kHz*].txt"))
        for f in desc_files:
            f.unlink()
            did_remove_old_desc = True

    if did_remove_old_desc:
        print_notice(f"Removed old description {pluralize(len(desc_files), 'file')}")

    mv_file_to_dir(
        book.merge_desc_file,
        book.final_desc_file.parent,
        new_filename=book.final_desc_file.name,
        overwrite_mode="overwrite-silent",
    )


def move_converted_book_and_extras(book: Audiobook):
    ln = "Moving to converted books folder → "
    smart_print(
        f"{ln}{tint_path(fmt_linebreak_path(book.converted_file, max_term_width(len(ln)), len(ln)))}"
    )

    # Copy other jpg, png, and txt files from mergefolder to output folder
    mv_dir_contents(
        book.merge_dir,
        book.converted_dir,
        only_file_exts=cfg.OTHER_EXTS,
        overwrite_mode="overwrite-silent",
    )

    mv_file_to_dir(
        book.log_file,
        book.converted_dir,
        new_filename=book.log_filename,
        overwrite_mode="overwrite-silent",
    )

    rm_all_empty_dirs(book.build_dir)

    # Move all built audio files to output folder
    mv_dir_contents(
        book.build_dir,
        book.converted_dir,
        only_file_exts=AUDIO_EXTS,
        silent_files=[book.build_file.name],
    )

    book.set_active_dir("converted")

    if not book.converted_file.is_file():
        print_error(
            f"Error: The output file does not exist, something went wrong during the conversion\n     Expected it to be at {book.converted_file}"
        )
        fail_book(book)
        return False

    # Remove description.txt from output folder if "$book [$desc_quality].txt" exists
    if book.final_desc_file.is_file():
        (book.converted_dir / "description.txt").unlink(missing_ok=True)
    else:
        print_notice(
            "The description.txt is missing (reason unknown), trying to save a new one"
        )
        book.write_description_txt(book.final_desc_file)
    return True


def archive_inbox_copy(book: Audiobook):
    if cfg.ON_COMPLETE == "move":
        smart_print("Archiving original from inbox...", end="")
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
            return
        print_aqua(" ✓")

    elif cfg.ON_COMPLETE == "delete":
        smart_print("Deleting original from inbox...", end="")
        can_del = is_ok_to_delete(book.inbox_dir)
        if can_del or cfg.BACKUP:
            rm_dir(book.inbox_dir, ignore_errors=True, even_if_not_empty=True)
        elif not can_del and not cfg.BACKUP:
            print_notice(
                "Notice: The original folder is not empty, it will not be deleted because backups are disabled"
            )
            return
        print_aqua(" ✓")

    elif cfg.ON_COMPLETE == "test_do_nothing":
        print_notice("Test mode: The original folder will not be moved or deleted")


def process_inbox():
    inbox = InboxState()

    if not audio_files_found():
        return

    if not inbox.inbox_needs_processing() and inbox.ready:
        print_debug("Inbox hash is the same, skipping this loop", only_once=True)
        return

    inbox.scan()
    inbox.ready = True

    process_standalone_files()

    check_failed_books()

    if not has_books_to_process():
        return

    for b, item in enumerate(inbox.matched_ok_books.values()):

        book = Audiobook(item.path)
        print_book_header(book)

        if not item.path.exists():
            print_notice(
                f"This book was removed from the inbox or cannot be accessed, skipping"
            )
            continue

        # check if the current dir was modified in the last 1m and skip if so
        if was_recently_modified(book.inbox_dir):
            print_notice(en.BOOK_RECENTLY_MODIFIED)
            continue

        if inbox.should_retry(book):
            nl()
            smart_print(en.BOOK_SHOULD_RETRY)

        # can't modify the inbox dir until we check whether it was modified recently
        book.log_file.unlink(missing_ok=True)

        if is_already_m4b(book):
            continue

        if not has_audio_files(book):
            continue

        if not can_process_multi_dir(book):
            continue

        if not can_process_roman_numeral_book(book):
            continue

        flatten_nested_book(book)
        print_book_info(book)

        if not backup_ok(book):
            continue

        if not ok_to_overwrite(book):
            continue

        inbox.set_ok(book)

        copy_to_working_dir(book)

        book.extract_path_info()
        book.extract_metadata()

        clean_dirs([book.build_dir, book.build_tmp_dir])
        rm_all_empty_dirs(cfg.merge_dir)

        book.set_active_dir("build")

        nl()

        book.write_description_txt()

        if (elapsedtime := convert_book(book)) is False:
            continue

        book.converted_dir.mkdir(parents=True, exist_ok=True)

        # m4b_num_parts=1 # hardcode for now, until we know if we need to split parts

        move_desc_file(book)
        log_global_results(book, "SUCCESS", elapsedtime)

        # TODO: Only handles single m4b output file, not multiple files.
        verify_and_update_id3_tags(book, "build")

        if not move_converted_book_and_extras(book):
            continue

        archive_inbox_copy(book)
        print_book_done(b, book, elapsedtime)
        rm_dirs(
            [book.build_dir, book.merge_dir], ignore_errors=True, even_if_not_empty=True
        )

    print_footer()
    clean_dirs([cfg.merge_dir, cfg.build_dir, cfg.trash_dir])
    inbox.done()
