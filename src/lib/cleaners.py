import re


def strip_html_tags(s: str) -> str:
    """Replaces all html tags including <open> and </close> tags, and <autoclose /> tags with an empty string"""
    return re.sub(r"</?\w+\s*/?>", "", s, flags=re.DOTALL)


def strip_disc_number(s: str) -> str:
    """Takes a string and removes any disc/CD number found in the string"""
    return re.sub(r"\W*?-?\W*?[\(\[]*(disc|cd)\W*\d+[\)\]]*", "", s, flags=re.I).strip()


def strip_part_number(s: str) -> str:
    """Takes a string and removes any part number found in the string"""
    return re.sub(r"\W*?-?\W*?[\(\[]*p(ar)?t\W*\d+[\)\]]*", "", s, flags=re.I).strip()


def fix_smart_quotes(s: str) -> str:
    """Takes a string and replaces smart quotes with regular quotes"""
    trans = str.maketrans("‘’‚‛′′“”„‟″″", "''''''\"\"\"\"\"\"")
    return s.translate(trans)


urlencode_map = {
    "%20": " ",
    "%2C": ",",
    "%2F": "/",
    "%3A": ":",
    "%40": "@",
    "%3D": "=",
    "%26": "&",
    "%3F": "?",
    "&amp;": "&",
    "&quot;": '"',
    "&apos;": "'",
    "&lt;": "<",
    "&gt;": ">",
    "&nbsp;": " ",
    "&mdash;": "—",
    "&ndash;": "–",
    "&copy;": "©",
}


def un_urlencode(s: str) -> str:
    """Looks for common url-encoded characters and replaces them with their ascii equivalent (case insensitive)"""
    for k, v in urlencode_map.items():
        if k.lower() in s.lower():
            # replace all instances of the key with the value
            s = re.sub(re.escape(k), v, s, flags=re.I)
    return s


def clean_string(s: str, strip_disc_no: bool = True, strip_part_no: bool = True) -> str:
    """Cleans a string by stripping html tags, smart quotes, and url-encoded characters"""
    s = strip_html_tags(s)
    s = fix_smart_quotes(s)
    s = un_urlencode(s)
    if strip_disc_no:
        s = strip_disc_number(s)
    if strip_part_no:
        s = strip_part_number(s)
    return s
