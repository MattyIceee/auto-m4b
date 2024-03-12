from src.lib.parsers import extract_path_info


def test_extract_path_info(benedict_society__mp3):

    assert extract_path_info(benedict_society__mp3) == "Audiobook"
