import sys
import traceback

import import_debug
from tinta import Tinta

from src.lib.typing import copy_kwargs_classless

import_debug.bug.push("src/auto_m4b.py")
import time

from src.lib import run
from src.lib.config import AutoM4bArgs, cfg
from src.lib.term import print_error

LOOP_COUNT = 0


def handle_err(e: Exception):
    if cfg.DEBUG:
        Tinta().red(traceback.format_exc()).print()
        exit(1)
    elif cfg.TEST or "pytest" in sys.modules:
        raise e
    else:
        print_error(f"Error: {e}")


@copy_kwargs_classless(AutoM4bArgs.__init__)
def app(**kwargs):

    args = AutoM4bArgs(**kwargs)
    print(args)
    global LOOP_COUNT, EXIT_CODE
    try:
        cfg.startup(args)
        while args.max_loops == -1 or LOOP_COUNT < args.max_loops:
            try:
                run.process_inbox()
            finally:
                LOOP_COUNT += 1
                if args.max_loops != -1 and LOOP_COUNT < args.max_loops:
                    time.sleep(cfg.SLEEPTIME)
    except Exception as e:
        handle_err(e)
    finally:
        cfg.PID_FILE.unlink(missing_ok=True)

    import_debug.bug.pop("src/auto_m4b.py")


if __name__ == "__main__":
    app()