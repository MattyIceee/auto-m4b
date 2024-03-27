import json
import os
import time
from copy import deepcopy
from pathlib import Path
from typing import Literal

from src.lib.audiobook import Audiobook
from src.lib.config import cfg, singleton
from src.lib.formatters import human_elapsed_time, human_size
from src.lib.fs_utils import (
    find_books_in_inbox,
    get_size,
    hash_dir_audio_files,
    hash_entire_inbox,
    hash_path,
    last_updated_audio_files_at,
)
from src.lib.term import print_debug

InboxItemStatus = Literal["new", "ok", "needs_retry", "failed", "gone"]


class InboxItem:

    def __init__(self, book: str | Path | Audiobook):
        from src.lib.config import cfg

        if isinstance(book, Audiobook):
            path = book.inbox_dir
        elif isinstance(book, str):
            path = Path(book)
        else:
            path = book

        if not path.is_absolute():
            path = cfg.inbox_dir / path

        self._last_hash = None
        self._last_updated: float | None = None
        self._curr_hash = hash_path(path, only_file_exts=cfg.AUDIO_EXTS)
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
        return self._curr_hash

    @property
    def last_updated(self):
        if self._last_updated is not None:
            return self._last_updated
        return last_updated_audio_files_at(self.path)

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
        self._global_hash = ""
        self._items = {}

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
                self.add(InboxItem(k), status="failed", last_updated=lu)
                for k, lu in failed_books.items()
            ]

    def add(
        self,
        key: str | Path | Audiobook | InboxItem,
        *,
        status: InboxItemStatus | None = None,
        last_updated: float | None = None,
    ):
        if isinstance(key, str):
            item = InboxItem(cfg.inbox_dir / key)

        elif not isinstance(key, InboxItem):
            item = InboxItem(key)

        else:
            item = key

        if item.path in self._items:
            msg = f"Item {item.key} already exists in inbox, updating it"
            if status and last_updated:
                msg += f" - new status {status} and last updated {last_updated}"
            elif status:
                msg += f" - new status {status}"
            elif last_updated:
                msg += f" - new last updated {last_updated}"
            print_debug(msg)
            if last_updated:
                self._items[item.path]._last_updated = last_updated
            if status:
                self._items[item.path].status = status
            return
        self._items[item.key] = item

    def get(self, path_or_key: str | Path) -> InboxItem | None:
        key = path_or_key if isinstance(path_or_key, str) else path_or_key.name
        return self._items.get(key, None)

    def rm(self, path_key_or_hash: str | Path):
        if path_key_or_hash in self._items:
            key = path_key_or_hash
        else:
            key = next(
                (
                    item.key
                    for item in self._items.values()
                    if item.hash == path_key_or_hash or item.path == path_key_or_hash
                ),
                None,
            )
        if key:
            self._items.pop(key, None)

    def refresh(self):
        for item in deepcopy(self._items).values():
            # if path no longer exists, remove it
            if item.is_gone:
                self.rm(item.path)
            else:
                item.hash

    def reset(self):
        self._items = {path.name: InboxItem(path) for path in find_books_in_inbox()}
        self.flush_global_hash()

    def clear_failed(self):
        for item in self.failed_books.values():
            item.set_ok()
        self._sync_env_failed_books({})

    @property
    def global_hash(self):
        return self._global_hash

    def flush_global_hash(self):
        self._global_hash = ""

    def get_global_hash(self):
        self._global_hash = hash_entire_inbox()

    @property
    def did_change(self):
        return self.global_hash != hash_entire_inbox()

    @property
    def first_run(self):
        return not self._global_hash

    def to_dict(self, refresh_hashes=False):
        return {
            path: item.to_dict(refresh_hashes) for path, item in self._items.items()
        }

    @property
    def items(self):
        return self._items

    @property
    def failed_books(self):
        return {k: v for k, v in self._items.items() if v.status == "failed"}

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
