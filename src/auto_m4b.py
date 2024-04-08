import sys
import time
import traceback
from contextlib import contextmanager

from src.lib import run
from src.lib.config import AutoM4bArgs, cfg
from src.lib.term import print_error, print_red
from src.lib.typing import copy_kwargs_omit_first_arg

LOOP_COUNT = 0


def handle_err(e: Exception):

    from src.lib.config import cfg

    with open(cfg.FATAL_FILE, "a") as f:
        f.write(f"Fatal Error: {e}")

    if cfg.DEBUG:
        print_red(f"\n{traceback.format_exc()}")
    else:
        print_error(f"Error: {e}")

    if "pytest" in sys.modules:
        raise e

    time.sleep(cfg.SLEEP_TIME)


@contextmanager
def use_error_handler():
    try:
        yield
    except Exception as e:
        handle_err(e)


@copy_kwargs_omit_first_arg(AutoM4bArgs.__init__)
def app(**kwargs):
    args = AutoM4bArgs(**kwargs)
    infinite_loop = args.max_loops == -1
    global LOOP_COUNT
    LOOP_COUNT = 0
    with use_error_handler():
        cfg.startup(args)
        while infinite_loop or LOOP_COUNT < args.max_loops:
            try:
                run.process_inbox()
            finally:
                LOOP_COUNT += 1
                if infinite_loop or LOOP_COUNT < args.max_loops:
                    time.sleep(cfg.SLEEP_TIME)


if __name__ == "__main__":
    app()
