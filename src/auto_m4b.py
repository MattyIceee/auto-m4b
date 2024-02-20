import time

from lib.term import print_error

from src.lib import run
from src.lib.config import cfg, Config

LOOP_COUNT = 0
EXIT_CODE = 0


def handle_err(e: Exception):
    print_error(f"Error: {e}")
    global EXIT_CODE
    EXIT_CODE = 1


def app(max_loops: int = -1):
    global LOOP_COUNT, EXIT_CODE
    try:
        Config.startup()
        run.print_launch_and_set_running()
        while max_loops == -1 or LOOP_COUNT < max_loops:
            try:
                run.process_inbox()
            except Exception as e:
                handle_err(e)
            finally:
                time.sleep(cfg.SLEEPTIME)
                LOOP_COUNT += 1
    except Exception as e:
        handle_err(e)
    finally:
        cfg.PID_FILE.unlink(missing_ok=True)

    exit(EXIT_CODE)


if __name__ == "__main__":
    app()
