import import_debug

import_debug.bug.push("src/lib/run.py")
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from src.lib.audiobook import Audiobook
from src.lib.config import AUDIO_EXTS, cfg
from src.lib.ffmpeg_utils import build_id3_tags_args
from src.lib.formatters import friendly_date, pluralize
from src.lib.fs_utils import (
    clean_dir,
    count_audio_files_in_dir,
    cp_dir,
    cp_file_to_dir,
    dir_is_empty,
    find_root_dirs_with_audio_files,
    flatten_files_in_dir,
    is_ok_to_delete,
    mv_dir,
    mv_dir_contents,
    rm_all_empty_dirs,
    was_recently_modified,
)
from src.lib.id3_utils import verify_and_update_id3_tags
from src.lib.logger import log_results
from src.lib.misc import human_elapsed_time
from src.lib.parsers import count_roman_numerals
from src.lib.term import (
    divider,
    fmt_linebreak_path,
    nl,
    print_aqua,
    print_blue,
    print_error,
    print_grey,
    print_light_grey,
    print_list,
    print_notice,
    print_orange,
    print_red,
    print_warning,
    smart_print,
    tint_error_accent,
    tint_light_grey,
    tint_path,
    tint_warning,
    tinted_file,
    tinted_m4b,
)


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
            print("This book is already an m4b")
            print(f"Moving directly to converted books folder → {unique_target}")

            if unique_target.exists():
                print(
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
                print(f"Successfully moved to {unique_target}")
        else:
            print(f"Moving book into its own folder → {folder_name}/")
            new_folder = cfg.inbox_dir / folder_name
            new_folder.mkdir(exist_ok=True)
            shutil.move(str(audio_file), str(new_folder))


# glasses 1: ⌐◒-◒
# glasses 2: ᒡ◯ᴖ◯ᒢ


def process_inbox():

    audiobooks_count = count_audio_files_in_dir(
        cfg.inbox_dir, only_file_exts=AUDIO_EXTS
    )

    if audiobooks_count == 0:
        return

    current_local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_aqua(
        f"-------------------  ⌐◒-◒  auto-m4b • {current_local_time}  ---------------------"
    )

    print_grey(f"Checking for new books in {{{{{cfg.inbox_dir}}}}} ꨄ︎")

    if was_recently_modified(
        cfg.inbox_dir
    ):  # replace 'unfinished_dirs' with your variable
        smart_print(
            "The inbox folder was recently modified, waiting for a bit to make sure all files are done copying...\n"
        )
        return

    standalone_count = count_audio_files_in_dir(
        cfg.inbox_dir, only_file_exts=AUDIO_EXTS, maxdepth=0
    )
    if standalone_count:
        process_standalone_files()

    # Find directories containing audio files, handling single quote if present
    audio_dirs = find_root_dirs_with_audio_files(cfg.inbox_dir, mindepth=1)
    books_count = len(audio_dirs)
    # If no books to convert, print, sleep, and exit
    if books_count == 0:  # replace 'books_count' with your variable
        smart_print(f"No books to convert, next check in {cfg.SLEEPTIME}\n")
        return

    smart_print(f"Found {books_count} {pluralize(books_count, 'book')} to convert\n")

    for book_full_path in audio_dirs:

        book = Audiobook(book_full_path)

        m4b_count = count_audio_files_in_dir(book.inbox_dir, only_file_exts=["m4b"])
        root_only_audio_files_count = count_audio_files_in_dir(
            book.inbox_dir, only_file_exts=AUDIO_EXTS, maxdepth=1
        )

        divider()

        print_blue(book.dir_name)

        nested_audio_dirs = find_root_dirs_with_audio_files(book.inbox_dir, mindepth=2)
        nested_audio_dirs_count = len(nested_audio_dirs)
        roman_numerals_count = count_roman_numerals(book.inbox_dir)

        # check if the current dir was modified in the last 1m and skip if so
        if was_recently_modified(book.inbox_dir):
            print_notice(
                "Skipping this book, it was recently updated and may still be copying"
            )
            continue

        if not book.num_files("inbox"):
            print_error(
                f"Error: {book.inbox_dir} does not contain any known audio files, skipping"
            )
            continue

        if m4b_count == 1:
            smart_print("This book is already an m4b")
            smart_print(
                f"Moving directly to converted books folder → {book.converted_dir}"
            )
            mv_dir_contents(book.inbox_dir, book.converted_dir)
            continue

        if book.num_files("inbox") == 0:
            print_notice("No audio files found, skipping")
            continue

        # Check if a copy of this book is in fix_dir and bail
        if (cfg.fix_dir / book.dir_name).exists():
            print_error(
                "Error: A copy of this book is in the fix folder, please fix it and try again"
            )
            continue

        def mv_to_fix_dir():
            smart_print(f"Moving to fix folder → {tint_path(book.fix_dir)}")
            mv_dir(book.inbox_dir, cfg.fix_dir)
            cp_file_to_dir(
                book.log_file, book.fix_dir, new_filename=f"m4b-tool.{book}.log"
            )

        needs_fixing = False
        if nested_audio_dirs_count > 1 or (
            nested_audio_dirs_count == 1 and root_only_audio_files_count > 0
        ):
            needs_fixing = True
            print_error("Error: This book contains multiple folders with audio files")
            smart_print(
                "Maybe this is a multi-disc book, or maybe it is multiple books?"
            )
            smart_print(
                "All files must be in a single folder, named alphabetically in the correct order\n"
            )

        if roman_numerals_count > 1:
            needs_fixing = True
            print_error(
                "Error: Some of this book's files appear to be named with roman numerals"
            )
            smart_print(
                "Roman numerals do not sort in alphabetical order; please make sure files are named alphabetically in the correct order, then remove roman numerals from filenames\n"
            )

        if needs_fixing:
            mv_to_fix_dir()
            continue

        if nested_audio_dirs_count == 1:
            smart_print(
                f"Audio files for this book are a subfolder: {tint_path(f'./{nested_audio_dirs[0]}')}"
            )
            smart_print(f"Moving them to book's root → {tint_path(book.inbox_dir)}")
            flatten_files_in_dir(book.inbox_dir)

        smart_print("\nPreparing to convert...")

        print_list(f"Output folder: {book.converted_dir}")
        print_list(f"File type: {book.orig_file_type}")
        print_list(f"Audio files: {book.num_files('inbox')}")
        print_list(f"Total size: {book.size('inbox', 'human')}")
        print_list(f"Duration: {book.duration('inbox', 'human')}")

        nl()

        # Copy files to backup destination
        if cfg.MAKE_BACKUP:
            smart_print("Skipping making a backup (MAKE_BACKUP is set to N)")
        elif dir_is_empty(book.inbox_dir):
            smart_print("Skipping making a backup (folder is empty)")
        else:
            smart_print(f"Making a backup copy → {tint_path(book.backup_dir)}")
            cp_dir(book.inbox_dir, cfg.backup_dir, "overwrite-silent")

            # Check that files count and folder size match
            orig_files_count = book.num_files("inbox")
            orig_size_b = book.size("inbox", "bytes")
            orig_size_human = book.size("inbox", "human")
            orig_plural = pluralize(orig_files_count, "file")

            backup_files_count = book.num_files("backup")
            backup_size_b = book.size("backup", "bytes")
            backup_size_human = book.size("backup", "human")
            backup_plural = pluralize(backup_files_count, "file")

            if orig_files_count == backup_files_count and orig_size_b == backup_size_b:
                smart_print(
                    f"Backup successful - {backup_files_count} {orig_plural} ({backup_size_human})"
                )
            elif orig_files_count < backup_files_count or orig_size_b < backup_size_b:
                print_light_grey(
                    f"Backup successful - but expected {orig_plural} ({orig_size_human}), found {backup_files_count} {backup_plural} ({backup_size_human})"
                )
                print_light_grey("Assuming this is a previous backup and continuing")
            else:
                print_error(
                    f"Backup failed - expected {orig_files_count} {orig_plural} ({orig_size_human}), found {backup_files_count} {backup_plural} ({backup_size_human})"
                )
                smart_print("Skipping this book")
                continue

        if book.converted_file.is_file():
            if cfg.OVERWRITE_EXISTING == "N":
                if book.archive_dir.exists():
                    smart_print(
                        f"Found a copy of this book in {tint_path(cfg.archive_dir)}, it has probably already been converted"
                    )
                    smart_print(
                        'Skipping this book because OVERWRITE_EXISTING is not "Y"'
                    )
                    continue
                elif book.size("converted", "bytes") > 0:
                    print_error(
                        f"Error: Output file already exists and OVERWRITE_EXISTING is not 'Y', skipping this book"
                    )
                    continue
            else:
                print_warning(
                    "Warning: Output file already exists, it and any other {{.m4b}} files will be overwritten"
                )

        # Move from inbox to merge folder
        smart_print("\nCopying files to build folder...", end="")
        cp_dir(book.inbox_dir, cfg.merge_dir, "overwrite-silent")
        print_aqua(f" ✓\n")

        book.extract_path_info()
        book.extract_metadata()

        # Pre-create tempdir for m4b-tool in "$buildfolder$book-tmpfiles" and ensure writable
        clean_dir(book.build_dir)
        clean_dir(book.build_tmp_dir)
        rm_all_empty_dirs(cfg.merge_dir)
        book.log_file.unlink(missing_ok=True)

        starttime = time.time()
        starttime_friendly = friendly_date()

        nl()

        id3tags = build_id3_tags_args(book.title, book.author, book.year, book.comment)

        book.write_description_txt()

        if book.orig_file_type == "mp3" or book.orig_file_type == "wma":

            smart_print(
                f"Starting {tinted_file(book.orig_file_type)} → {tinted_m4b()} conversion at {tint_light_grey(starttime_friendly)}..."
            )

            chapters_args = f"{cfg.use_filenames_as_chapters_arg}--no-chapter-reindexing --max-chapter-length={cfg.max_chapter_length}"

            m4btool_merge_command = f"{cfg.m4b_tool} merge {book.merge_dir} -n {cfg.debug_arg} --audio-bitrate={book.bitrate} --audio-samplerate={book.samplerate}{cfg.no_cover_image_arg} {chapters_args} --audio-codec=libfdk_aac --jobs={cfg.CPU_CORES} --output-file={book.build_file} --logfile={book.log_file} {id3tags}"

            m4btool_merge_command = " ".join(m4btool_merge_command.split())

        elif book.orig_file_type == "m4a" or book.orig_file_type == "m4b":

            smart_print(
                f"Starting merge/passthrough → {tinted_m4b()} at {tint_light_grey(starttime_friendly)}..."
            )

            # Merge the files directly as chapters (use chapters.txt if it exists) instead of converting
            # Get existing chapters from file
            chapters_args = (
                f"{cfg.use_filenames_as_chapters_arg} --no-chapter-reindexing"
            )
            chapters_files = list(book.merge_dir.glob("*chapters.txt"))

            if len(chapters_files) > 0:
                chapters_file = chapters_files[0]
                chapters_args = f'--chapters-file="{chapters_file}"'
                smart_print(
                    f"Found {len(chapters_files)} chapters {pluralize(len(chapters_files), 'file')}, setting chapters from {tinted_file(chapters_file.name)}"
                )

            m4btool_merge_command = f"{cfg.m4b_tool} merge {book.merge_dir} -n {cfg.debug_arg} --audio-codec=copy --jobs={cfg.CPU_CORES} --output-file={book.build_file} --logfile={book.log_file} {chapters_args} {id3tags}"

        stdout = subprocess.PIPE if cfg.DEBUG else subprocess.DEVNULL
        stderr = subprocess.STDOUT if cfg.DEBUG else subprocess.DEVNULL

        return

        subprocess.run(m4btool_merge_command, shell=True, stdout=stdout, stderr=stderr)

        # print_error "Error: [TEST] m4b-tool failed to convert \"$book\""
        # print "     Moving \"$book\" to fix folder..."
        # mv_dir "$mergefolder$book" "$fix_dir"
        # cp "$logfile" "$fix_dir$book/m4b-tool.$book.log"
        # log_results "$book_full_path" "FAILED" ""
        # break

        endtime_friendly = friendly_date()
        elapsed_time = int(time.time() - starttime)
        elapsedtime_friendly = human_elapsed_time(elapsed_time)

        with open(book.log_file, "r") as f:
            logfile = f.read()

            err = False
            valid_err_blocks = []
            if re.search(r"error", logfile, re.I):

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

                # ignorable errors:
                ignorable_errors = [
                    r"failed to save key",
                    r"implicit conversion from float",
                    r"ffmpeg version .* or higher is .* likely to cause errors",
                ]

                # if any of the err_blocks do not match any of the ignorable errors, then it's a valid error
                valid_err_blocks = [
                    block
                    for block in err_blocks
                    if not any(re.search(err, block) for err in ignorable_errors)
                ]
                print_error(f"Error: m4b-tool found an error in the log file")
                print_red(f"     Last error message: '{valid_err_blocks[-1]}'")
                smart_print(
                    f"     See log file in {tint_light_grey(book.fix_dir)} for details"
                )
                err = True
            elif not book.build_file.exists():
                print_error(
                    f"Error: m4b-tool failed to convert {tint_error_accent(book)}, no output .m4b file was found"
                )
                err = True

            if err:
                mv_to_fix_dir()
                log_results(book, "FAILED", "")
                continue
            else:
                with open(book.log_file, "a") as f:
                    f.write(
                        f"{endtime_friendly} :: {book} :: Converted in {elapsedtime_friendly}\n"
                    )

        # create converted dir
        book.converted_dir.mkdir(parents=True, exist_ok=True)

        # m4b_num_parts=1 # hardcode for now, until we know if we need to split parts

        # Remove old description files from current dir, $buildfolder$book and $mergefolder$book
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

        book.merge_desc_file.rename(book.final_desc_file)
        smart_print(f"Finished in {elapsedtime_friendly}")

        log_results(book, "SUCCESS", elapsedtime_friendly)

        # Copy log file to output folder as $buildfolder$book/m4b-tool.$book.log
        cp_file_to_dir(
            book.log_file, book.converted_dir, new_filename=f"m4b-tool.{book}.log"
        )

        smart_print("Verifying id3 tags...")
        # TODO: Only handles single m4b output file, not multiple files.
        verify_and_update_id3_tags(book, "build")

        nl()

        smart_print(
            f"Moving to converted books folder → {tint_path(fmt_linebreak_path(book.converted_file, 120, 35))}"
        )

        # Move all built audio files to output folder
        mv_dir_contents(book.build_dir, book.converted_dir, only_file_exts=AUDIO_EXTS)

        # Copy other jpg, png, and txt files from mergefolder to output folder
        mv_dir_contents(
            book.merge_dir, book.converted_dir, only_file_exts=cfg.OTHER_EXTS
        )

        # Remove description.txt from output folder if "$book [$desc_quality].txt" exists
        if book.final_desc_file.is_file():
            (book.converted_dir / "description.txt").unlink(missing_ok=True)
        else:
            print_notice(
                "The description.txt is missing (reason unknown), trying to save a new one"
            )
            book.write_description_txt(book.final_desc_file)

        # Remove temp copy in merge
        shutil.rmtree(book.merge_dir, ignore_errors=True)

        if cfg.on_complete == "move":
            smart_print("Archiving original from inbox...")
            mv_dir_contents(book.inbox_dir, book.archive_dir, "overwrite-silent")

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

        smart_print("\nDone processing 🐾✨🥞\n")

    # clear the folders
    divider()
    shutil.rmtree(cfg.merge_dir, ignore_errors=True)
    shutil.rmtree(cfg.build_dir, ignore_errors=True)
    shutil.rmtree(cfg.trash_dir, ignore_errors=True)

    # Delete all *-tmpfiles dirs inside $outputfolder
    for d in list(book.build_dir.rglob("*-tmpfiles")) + list(
        book.converted_dir.rglob("*-tmpfiles")
    ):
        if d.is_dir() and len(list(d.parents)) <= 2:
            shutil.rmtree(d, ignore_errors=True)

    if books_count >= 1:
        smart_print(
            f"Finished converting all available books, next check in {cfg.SLEEPTIME}"
        )
    else:
        smart_print(f"Next check in {cfg.SLEEPTIME}")

    divider()
    nl()


import_debug.bug.pop("src/lib/run.py")
