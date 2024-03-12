import sys
import traceback

import import_debug

from src.lib.typing import copy_kwargs_omit_first_arg

import_debug.bug.push("src/auto_m4b.py")
import time

from src.lib import run
from src.lib.config import AutoM4bArgs, cfg
from src.lib.term import print_error, print_red

LOOP_COUNT = 0


def handle_err(e: Exception):
    if "pytest" in sys.modules:
        raise e
    elif cfg.DEBUG:
        print_red(f"\n{traceback.format_exc()}")
    else:
        print_error(f"Error: {e}")
    time.sleep(cfg.SLEEPTIME)


@copy_kwargs_omit_first_arg(AutoM4bArgs.__init__)
def app(**kwargs):
    args = AutoM4bArgs(**kwargs)
    infinite_loop = args.max_loops == -1
    first_time = True
    global LOOP_COUNT
    try:
        cfg.startup(args)
        while infinite_loop or LOOP_COUNT < args.max_loops:
            try:
                run.process_inbox(first_run=first_time)
            finally:
                LOOP_COUNT += 1
                first_time = False
                if infinite_loop or LOOP_COUNT < args.max_loops:
                    time.sleep(cfg.SLEEPTIME)
    except Exception as e:
        handle_err(e)
    finally:
        cfg.PID_FILE.unlink(missing_ok=True)

    import_debug.bug.pop("src/auto_m4b.py")


if __name__ == "__main__":
    app()
