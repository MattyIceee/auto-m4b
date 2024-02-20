from datetime import datetime
from pathlib import Path

from src.lib.audiobook import Audiobook
from src.lib.config import cfg


def log_results(
    book: Audiobook,
    result: str,
    elapsed: str | int | float = "",
) -> None:
    # note: requires `column` version 2.39 or higher, available in util-linux 2.39 or higher

    # takes the original book's path and the result of the book and logs to outputfolder/auto-m4b.log
    # format: [date] [time] [original book relative path] [info] ["result"=success|failed] [failure-message]
    # pad the relative path with spaces to 70 characters and truncate to 70 characters
    # sanitize book_src to remove multiple spaces and replace | with _
    book_name = f"{book.dir_name[:70]:<70}".replace("  ", " ").replace("|", "_")

    # pad result with spaces to 9 characters
    result = f"{result:<10}"

    # strip all chars from elapsed that are not number or :
    elapsed = "".join(c for c in str(elapsed) if c.isdigit() or c == ":")

    # get current date and time
    datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S%z")

    # Read the current auto-m4b.log file and replace all double spaces with |
    with open(cfg.GLOBAL_LOG_FILE, "r") as f:
        log = f.read().replace("  ", "\t")

    # Remove each line from log if it starts with ^Date\s+
    log = "\n".join(line for line in log.split("\n") if not line.startswith("Date "))

    # Remove blank lines from end of log file
    log = log.rstrip("\n")

    # append the new log entry to the log var if book_src is not empty or whitespace
    if book_name.strip():
        log += f"\n{datetime_str}\t{result}\t{book_name}\t{book.bitrate_friendly}\t{book.samplerate_friendly}\t.{book.orig_file_type}\t{book.num_files("inbox")} files\t{book.size("inbox", "human")}\t{book.duration("inbox", "human")}\t{elapsed}"

    # write the log file
    with open(cfg.GLOBAL_LOG_FILE, "w") as f:
        f.write(log)


def get_log_entry(book_src: Path) -> str:
    # looks in the log file to see if this book has been converted before and returns the log entry or ""
    book_name = book_src.name
    with open(cfg.GLOBAL_LOG_FILE, "r") as f:
        log_entry = next((line for line in f if book_name in line), "")
    return log_entry
