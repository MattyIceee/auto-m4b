import pytest


@pytest.mark.parametrize(
    "test_str, expected",
    [
        ("disc 1", ""),
        ("Disc 1", ""),
        ("CD 1", ""),
        ("cd1", ""),
        ("CD 2", ""),
        ("cd.3", ""),
        ("(Disc 4)", ""),
        (" - disc 5", ""),
        (
            "The Last Guardian (Disc 01) - Track07.mp3",
            "The Last Guardian - Track07.mp3",
        ),
        (
            "The Last Guardian - Disc 01 - Track07.mp3",
            "The Last Guardian - Track07.mp3",
        ),
        (
            "The Last Guardian (Disc 01)",
            "The Last Guardian",
        ),
        (
            "The Last Guardian - Disc 01",
            "The Last Guardian",
        ),
        (
            "The Last Guardian, CD01",
            "The Last Guardian",
        ),
    ],
)
def test_strip_disc_number(test_str: str, expected: str):
    from src.lib.cleaners import strip_disc_number

    assert strip_disc_number(test_str) == expected


@pytest.mark.parametrize(
    "test_str, expected",
    [
        ("part 1", ""),
        ("pt 08", ""),
        ("pt. 42", ""),
        ("Part 1", ""),
        ("Part 06", ""),
        ("Part 009", ""),
        ("pt1", ""),
        ("PT 2", ""),
        ("(Part 4)", ""),
        (" - part 5", ""),
        (
            "The Last Guardian (Part 01) - Track07.mp3",
            "The Last Guardian - Track07.mp3",
        ),
        (
            "The Last Guardian - Part 01 - Track07.mp3",
            "The Last Guardian - Track07.mp3",
        ),
        (
            "The Last Guardian (Part 01)",
            "The Last Guardian",
        ),
        (
            "The Last Guardian - Part 01",
            "The Last Guardian",
        ),
        (
            "The Last Guardian, PT.01",
            "The Last Guardian",
        ),
        (
            "The Last Guardian, pt 1",
            "The Last Guardian",
        ),
    ],
)
def test_strip_part_number(test_str: str, expected: str):
    from src.lib.cleaners import strip_part_number

    assert strip_part_number(test_str) == expected


@pytest.mark.parametrize(
    "test_str, expected",
    [
        ("That's to runnin' scared", "That's to runnin' scared"),
        ("That‘s to runnin’ scared", "That's to runnin' scared"),
        ("That’s to runnin’ scared", "That's to runnin' scared"),
        ('"Hello," she said.', '"Hello," she said.'),
        ("‘Hello,’ she said.", "'Hello,' she said."),
        ("’Hello,’ she said.", "'Hello,' she said."),
        ("‚Hello,‘ she said.", "'Hello,' she said."),
        ("‛Hello,‛ she said.", "'Hello,' she said."),
        ("′Hello,′ she said.", "'Hello,' she said."),
        ("‘Hello,’ she said.", "'Hello,' she said."),
        ("“Hello,” she said.", '"Hello," she said.'),
        ("”Hello,” she said.", '"Hello," she said.'),
        ("„Hello,“ she said.", '"Hello," she said.'),
        ("‟Hello,‟ she said.", '"Hello," she said.'),
        ("″Hello,″ she said.", '"Hello," she said.'),
        ("″Hello,″ she said.", '"Hello," she said.'),
    ],
)
def test_fix_smart_quotes(test_str: str, expected: str):
    from src.lib.cleaners import fix_smart_quotes

    assert fix_smart_quotes(test_str) == expected


@pytest.mark.parametrize(
    "test_str, expected",
    [
        ("hello%20world", "hello world"),
        ("hello%2Cworld", "hello,world"),
        ("hello%2Fworld", "hello/world"),
        ("hello%3Aworld", "hello:world"),
        ("hello%40world", "hello@world"),
        ("hello%3Dworld", "hello=world"),
        ("hello%26world", "hello&world"),
        ("hello%3Fworld", "hello?world"),
        ("hello&amp;world", "hello&world"),
        ("hello&quot;world", 'hello"world'),
        ("h&quot;&quot;w&quot;", 'h""w"'),
        ("hello&apos;world", "hello'world"),
        ("hello&lt;world", "hello<world"),
        ("hello&gt;world", "hello>world"),
        ("hello&nbsp;world", "hello world"),
        ("hello&mdash;world", "hello—world"),
        ("hello&ndash;world", "hello–world"),
        ("hello&copy;world", "hello©world"),
    ],
)
def test_un_urlencode(test_str: str, expected: str):
    from src.lib.cleaners import un_urlencode

    assert un_urlencode(test_str) == expected


@pytest.mark.parametrize(
    "test_str, expected",
    [
        ("<p>hello world</p>", "hello world"),
        ("<p>hello world", "hello world"),
        ("hello world</p>", "hello world"),
        ("<p>hello world", "hello world"),
        (
            "hello, <br />what a <b>wonderful</b> <span>world</span>",
            "hello, what a wonderful world",
        ),
    ],
)
def test_strip_html_tags(test_str: str, expected: str):
    from src.lib.cleaners import strip_html_tags

    assert strip_html_tags(test_str) == expected
