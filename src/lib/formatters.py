import humanize
import import_debug

import_debug.bug.push("src/lib/formatters.py")
from datetime import datetime

import inflect
import numpy as np


def log_date() -> str:
    current_tz = datetime.now().astimezone().tzinfo
    return datetime.now(tz=current_tz).strftime("%Y-%m-%d %H:%M:%S%z")


def friendly_date() -> str:
    return datetime.now().strftime("%I:%M:%S %p, %a, %d %b %Y")


def round_bitrate(bitrate: int) -> int:
    standard_bitrates = np.array(
        [32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
    )  # see https://superuser.com/a/465660/254022
    min_bitrate = standard_bitrates[0]

    bitrate_k = bitrate // 1000

    # get the lower and upper bitrates (inclusive) from the standard_bitrates array
    lower_bitrate = standard_bitrates[standard_bitrates <= bitrate_k][-1]
    upper_bitrate = (
        standard_bitrates[standard_bitrates >= bitrate_k][0]
        if any(standard_bitrates >= bitrate_k)
        else None
    )

    # should never happen, but if the upper bitrate is empty, then the bitrate is higher
    # than the highest standard bitrate, so return the highest standard bitrate
    if upper_bitrate is None:
        closest_bitrate = standard_bitrates[-1]
    else:
        # get 25% of the difference between lower and upper
        diff = (upper_bitrate - lower_bitrate) // 4

        # if bitrate_k + diff is closer to bitrate_k than bitrate_k - diff, use upper bitrate
        closest_bitrate = (
            upper_bitrate if bitrate_k + diff >= bitrate_k else lower_bitrate
        )

    # if the closest bitrate is less than the minimum bitrate, use the minimum bitrate
    if closest_bitrate < min_bitrate:
        closest_bitrate = min_bitrate

    return closest_bitrate * 1000


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


import_debug.bug.pop("src/lib/formatters.py")
