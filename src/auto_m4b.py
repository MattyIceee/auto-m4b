import sys
import traceback

import import_debug
from tinta import Tinta

import_debug.bug.push("src/auto_m4b.py")
import time

from src.lib import run
from src.lib.config import cfg
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


def app(max_loops: int = cfg.MAX_LOOPS):
    global LOOP_COUNT, EXIT_CODE
    try:
        cfg.startup()
        while max_loops == -1 or LOOP_COUNT < max_loops:
            try:
                run.process_inbox()
            finally:
                LOOP_COUNT += 1
                if max_loops != -1 and LOOP_COUNT < max_loops:
                    time.sleep(cfg.SLEEPTIME)
    except Exception as e:
        handle_err(e)
    finally:
        cfg.PID_FILE.unlink(missing_ok=True)

    import_debug.bug.pop("src/auto_m4b.py")


if __name__ == "__main__":
    app()
