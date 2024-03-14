from datetime import datetime
from pathlib import Path

import cachetools.func
import humanize
import inflect

from src.lib.typing import MEMO_TTL, STANDARD_BITRATES


def log_date() -> str:
    current_tz = datetime.now().astimezone().tzinfo
    return datetime.now(tz=current_tz).strftime("%Y-%m-%d %H:%M:%S%z")


def friendly_date() -> str:
    return datetime.now().strftime("%I:%M:%S %p, %a, %d %b %Y")


@cachetools.func.ttl_cache(maxsize=128, ttl=MEMO_TTL)
def get_nearest_standard_bitrate(bitrate: int) -> int:
    min_bitrate = STANDARD_BITRATES[0]

    bitrate_k = bitrate // 1000 if bitrate > 999 else bitrate

    if bitrate_k in STANDARD_BITRATES:
        return bitrate

    # get the lower and upper bitrates (inclusive) from the STANDARD_BITRATES array
    lower_bitrate = STANDARD_BITRATES[STANDARD_BITRATES <= bitrate_k][-1]
    upper_bitrate = (
        STANDARD_BITRATES[STANDARD_BITRATES >= bitrate_k][0]
        if any(STANDARD_BITRATES >= bitrate_k)
        else None
    )

    # should never happen, but if the upper bitrate is empty, then the bitrate is higher
    # than the highest standard bitrate, so return the highest standard bitrate
    if upper_bitrate is None:
        closest_bitrate = STANDARD_BITRATES[-1]
    else:
        # get 25% of the difference between lower and upper
        diff = (upper_bitrate - lower_bitrate) // 4

        # if bitrate_k + diff is closer to bitrate_k than bitrate_k - diff, use upper bitrate
        closest_bitrate = (
            upper_bitrate if bitrate_k + diff >= bitrate_k else lower_bitrate
        )

    closest_bitrate = int(closest_bitrate)

    # if the closest bitrate is less than the minimum bitrate, use the minimum bitrate
    if closest_bitrate < min_bitrate:
        closest_bitrate = min_bitrate

    return closest_bitrate * 1000


def human_bitrate(file: Path) -> str:
    from src.lib.ffmpeg_utils import get_bitrate_py, is_variable_bitrate

    std, actual = get_bitrate_py(file)
    if is_variable_bitrate(file):
        return f"~{round(actual / 1000)} kb/s"
    return f"{round(std / 1000)} kb/s"


def human_size(size: int) -> str:
    f = "%.2f" if size >= 1024**3 else "%d"
    return humanize.naturalsize(size, format=f)


def pluralize(count: int, singular: str, plural: str | None = None) -> str:
    p = inflect.engine()
    if count == 1:
        return singular
    elif count == 0 or count > 1:
        return p.plural(singular) if plural is None else plural
    else:
        return f"{singular}(s)"
