import functools
import inspect
from collections.abc import Callable
from typing import Any, cast, Concatenate, Literal, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

AudiobookFmt = Literal["m4b", "mp3", "m4a", "wma"]
Operation = Literal["move", "copy"]
OverwriteMode = Literal["skip", "overwrite", "overwrite-silent"]
PathType = Literal["dir", "file"]
SizeFmt = Literal["bytes", "human"]
DirName = Literal[
    "inbox", "converted", "archive", "fix", "backup", "build", "merge", "trash"
]


# Source: https://stackoverflow.com/a/71968448/1214800
def copy_kwargs(func: Callable[P, R]) -> Callable[..., Callable[P, R]]:
    """Decorator does nothing but casts the original function to match the given function signature"""

    @functools.wraps(func, updated=())
    def _cast_func(_func: Callable[..., Any]) -> Callable[P, R]:
        return cast(Callable[P, R], _func)

    if inspect.isfunction(func):
        return _cast_func

    raise RuntimeError("You must pass a function to this decorator.")


F = TypeVar("F")


def copy_kwargs_classless(
    func: Callable[Concatenate[F, P], R],
) -> Callable[..., Callable[P, R]]:
    """Decorator does nothing but casts the original function to match the given function signature, but omits the first parameter"""

    @functools.wraps(func, updated=())
    def _cast_func(_func: Callable[..., Any]) -> Callable[P, R]:
        return cast(Callable[P, R], _func)

    if inspect.isfunction(func):
        return _cast_func

    raise RuntimeError("You must pass a function to this decorator.")
