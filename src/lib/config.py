import time
from contextlib import contextmanager
from datetime import datetime

import import_debug

from src.lib.misc import get_git_root, load_env, parse_bool, to_json
from src.lib.term import nl, print_amber

import_debug.bug.push("src/lib/config.py")
import argparse
import os
import shutil
import subprocess
import tempfile
from functools import cached_property
from multiprocessing import cpu_count
from pathlib import Path
from typing import Any, cast, Literal, overload, TYPE_CHECKING, TypeVar

from src.lib.typing import OverwriteMode

DEFAULT_SLEEPTIME = 10  # Set this to your default sleep time
AUDIO_EXTS = [".mp3", ".m4a", ".m4b", ".wma"]
OTHER_EXTS = [
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".svg",
    ".epub",
    ".mobi",
    ".azw",
    ".pdf",
    ".txt",
    ".log",
]

IGNORE_FILES = [
    ".DS_Store",
    "._*",
    ".AppleDouble",
    ".LSOverride",
    ".Spotlight-V100",
    ".Trashes",
    "__MACOSX",
    "ehthumbs.db",
    "Thumbs.db",
    "@eaDir",
    "*.sh",
]

WORKING_DIRS = [
    "BUILD_FOLDER",
    "MERGE_FOLDER",
    "TRASH_FOLDER",
]

if TYPE_CHECKING:
    pass

OnComplete = Literal["move", "delete"]

parser = argparse.ArgumentParser()
parser.add_argument("--env", help="Path to .env file", type=Path)
parser.add_argument("--debug", help="Enable debug mode", action="store_true")
parser.add_argument("--test", help="Enable test mode", action="store_true")
parser.add_argument(
    "-l",
    "--max_loops",
    help="Max number of times the app should loop (default: -1, infinity)",
    default=-1,
    type=int,
)
parser.add_argument(
    "--no-fix",
    help="Disables moving problematic books to the fix folder. Default is False, or True if DEBUG mode is on.",
    action="store_true",
)


class AutoM4bArgs:
    env: Path | None
    debug: bool
    test: bool
    max_loops: int
    no_fix: bool

    def __init__(
        self,
        env: Path | None = None,
        debug: bool | None = None,
        test: bool | None = None,
        max_loops: int | None = None,
        no_fix: bool | None = None,
    ):

        args = parser.parse_known_args()[0]

        def pick(a, b, default=None):
            return a if a is not None else (b if b is not None else default)

        self.env = pick(env, args.env)
        self.debug = pick(debug, args.debug, False)
        self.test = pick(test, args.test, False)
        self.max_loops = pick(max_loops, args.max_loops, -1)
        self.no_fix = pick(no_fix, args.no_fix, False)

    def __str__(self) -> str:
        return to_json(self.__dict__)


def ensure_dir_exists_and_is_writable(path: Path, throw: bool = True) -> None:
    from src.lib.term import print_warning

    path.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    is_writable = os.access(path, os.W_OK)

    if not exists:
        raise FileNotFoundError(f"{path} does not exist and could not be created")

    if not is_writable:
        if throw:
            raise PermissionError(
                f"{path} is not writable by current user, please fix permissions and try again"
            )
        else:
            print_warning(
                f"Warning: {path} is not writable by current user, this may result in data loss"
            )
            return


C = TypeVar("C")


def singleton(class_: type[C]) -> type[C]:
    class class_w(class_):
        _instance = None

        def __new__(cls, *args, **kwargs):
            if class_w._instance is None:
                import_debug.bug.push("src/lib/config.py -> new Config()")
                class_w._instance = super(class_w, cls).__new__(cls, *args, **kwargs)
                class_w._instance._sealed = False
            return class_w._instance

        def __init__(self, *args, **kwargs):
            if self._sealed:
                return
            super(class_w, self).__init__(*args, **kwargs)
            self._sealed = True

    class_w.__name__ = class_.__name__
    return cast(type[C], class_w)


@singleton
class Config:

    _ENV: dict[str, str | None] = {}
    _ENV_SRC: Any = None
    use_docker = False

    def startup(self, args: AutoM4bArgs | None = None):
        from src.lib.term import print_aqua, print_dark_grey, print_grey

        self._ARGS = args or AutoM4bArgs()

        with self.load_env() as env_msg:
            if self.SLEEPTIME and not self.TEST:
                time.sleep(min(2, self.SLEEPTIME / 2))
            if not self.PID_FILE.is_file():
                self.PID_FILE.touch()
                current_local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with self.PID_FILE.open("a") as f:
                    f.write(
                        f"auto-m4b started at {current_local_time}, watching {self.inbox_dir}\n"
                    )
                print_aqua("\nStarting auto-m4b...")
                if self.TEST and self.DEBUG:
                    print_amber("TEST + DEBUG modes on")
                elif self.TEST:
                    print_amber("TEST mode on")
                elif self.DEBUG:
                    print_amber("DEBUG mode on")
                print_grey(self.info_str)
                if env_msg:
                    print_dark_grey(env_msg)

        nl()

        self.clean()

        self.clear_cached_attrs()
        self.check_dirs()
        self.check_m4b_tool()

    @cached_property
    def on_complete(self):
        return cast(OnComplete, os.getenv("ON_COMPLETE", "move"))

    @cached_property
    def OVERWRITE_EXISTING(self):
        return parse_bool(os.getenv("OVERWRITE_EXISTING", False))

    # @cached_property
    # def overwrite_arg(self):
    #     return "--overwrite" if self.OVERWRITE_EXISTING else "--no-overwrite"

    @cached_property
    def default_overwrite_mode(self) -> OverwriteMode:
        return "overwrite" if self.OVERWRITE_EXISTING else "skip"

    @cached_property
    def NO_FIX(self) -> bool:
        if self.ARGS.no_fix or self.ARGS.debug:
            return True
        return parse_bool(os.getenv("NO_FIX", False))

    @cached_property
    def CPU_CORES(self) -> int:
        return int(os.getenv("CPU_CORES", cpu_count()))

    @cached_property
    def SLEEPTIME(self):
        return float(os.getenv("SLEEPTIME", DEFAULT_SLEEPTIME))

    @property
    def sleeptime_friendly(self):
        """If it can be represented as a whole number, do so as {number}s
        otherwise, show as a float rounded to 1 decimal place, e.g. 0.1s"""
        return (
            f"{int(self.SLEEPTIME)}s"
            if self.SLEEPTIME.is_integer()
            else f"{self.SLEEPTIME:.1f}s"
        )

    @cached_property
    def MAX_CHAPTER_LENGTH(self):
        """Max chapter length in seconds, default is 15-30m, and is converted to m4b-tool's seconds format."""
        max_chapter_length = os.getenv("MAX_CHAPTER_LENGTH", "15,30")
        return ",".join(str(int(x) * 60) for x in max_chapter_length.split(","))

    @cached_property
    def max_chapter_length_friendly(self):
        return (
            "-".join(
                [str(int(int(t) / 60)) for t in self.MAX_CHAPTER_LENGTH.split(",")]
            )
            + "m"
        )

    @cached_property
    def SKIP_COVERS(self):
        return parse_bool(os.getenv("SKIP_COVERS", False))

    # @cached_property
    # def no_cover_image_arg(self):
    #     return "--no-cover-image" if self.should_skip_covers else ""

    @cached_property
    def USE_FILENAMES_AS_CHAPTERS(self):
        return parse_bool(os.getenv("USE_FILENAMES_AS_CHAPTERS", False))

    # @cached_property
    # def use_filenames_as_chapters_arg(self):
    #     return "--use-filenames-as-chapters" if self.use_filenames_as_chapters else ""

    @cached_property
    def VERSION(self):
        return os.getenv("VERSION", "stable")

    @cached_property
    def _m4b_tool(self):
        return ["m4b-tool-pre"] if self.VERSION == "latest" else ["m4b-tool"]

    @property
    def m4b_tool(self):
        return " ".join(self._m4b_tool)

    @overload
    def _load_env(self, key: str, default: Path, allow_empty: bool = ...) -> Path: ...

    @overload
    def _load_env(
        self,
        key: str,
        default: Path | None = None,
        allow_empty: Literal[True] = True,
    ) -> Path | None: ...

    @overload
    def _load_env(
        self,
        key: str,
        default: Path | None = None,
        allow_empty: Literal[False] = False,
    ) -> Path: ...

    def _load_env(
        self, key: str, default: Path | None = None, allow_empty: bool = True
    ) -> Path | None:
        env = os.getenv(key, self.ENV.get(key, None))
        path = Path(env).expanduser() if env else default
        if not path and not allow_empty:
            raise EnvironmentError(
                f"{key} is not set, please make sure to set it in a .env file or as an ENV var"
            )
        return path

    # def parse_args(self):
    #     args = parser.parse_known_args()[0]
    #     self._ARGS = AutoM4bArgs(
    #         env=args.env,
    #         debug=args.debug,
    #         test=args.test,
    #         max_loops=args.loops,
    #         no_fix=args.no_fix,
    #     )

    @property
    def ARGS(self) -> AutoM4bArgs:
        return self._ARGS

    @property
    def ENV(self):
        return self._ENV

    @cached_property
    def TEST(self):
        if self.ARGS.test:
            return True
        return parse_bool(os.getenv("TEST", False))

    @cached_property
    def DEBUG(self):
        if self.ARGS.debug:
            return True
        return parse_bool(os.getenv("DEBUG", False))

    # @cached_property
    # def debug_arg(self):
    #     return "--debug" if self.DEBUG == "Y" else "-q"

    @property
    def MAX_LOOPS(self):
        return self.ARGS.max_loops if self.ARGS.max_loops else -1

    @cached_property
    def info_str(self):
        info = f"{self.CPU_CORES} CPU cores / "
        info += f"{self.sleeptime_friendly} sleep / "
        info += f"Max chapter length: {self.max_chapter_length_friendly} / "
        info += f"Cover images: {'off' if self.SKIP_COVERS else 'on'} / "
        if self.VERSION == "latest":
            info += "m4b-tool: latest (preview)"
        else:
            info += "m4b-tool: stable"

        return info

    @cached_property
    def AUDIO_EXTS(self):
        if env_audio_exts := os.getenv("AUDIO_EXTS"):
            global AUDIO_EXTS
            AUDIO_EXTS = env_audio_exts.split(",")
        return AUDIO_EXTS

    @cached_property
    def OTHER_EXTS(self):
        global OTHER_EXTS
        return OTHER_EXTS

    @cached_property
    def IGNORE_FILES(self):
        global IGNORE_FILES
        return IGNORE_FILES

    @cached_property
    def TMP_DIR(self):
        return Path(tempfile.gettempdir()) / "auto-m4b"

    @cached_property
    def MAKE_BACKUP(self):
        return parse_bool(os.getenv("MAKE_BACKUP", False))

    @cached_property
    def backup_arg(self):
        return "--backup" if self.MAKE_BACKUP == "Y" else ""

    @cached_property
    def inbox_dir(self):
        return self._load_env("INBOX_FOLDER", allow_empty=False)

    @cached_property
    def converted_dir(self):
        return self._load_env("CONVERTED_FOLDER", allow_empty=False)

    @cached_property
    def archive_dir(self):
        return self._load_env("ARCHIVE_FOLDER", allow_empty=False)

    @cached_property
    def fix_dir(self):
        return self._load_env("FIX_FOLDER", allow_empty=False)

    @cached_property
    def backup_dir(self):
        return self._load_env("BACKUP_FOLDER", allow_empty=False)

    @cached_property
    def build_dir(self):
        return self._load_env("BUILD_FOLDER", self.TMP_DIR / "build")

    @cached_property
    def merge_dir(self):
        return self._load_env("MERGE_FOLDER", self.TMP_DIR / "merge")

    @cached_property
    def trash_dir(self):
        return self._load_env("TRASH_FOLDER", self.TMP_DIR / "delete")

    @cached_property
    def GLOBAL_LOG_FILE(self):
        log_file = self.converted_dir / "auto-m4b.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.touch(exist_ok=True)
        return log_file

    @cached_property
    def PID_FILE(self):
        pid_file = self.TMP_DIR / "running"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        return pid_file

    def clean(self):
        from src.lib.fs_utils import clean_dir

        # Pre-clean working folders
        clean_dir(self.merge_dir)
        clean_dir(self.build_dir)
        clean_dir(self.trash_dir)

    def check_dirs(self):

        dirs = [
            self.inbox_dir,
            self.converted_dir,
            self.archive_dir,
            self.fix_dir,
            self.backup_dir,
            self.build_dir,
            self.merge_dir,
            self.trash_dir,
        ]

        for d in dirs:
            ensure_dir_exists_and_is_writable(d)

    def clear_cached_attrs(self):
        for prop in [d for d in dir(self) if not d.startswith("_")]:
            try:
                delattr(self, prop)
            except AttributeError:
                pass

    def check_m4b_tool(self):

        has_native_m4b_tool = bool(shutil.which(self.m4b_tool))
        if has_native_m4b_tool:
            return True

        # docker images -q sandreas/m4b-tool:latest
        has_docker = bool(shutil.which("docker"))
        docker_image_exists = has_docker and bool(
            subprocess.check_output(
                ["docker", "images", "-q", "sandreas/m4b-tool:latest"]
            ).strip()
        )
        if has_docker and docker_image_exists:

            uid = os.getuid()
            gid = os.getgid()
            # Set the m4b_tool to the docker image
            self._m4b_tool = [
                "docker",
                "run",
                "-it",
                "--rm",
                "-u",
                f"{uid}:{gid}",
                "-v",
                f"{self.merge_dir}:/mnt",
                "sandreas/m4b-tool:latest",
            ]

            self.use_docker = True
            return True

        raise RuntimeError(
            f"{{{{{self._m4b_tool}}}}} is not installed or not in PATH, please install it and try again\n     (See https://github.com/sandreas/m4b-tool)\n\n     If you are using Docker, make sure the image 'sandreas/m4b-tool:latest' is available and you have added an appropriate alias (hint: run ./install-m4b-tool.sh)."
        )

    @contextmanager
    def load_env(self):
        msg = ""
        if self.ARGS.env:
            if self._ENV_SRC != self.ARGS.env:
                msg = f"Loading ENV from {self.ARGS.env}"
            self._ENV_SRC = self.ARGS.env
            self._ENV = load_env(self.ARGS.env)
        elif self.TEST:
            env_file = get_git_root() / ".env.test"
            if self._ENV_SRC != env_file:
                msg = f"Loading test ENV from {env_file}"
            self._ENV_SRC = env_file
            self._ENV = load_env(env_file)
        else:
            self._ENV = {}
        yield msg

    def reload(self):
        self.__init__()
        self.clear_cached_attrs()
        self.load_env()


cfg = Config()

__all__ = ["cfg"]
import_debug.bug.pop("src/lib/config.py")