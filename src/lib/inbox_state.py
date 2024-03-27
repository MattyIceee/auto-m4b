import json
import os
import time
from pathlib import Path
from typing import Literal

from src.lib.audiobook import Audiobook
from src.lib.config import cfg, singleton
from src.lib.formatters import human_elapsed_time, human_size
from src.lib.fs_utils import (
    count_audio_files_in_inbox,
    count_standalone_books_in_inbox,
    find_book_dirs_in_inbox,
    find_books_in_inbox,
    find_standalone_books_in_inbox,
    get_size,
    hash_dir_audio_files,
    hash_entire_inbox,
    hash_path,
    inbox_was_recently_modified,
    last_updated_audio_files_at,
    name_matches,
)
from src.lib.term import print_debug

InboxItemStatus = Literal["new", "ok", "needs_retry", "failed", "gone"]


def get_key(path_or_book: "str | Path | Audiobook | InboxItem") -> str:
    if isinstance(path_or_book, str):
        return path_or_book
    if isinstance(path_or_book, Path):
        return path_or_book.name
    if isinstance(path_or_book, Audiobook):
        return path_or_book.basename
    return path_or_book.key


def get_path(key_path_or_book: "str | Path | Audiobook | InboxItem") -> Path:
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
    if isinstance(key_path_or_book, str):
        return InboxItem(cfg.inbox_dir / key_path_or_book)
    if isinstance(key_path_or_book, Path):
        return InboxItem(key_path_or_book)
    if isinstance(key_path_or_book, Audiobook):
        return InboxItem(key_path_or_book)
    return key_path_or_book


class InboxItem:

    def __init__(self, book: str | Path | Audiobook):
        from src.lib.config import cfg

        path = get_path(book)

        self._last_hash = None
        self._last_updated: float | None = None
        self._curr_hash = hash_path(path, only_file_exts=cfg.AUDIO_EXTS)
        self._hash_changed: float = 0
        self.key = path.name
        self.size = (
            get_size(path, only_file_exts=cfg.AUDIO_EXTS) if path.exists() else 0
        )
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
        return cfg.inbox_dir / self.key

    @property
    def hash(self):
        if self.is_gone:
            return ""
        new_hash = (
            hash_dir_audio_files(self.path)
            if self.path.is_dir()
            else hash_path(self.path)
        )
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

    def set_failed(self, reason: str):
        if self.is_gone:
            return
        self.status = "failed"
        self.failed_reason = reason

    def set_needs_retry(self):
        if self.is_gone:
            return
        self.status = "needs_retry"
        self.hash

    def set_ok(self):
        if self.is_gone:
            return
        self.status = "ok"
        self.hash

    @property
    def is_gone(self):
        if self.path.exists():
            return False
        self.status = "gone"
        return True

    @property
    def is_filtered(self):
        return not name_matches(self.path.relative_to(cfg.inbox_dir), cfg.MATCH_NAME)

    @property
    def did_change(self) -> bool:
        return (
            True if self.is_gone else hash_dir_audio_files(self.path) != self._curr_hash
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
class InboxState:

    def __init__(self):
        self._last_global_hash = ""
        self._curr_global_hash = ""
        self._global_hash_changed: float = 0
        self._items = {}
        self.ready = False
        # cfg.MATCH_NAME = os.getenv("MATCH_NAME", None)

    def init(self):
        if not self._items:
            self._items = {p.name: InboxItem(p) for p in find_books_in_inbox()}
        self._items = {k: v for k, v in self._items.items() if not v.is_gone}

        if not self.failed_books and os.getenv("FAILED_BOOKS"):
            failed_books = {
                k: float(v)
                for k, v in json.loads(os.getenv("FAILED_BOOKS", "{}")).items()
            }
            [
                self.set(InboxItem(k), status="failed", last_updated=lu)
                for k, lu in failed_books.items()
            ]
        # self.set_match_filter()
        self.refresh_global_hash()
        self.ready = True

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

    # def refresh(self):
    #     for item in deepcopy(self._items).values():
    #         # if path no longer exists, remove it
    #         if item.is_gone:
    #             self.rm(item.path)
    #         else:
    #             item.hash

    @property
    def match_filter(self):
        if not cfg.MATCH_NAME and (env := os.getenv("MATCH_NAME")):
            self.set_match_filter(env)
            print_debug(
                f"Setting match filter from env: {cfg.MATCH_NAME} (was not previoulsy set in state)"
            )
        return cfg.MATCH_NAME

    def set_match_filter(self, match_name: str | None):
        if match_name != cfg.MATCH_NAME:
            cfg.enable_console()
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

    def reset(self):
        self._items = {}
        # self._items = {path.name: InboxItem(path) for path in find_books_in_inbox()}
        self.flush_global_hash()
        self.set_match_filter(None)
        self._global_hash_changed = 0
        self.ready = False
        return self

    def clear_failed(self):
        for item in self.failed_books.values():
            item.set_ok()
        self._sync_env_failed_books({})

    @property
    def global_hash(self):
        if not self._curr_global_hash or self._curr_global_hash != (
            new_hash := hash_entire_inbox()
        ):
            self._last_global_hash = self._curr_global_hash
            self._curr_global_hash = new_hash
            self._global_hash_changed = time.time()
        return self._curr_global_hash

    def flush_global_hash(self):
        self._curr_global_hash = ""

    def refresh_global_hash(self):
        self._curr_global_hash = hash_entire_inbox()

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
    def did_change(self):
        return self._curr_global_hash != hash_entire_inbox()

    @property
    def time_since_last_change(self):
        return time.time() - self._global_hash_changed

    @property
    def was_recently_modified(self):
        return inbox_was_recently_modified(5)

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
    def all_books(self):
        return find_book_dirs_in_inbox()

    @property
    def num_books(self):
        return len(self.all_books)

    @property
    def filtered_books(self):
        return {k: v for k, v in self._items.items() if v.is_filtered}

    @property
    def num_filtered(self):
        return len(self.filtered_books)

    @property
    def matched_books(self):
        return {
            k: v
            for k, v in self._items.items()
            if not v.is_filtered and v.status != "gone"
        }

    @property
    def num_matched(self):
        return len(self.matched_books)

    @property
    def ok_books(self):
        return {k: v for k, v in self._items.items() if v.status in ["ok", "new"]}

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
    def last_changed(self):
        return self._global_hash_changed

    @property
    def first_run(self):
        return not self._curr_global_hash

    def to_dict(self, refresh_hashes=False):
        return {
            path: item.to_dict(refresh_hashes) for path, item in self._items.items()
        }

    def _sync_env_failed_books(self, new_failed_books: dict[str, float] = {}):
        current_failed_books = json.loads(os.getenv("FAILED_BOOKS", "{}"))
        current_failed_books.update(
            {item.key: item.last_updated for item in self.failed_books.values()}
        )
        if new_failed_books:
            current_failed_books.update(new_failed_books)
        os.environ["FAILED_BOOKS"] = json.dumps(current_failed_books)

    @property
    def fixed_books(self):
        return {
            k: v
            for k, v in self._items.items()
            if v.status == "needs_retry" and v.failed_reason
        }

    def set_failed(self, key_or_path: str | Path, reason: str):
        if item := self.get(key_or_path):
            item.set_failed(reason)
            self._sync_env_failed_books()
        else:
            print_debug(f"Item {key_or_path} not found in inbox")

    def set_needs_retry(self, key_or_path: str | Path):
        if item := self.get(key_or_path):
            item.set_needs_retry()
            self._sync_env_failed_books()
        else:
            print_debug(f"Item {key_or_path} not found in inbox")

    def set_ok(self, key_or_path: str | Path):
        if item := self.get(key_or_path):
            item.set_ok()
            self._sync_env_failed_books()
        else:
            print_debug(f"Item {key_or_path} not found in inbox")

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
