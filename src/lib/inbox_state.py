import json
import os
import time
from collections.abc import Callable
from functools import cached_property, wraps
from pathlib import Path
from typing import Any, cast, Literal

from src.lib.audiobook import Audiobook
from src.lib.formatters import human_elapsed_time, human_size
from src.lib.fs_utils import (
    count_audio_files_in_inbox,
    count_standalone_books_in_inbox,
    find_base_dirs_with_audio_files,
    find_book_dirs_in_inbox,
    find_books_in_inbox,
    find_standalone_books_in_inbox,
    get_audio_size,
    hash_path_audio_files,
    last_updated_audio_files_at,
    name_matches,
)
from src.lib.misc import singleton
from src.lib.parsers import is_maybe_multi_book_or_series
from src.lib.term import print_debug

InboxItemStatus = Literal["new", "ok", "needs_retry", "failed", "gone"]


def get_key(path_or_book: "str | Path | Audiobook | InboxItem") -> str:
    if isinstance(path_or_book, str):
        return path_or_book
    if isinstance(path_or_book, Path):
        return path_or_book.name
    # if isinstance(path_or_book, Audiobook):
    #     return path_or_book.key
    return path_or_book.key


def get_path(key_path_or_book: "str | Path | Audiobook | InboxItem") -> Path:
    from src.lib.config import cfg

    if isinstance(key_path_or_book, str):
        path = Path(key_path_or_book)
        if not path.is_absolute():
            return cfg.inbox_dir / key_path_or_book
        return path
    if isinstance(key_path_or_book, Path):
        return key_path_or_book
    if isinstance(key_path_or_book, Audiobook):
        return key_path_or_book.inbox_dir
    return key_path_or_book.path


def get_item(key_path_or_book: "str | Path | Audiobook | InboxItem") -> "InboxItem":
    from src.lib.config import cfg

    if isinstance(key_path_or_book, str):
        return InboxItem(cfg.inbox_dir / key_path_or_book)
    if isinstance(key_path_or_book, Path):
        return InboxItem(key_path_or_book)
    if isinstance(key_path_or_book, Audiobook):
        return InboxItem(key_path_or_book)
    return key_path_or_book


def filter_series_parents(d: dict[str, "InboxItem"]):
    return {k: v for k, v in d.items() if not v.is_maybe_series_parent}


def scanner(func: Callable[..., Any]):
    """A decorator that scans the path of a Hasher object after calling the decorated function."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        hasher = cast(Hasher, args[0])
        result = func(*args, **kwargs)
        hasher.scan()
        return result

    return wrapper


class Hasher:
    """Stores the current, and previous 5 hashes of a given path as a tuple. When a new hash is added, the oldest one is removed, and the rest are shifted down by one. If a hash is the same as the previous one, it is not added - only the timestamp on the current hash is updated. This is used to determine if a file has changed in the last 5 seconds."""

    def __init__(self, path: Path, max_hashes: int = 10):
        self.path = path
        # self.last_updated = last_updated_audio_files_at(path)
        self.max_hashes = max_hashes
        self._hashes = []
        self._last_run = None
        self.flush()

    def __repr__(self):
        return f"{self.path} -- {self._hashes} -- {human_elapsed_time(time.time() - self.last_updated)}"

    def __eq__(self, other):
        return self.path == other.path

    @property
    def last_updated(self):
        return last_updated_audio_files_at(self.path)

    def scan(self):
        new_hash = hash_path_audio_files(self.path)
        if new_hash != self.current_hash:
            self._hashes.insert(0, (new_hash, time.time()))
            if len(self._hashes) > self.max_hashes:
                self._hashes.pop()

    @property
    def hashes(self):
        # returns self._hashes, but calculates time since on each hash
        return [(h, time.time() - t) for h, t in self._hashes]

    @property
    @scanner
    def changed_since_last_run(self):
        return hash_path_audio_files(self.path) != self.last_run_hash

    @property
    def time_since_last_change(self):
        return time.time() - self.last_updated

    @property
    def time_since_hash_changed(self):
        return time.time() - self._hashes[0][1]

    @property
    def dir_was_recently_modified(self):
        from src.lib.config import cfg

        return self.time_since_last_change < cfg.WAIT_TIME

    def inbox_needs_processing(self):

        from src.lib.run import print_banner

        changed_after_waiting = False
        # printed_waiting = False
        waited_count = 0
        before_modified_hash = self.current_hash
        banner_printed = False
        rec_mod = self.dir_was_recently_modified
        while self.dir_was_recently_modified:
            print_debug(f"Waiting for inbox to be modified: {waited_count + 1}")
            self.scan()
            self.ready = True
            if self.current_hash != before_modified_hash:
                print_debug(
                    f"self hash - last: {self.previous_hash or None} / curr: {self.current_hash}",
                    # only_once=True,
                )
                if not banner_printed:
                    self.banner_printed = False
                    changed_after_waiting = True
                    self.waited_for_changes = True
                    print_banner()
                    banner_printed = True
                # if not printed_waiting:

                #     printed_waiting = True
            waited_count += 1
            time.sleep(0.5)

        needs_processing = changed_after_waiting or self.changed_since_last_run
        # print_debug(
        #     f"----------------------------\n"
        #     f"        Recently modified: {rec_mod}\n"
        #     f"        Last run hash: {self.last_run_hash}\n"
        #     f"        Prev hash: {self.previous_hash}\n"
        #     f"        Curr hash: {self.current_hash}\n"
        #     f"        Next hash: {self.next_hash}\n"
        #     f"        Changed after waiting: {changed_after_waiting}\n"
        #     f"        Changed since last run: {self.changed_since_last_run}\n"
        #     f"        Needs processing: {needs_processing}\n"
        #     f"        Waited count: {waited_count}\n"
        #     f"        Ready: {self.ready}\n"
        # )

        if waited_count:
            print_debug("Done waiting for inbox to be modified")
            self.banner_printed = True

        if needs_processing:
            self.banner_printed = banner_printed
            print_banner()
            self.scan()
            self.ready = True

        return needs_processing

    @property
    def hash_was_recently_changed(self):
        from src.lib.config import cfg

        return self.time_since_hash_changed < cfg.WAIT_TIME + cfg.SLEEP_TIME

    @property
    def current_hash(self):
        return self._hashes[0][0]

    @property
    def previous_hash(self):
        return self._hashes[1][0] if len(self._hashes) > 1 else ""

    @property
    def next_hash(self):
        return hash_path_audio_files(self.path)

    def done(self):
        if len(self._hashes):
            self.scan()
            self._last_run = self._hashes[0]

    @property
    def last_run(self):
        return self._last_run

    @property
    def last_run_hash(self):
        return self.last_run[0] if self.last_run else ""

    def to_dict(self):
        return {
            "path": str(self.path),
            "hashes": self._hashes,
            "last_updated": self.last_updated,
        }

    def flush(self):
        self._hashes = [(hash_path_audio_files(self.path), self.last_updated)]

    def __hash__(self):
        return hash(self.path)

    def __str__(self):
        return self.__repr__()


class InboxItem:

    def __init__(self, book: str | Path | Audiobook):
        from src.lib.config import cfg

        path = get_path(book)

        self._last_hash = None
        self._last_updated: float | None = None
        self._curr_hash = hash_path_audio_files(path)
        self._hash_changed: float = 0
        self.key = str(path.relative_to(cfg.inbox_dir))
        self.size = get_audio_size(path) if path.exists() else 0
        self.status: InboxItemStatus = "new"
        self.failed_reason: str = ""

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        since = human_elapsed_time(time.time() - self.last_updated)
        return f"{self.key} ({human_size(self.size)}) -- {self.status} -- {since} -- {self.hash}"

    def __eq__(self, other):
        return self.key == other.key

    def reload(self):
        self = InboxItem(self.path)

    @property
    def path(self) -> Path:
        from src.lib.config import cfg

        return cfg.inbox_dir / self.key

    @property
    def hash(self):
        if self.is_gone:
            return ""
        new_hash = hash_path_audio_files(self.path)
        if new_hash != self._curr_hash:
            self._last_hash = self._curr_hash
            self._curr_hash = new_hash
            self._hash_changed = time.time()
        return self._curr_hash

    @property
    def last_updated(self):
        if self._last_updated is not None:
            return self._last_updated
        return last_updated_audio_files_at(self.path)

    @property
    def time_since_last_change(self):
        return time.time() - self._hash_changed

    def _set(
        self,
        status: InboxItemStatus,
        reason: str | None = None,
        last_updated: float | None = None,
    ):
        if self.is_gone:
            return
        self.status = status
        if reason:
            self.failed_reason = reason
        if last_updated:
            self._last_updated = last_updated
        self.hash

    def set_failed(self, reason: str, last_updated: float | None = None):
        self._set("failed", reason, last_updated)

    def set_needs_retry(self):
        self._set("needs_retry")

    def set_ok(self):
        self._set("ok")

    def set_gone(self):
        self._set("gone")

    @property
    def is_gone(self):
        if self.path.exists():
            return False
        self.status = "gone"
        return True

    @property
    def is_filtered(self):
        from src.lib.config import cfg

        return not name_matches(self.path.relative_to(cfg.inbox_dir), cfg.MATCH_NAME)

    @property
    def is_maybe_series_book(self):
        return len(Path(self.key).parts) > 1

    @cached_property
    def is_maybe_series_parent(self):
        return any(
            [
                is_maybe_multi_book_or_series(d.name)
                for d in find_base_dirs_with_audio_files(self.path)
            ]
        )

    @property
    def did_change(self) -> bool:
        return (
            True
            if self.is_gone
            else hash_path_audio_files(self.path) != self._curr_hash
        )

    @property
    def type(self) -> Literal["dir", "file", "gone"]:
        return (
            "dir" if self.path.is_dir() else "file" if self.path.is_file() else "gone"
        )

    def to_dict(self, refresh_hash=False):
        h = self.hash if (refresh_hash or not self._curr_hash) else self._curr_hash
        return {
            "key": self.key,
            "hash": h,
            "path": str(self.path),
            "size": self.size,
            "last_updated": self.last_updated,
            "status": "gone" if self.is_gone else self.status,
            "failed_reason": self.failed_reason,
        }


@singleton
class InboxState(Hasher):

    def __init__(self):
        from src.lib.config import cfg

        super().__init__(cfg.inbox_dir)
        self._items = {}
        self.ready = False
        self.banner_printed = False
        self.waited_for_changes = False

    def set(
        self,
        key_path_or_book: str | Path | Audiobook | InboxItem,
        *,
        status: InboxItemStatus | None = None,
        last_updated: float | None = None,
    ):
        item = get_item(key_path_or_book)

        self._items[item.key] = item
        if last_updated:
            self._items[item.key]._last_updated = last_updated
        if status:
            self._items[item.key].status = status

    def get(self, key_path_or_book: str | Path | Audiobook) -> InboxItem | None:
        return self._items.get(get_key(key_path_or_book), None)

    def get_from_hash(self, hash: str):
        return next(
            (
                item.key
                for item in self._items.values()
                if item.hash == hash or item.path == hash
            ),
            None,
        )

    def rm(self, key_path_book_or_hash: str | Path | Audiobook):
        key = get_key(key_path_book_or_hash)
        if not key and not (key := self.get_from_hash(str(key_path_book_or_hash))):
            return
        self._items.pop(key, None)

    def scan(self):
        super().scan()
        new_items = {p.name: InboxItem(p) for p in find_books_in_inbox()}
        gone_keys = set(self._items.keys()) - set(new_items.keys())
        for k, v in new_items.items():
            if k not in self._items:
                self._items[k] = v

        # remove items that are no longer in the inbox
        for k in gone_keys:
            if item := self._items.get(k):
                item.set_gone()

        if not self.failed_books and os.getenv("FAILED_BOOKS"):
            self._sync_failed_from_env()

    def flush(self):
        super().flush()
        self._items = {}

    @property
    def match_filter(self):
        from src.lib.config import cfg

        if not cfg.MATCH_NAME and (env := os.getenv("MATCH_NAME")):
            self.set_match_filter(env)
            print_debug(
                f"Setting match filter from env: {cfg.MATCH_NAME} (was not previoulsy set in state)"
            )
        return cfg.MATCH_NAME

    def set_match_filter(self, match_name: str | None):
        from src.lib.config import cfg

        if match_name is None:
            os.environ.pop("MATCH_NAME", None)
            # update all items where filtered was set to ok
            for d in self.filtered_books:
                if item := self.get(d):
                    item.set_ok()
            cfg.MATCH_NAME = ""
            return

        os.environ["MATCH_NAME"] = match_name
        cfg.MATCH_NAME = match_name

    def reset(self, new_match_filter: str | None = None):

        # self._items = {path.name: InboxItem(path) for path in find_books_in_inbox()}
        # self.flush_global_hash()
        self.set_match_filter(new_match_filter)
        # self._items = {}
        # self._global_hash_changed = inbox_last_updated_at()
        self.flush()
        self.ready = False
        # self.scan()
        self._sync_failed_from_env()
        return self

    def clear_failed(self):
        for item in self.failed_books.values():
            item.set_ok()
        self._sync_failed_to_env()

    def did_fail(self, key_path_or_book: str | Path | Audiobook):
        if item := self.get(key_path_or_book):
            return item.status == "failed"
        return False

    def should_retry(self, key_path_or_book: str | Path | Audiobook):
        if item := self.get(key_path_or_book):
            return item.status == "needs_retry"
        return False

    def is_filtered(self, key_or_path: str | Path | Audiobook):
        if item := self.get(key_or_path):
            return item.is_filtered
        return False

    def is_ok(self, key_path_or_book: str | Path | Audiobook):
        if item := self.get(key_path_or_book):
            return item.status in ["ok", "new"]
        return False

    @property
    def items(self):
        return self._items

    @property
    def num_audio_files_deep(self):
        return count_audio_files_in_inbox()

    @property
    def standalone_files(self):
        return find_standalone_books_in_inbox()

    @property
    def num_standalone_files(self):
        return count_standalone_books_in_inbox()

    @property
    def book_dirs(self):
        return find_book_dirs_in_inbox()

    @property
    def series_parents(self):
        return find_book_dirs_in_inbox(only_series_parents=True)

    @property
    def num_books(self):
        return len(self.book_dirs) - len(self.series_parents)

    @property
    def num_series(self):
        return len(self.series_parents)

    @property
    def filtered_books(self):
        return {k: v for k, v in self._items.items() if v.is_filtered}

    @property
    def num_filtered(self):
        return len(self.filtered_books)

    @property
    def matched_books(self):
        return filter_series_parents(
            {k: v for k, v in self._items.items() if not v.is_filtered}
        )

    @property
    def items_to_process(self):
        return {
            k: v
            for k, v in self._items.items()
            if not v.is_filtered and v.status in ["ok", "new", "needs_retry"]
        }

    @property
    def num_matched(self):
        return len(self.matched_books)

    @property
    def ok_books(self):
        return filter_series_parents(
            {
                k: v
                for k, v in self._items.items()
                if v.status in ["ok", "new", "needs_retry"]
            }
        )

    @property
    def num_ok(self):
        return len(self.ok_books)

    @property
    def has_failed_books(self):
        return any(v.status in ["failed", "needs_retry"] for v in self._items.values())

    @property
    def failed_books(self):
        return {k: v for k, v in self._items.items() if v.status == "failed"}

    @property
    def num_failed(self):
        return len(self.failed_books)

    @property
    def all_books_failed(self):
        haystack = (
            self._items.values()
            if not self.match_filter
            else self.matched_books.values()
        )
        return all(v.status == "failed" for v in haystack)

    def to_dict(self, refresh_hashes=False):
        return {
            path: item.to_dict(refresh_hashes) for path, item in self._items.items()
        }

    def _sync_failed_to_env(self):
        os.environ["FAILED_BOOKS"] = json.dumps(
            {k: v.last_updated for k, v in self.failed_books.items()}
        )

    def _sync_failed_from_env(self):
        failed_books = {
            k: float(v) for k, v in json.loads(os.getenv("FAILED_BOOKS", "{}")).items()
        }
        for k, lu in failed_books.items():
            self.set_failed(k, "From ENV", lu)

    @property
    def fixed_books(self):
        return {
            k: v
            for k, v in self._items.items()
            if v.status == "needs_retry" and v.failed_reason
        }

    def set_failed(
        self,
        key_path_or_book: str | Path | Audiobook,
        reason: str,
        last_updated: float | None = None,
    ):
        if not self.get(key_path_or_book):
            self.set(key_path_or_book)

        if item := self.get(key_path_or_book):
            item.set_failed(reason)
            if last_updated is not None:
                item._last_updated = last_updated
            self._sync_failed_to_env()
        else:
            print_debug(f"Item {key_path_or_book} not found in inbox")

    def set_needs_retry(self, key_path_or_book: str | Path | Audiobook):
        if not self.get(key_path_or_book):
            self.set(key_path_or_book)

        if item := self.get(key_path_or_book):
            item.set_needs_retry()
            self._sync_failed_to_env()
        else:
            print_debug(f"Item {key_path_or_book} not found in inbox")

    def set_ok(self, key_path_or_book: str | Path | Audiobook):
        if not self.get(key_path_or_book):
            self.set(key_path_or_book)

        if item := self.get(key_path_or_book):
            item.set_ok()
            self._sync_failed_to_env()
        else:
            print_debug(f"Item {key_path_or_book} not found in inbox")

    def __iter__(self):
        return iter(self._items.values())

    def __len__(self):
        return len(self._items)

    def __contains__(self, path: Path):
        return path in self._items

    def __repr__(self):
        return f"Inbox state:\n{self.__str__()}"

    def __str__(self):
        return json.dumps(self.to_dict(), indent=4)
