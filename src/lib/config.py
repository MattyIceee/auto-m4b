import argparse
import os
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from functools import cached_property
from multiprocessing import cpu_count
from pathlib import Path
from typing import Any, cast, Literal, overload, TypeVar

from src.lib.misc import get_git_root, load_env, parse_bool, to_json
from src.lib.term import nl, print_amber
from src.lib.typing import ExifWriter, OverwriteMode

DEFAULT_SLEEPTIME = 10  # Set this to your default sleep time
AUDIO_EXTS = [".mp3", ".m4a", ".m4b", ".wma"]
OTHER_EXTS = [
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".webp",
    ".heic",
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
    "Desktop.ini",
    "ehthumbs.db",
    "Thumbs.db",
    "@eaDir",
]

WORKING_DIRS = [
    "BUILD_FOLDER",
    "MERGE_FOLDER",
    "TRASH_FOLDER",
]

OnComplete = Literal["move", "delete", "test_do_nothing"]

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
parser.add_argument(
    "--match-name",
    help="Only process books that contain this string in their filename. May be a regex pattern, but \\ must be escaped → '\\\\'. Default is None.",
    type=str,
    default=None,
)

T = TypeVar("T", bound=object)
D = TypeVar("D")


@overload
def pick(a: T, b) -> T: ...


@overload
def pick(a: T, b, default: None = None) -> T: ...


@overload
def pick(a, b, default: T) -> T: ...


def pick(a: T, b, default: D = None) -> T | D:
    if a is not None:
        return cast(T | D, a)
    if b is not None:
        return b
    return default


class AutoM4bArgs:
    env: Path | None
    debug: bool
    test: bool
    max_loops: int
    no_fix: bool
    match_name: str | None

    def __init__(
        self,
        env: Path | None = None,
        debug: bool | None = None,
        test: bool | None = None,
        max_loops: int | None = None,
        no_fix: bool | None = None,
        match_name: str | None = None,
    ):
        args = parser.parse_known_args()[0]

        self.env = pick(env, args.env)
        self.debug = pick(debug, args.debug, False)
        self.test = pick(test, args.test, False)
        self.max_loops = pick(max_loops, args.max_loops, -1)
        self.no_fix = pick(no_fix, args.no_fix, False)
        self.match_name = pick(match_name, args.match_name)

    def __str__(self) -> str:
        return to_json(self.__dict__)

    def __repr__(self) -> str:
        return f"AutoM4bArgs({self.__str__()})"


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
    _USE_DOCKER = False

    def __init__(self):
        """Do a first load of the environment variables in case we need them before the app runs."""
        self.load_env(quiet=True)

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
        if self.ARGS.test:
            return "test_do_nothing"
        return cast(OnComplete, os.getenv("ON_COMPLETE", "move"))

    @cached_property
    def OVERWRITE_MODE(self) -> OverwriteMode:
        return (
            "overwrite"
            if parse_bool(os.getenv("OVERWRITE_EXISTING", False))
            else "skip"
        )

    # @cached_property
    # def overwrite_arg(self):
    #     return "--overwrite" if self.OVERWRITE_EXISTING else "--no-overwrite"

    # @cached_property
    # def default_overwrite_mode(self) -> OverwriteMode:
    #     return "overwrite" if self.OVERWRITE_EXISTING else "skip"

    @cached_property
    def NO_FIX(self) -> bool:
        if self.ARGS.no_fix or self.ARGS.debug:
            return True
        return parse_bool(os.getenv("NO_FIX", False))

    @cached_property
    def NO_ASCII(self) -> bool:
        return parse_bool(os.getenv("NO_ASCII", False))

    @cached_property
    def MATCH_NAME(self) -> str | None:
        """Only process books that contain this string in their filename. May be a regex pattern,
        but \\ must be escaped → '\\\\'. Default is None. This is primarily for testing, but can
        be used to filter books or directories."""
        if self.ARGS.match_name:
            return self.ARGS.match_name
        match_name = os.getenv("MATCH_NAME", None)
        if str(match_name).lower() in ["none", ""]:
            return None
        return match_name

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
        return os.getenv("VERSION", "latest")

    @cached_property
    def m4b_tool_version(self):
        """Runs m4b-tool --version"""
        return (
            subprocess.check_output(f"{self.m4b_tool} m4b-tool --version", shell=True)
            .decode()
            .strip()
        )

    @cached_property
    def _m4b_tool(self):
        """Note: if you are using the Dockerized version of m4b-tool, this will always be `m4b-tool`, because the pre-release version is baked into the image."""
        return ["m4b-tool"]

    @property
    def m4b_tool(self):
        return " ".join(self._m4b_tool)

    @overload
    def _load_path_env(
        self, key: str, default: Path, allow_empty: bool = ...
    ) -> Path: ...

    @overload
    def _load_path_env(
        self,
        key: str,
        default: Path | None = None,
        allow_empty: Literal[True] = True,
    ) -> Path | None: ...

    @overload
    def _load_path_env(
        self,
        key: str,
        default: Path | None = None,
        allow_empty: Literal[False] = False,
    ) -> Path: ...

    def _load_path_env(
        self, key: str, default: Path | None = None, allow_empty: bool = True
    ) -> Path | None:
        v = os.getenv(key, self.ENV.get(key, None))
        if self.ARGS.env:
            env = load_env(self.ARGS.env)
            v = env.get(key, v)
        path = Path(v).expanduser() if v else default
        if not path and not allow_empty:
            raise EnvironmentError(
                f"{key} is not set, please make sure to set it in a .env file or as an ENV var"
            )
        return path.resolve() if path else None

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
        if not hasattr(self, "_ARGS"):
            self._ARGS = AutoM4bArgs()
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
        info += f"Max ch. length: {self.max_chapter_length_friendly} / "
        # info += f"Cover images: {"off" if self.SKIP_COVERS else "on"} / "
        if self.USE_DOCKER:
            info += f"{self.m4b_tool_version} (Docker)"
        elif self.VERSION == "{self.m4b_tool_version}":
            info += f"{self.m4b_tool_version}"
        else:
            info += f"{self.m4b_tool_version}"

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
    def MAKE_BACKUP(self):
        return parse_bool(os.getenv("MAKE_BACKUP", False))

    @cached_property
    def FLATTEN_MULTI_DISC_BOOKS(self):
        return parse_bool(os.getenv("FLATTEN_MULTI_DISC_BOOKS", False))

    @cached_property
    def EXIF_WRITER(self) -> ExifWriter:
        return cast(ExifWriter, os.getenv("EXIF_WRITER", "eyed3"))

    @cached_property
    def USE_DOCKER(self):
        self.check_m4b_tool()
        return self._USE_DOCKER

    @cached_property
    def docker_path(self):
        env_path = self._load_path_env("DOCKER_PATH", allow_empty=True)
        return env_path or shutil.which("docker")

    @cached_property
    def inbox_dir(self):
        return self._load_path_env("INBOX_FOLDER", allow_empty=False)

    @cached_property
    def converted_dir(self):
        return self._load_path_env("CONVERTED_FOLDER", allow_empty=False)

    @cached_property
    def archive_dir(self):
        return self._load_path_env("ARCHIVE_FOLDER", allow_empty=False)

    @cached_property
    def fix_dir(self):
        return self._load_path_env("FIX_FOLDER", allow_empty=False)

    @cached_property
    def backup_dir(self):
        return self._load_path_env("BACKUP_FOLDER", allow_empty=False)

    @cached_property
    def tmp_dir(self):
        t = Path(tempfile.gettempdir()).resolve() / "auto-m4b"
        t.mkdir(parents=True, exist_ok=True)
        return t

    @cached_property
    def working_dir(self):
        """The working directory for auto-m4b, defaults to /<tmpdir>/auto-m4b."""
        d = self._load_path_env("WORKING_FOLDER", None, allow_empty=True)
        if not d:
            return self.tmp_dir
        d.mkdir(parents=True, exist_ok=True)
        return d

    @cached_property
    def build_dir(self):
        return self.working_dir / "build"

    @cached_property
    def merge_dir(self):
        return self.working_dir / "merge"

    @cached_property
    def trash_dir(self):
        return self.working_dir / "trash"

    @cached_property
    def GLOBAL_LOG_FILE(self):
        log_file = self.converted_dir / "auto-m4b.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.touch(exist_ok=True)
        return log_file

    @cached_property
    def PID_FILE(self):
        pid_file = self.tmp_dir / "running.pid"
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
            self.working_dir,
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
        has_docker = bool(self.docker_path)
        docker_exe = self.docker_path or "docker"
        docker_image_exists = has_docker and bool(
            subprocess.check_output(
                [docker_exe, "images", "-q", "sandreas/m4b-tool:latest"]
            ).strip()
        )
        docker_ready = has_docker and docker_image_exists
        env_use_docker = bool(
            os.getenv("USE_DOCKER", self.ENV.get("USE_DOCKER", False))
        )
        if docker_ready and env_use_docker:
            uid = os.getuid()
            gid = os.getgid()
            is_tty = os.isatty(0)
            # Set the m4b_tool to the docker image
            # create working_dir if it does not exist
            self.working_dir.mkdir(parents=True, exist_ok=True)
            self._m4b_tool = [
                c
                for c in [
                    str(docker_exe),
                    "run",
                    "-it" if is_tty else "",
                    "--rm",
                    "-u",
                    f"{uid}:{gid}",
                    "-v",
                    f"{self.working_dir}:/mnt:rw",
                    "sandreas/m4b-tool:latest",
                ]
                if c
            ]

            self._USE_DOCKER = True
            return True

        elif env_use_docker:
            if not has_docker:
                if self.docker_path:
                    raise RuntimeError(
                        f"Could not find 'docker' executable at {self.docker_path}, please ensure Docker is in your PATH or set DOCKER_PATH to the correct path"
                    )
                raise RuntimeError(
                    f"Could not find 'docker' in PATH, please install Docker and try again, or set USE_DOCKER to N to use the native m4b-tool (if installed)"
                )
            elif not docker_image_exists:
                raise RuntimeError(
                    f"Could not find the image 'sandreas/m4b-tool:latest', run\n\n $ docker pull sandreas/m4b-tool:latest\n  # or\n $ ./install-m4b-tool.sh\n\nand try again, or set USE_DOCKER to N to use the native m4b-tool (if installed)"
                )
        else:
            raise RuntimeError(
                f"Could not find '{self.m4b_tool}' in PATH, please install it and try again (see https://github.com/sandreas/m4b-tool).\nIf you are using Docker, make sure the image 'sandreas/m4b-tool:latest' is available, and you've aliased m4b-tool to run the container.\nFor easy Docker setup, run:\n\n$ ./install-m4b-tool.sh"
            )

    @contextmanager
    def load_env(self, quiet: bool = False):
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
        yield "" if quiet else msg

    def reload(self):
        self.__init__()
        self.clear_cached_attrs()
        self.load_env()


cfg = Config()

__all__ = ["cfg"]
