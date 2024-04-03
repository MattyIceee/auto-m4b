from src.lib.audiobook import Audiobook
from src.lib.fs_utils import hash_path_audio_files
from src.lib.inbox_state import InboxState


class TestInboxState:

    def test_get_item_by_key(
        self,
        chanur_series__multi_book_series_mp3: Audiobook,
        clean_inbox_state: InboxState,
    ):

        assert (
            clean_inbox_state.get("Chanur Series")
            == chanur_series__multi_book_series_mp3._inbox_item
        )

    def test_get_item_from_audiobook(
        self,
        chanur_series__multi_book_series_mp3: Audiobook,
        clean_inbox_state: InboxState,
    ):

        assert (
            clean_inbox_state.get(chanur_series__multi_book_series_mp3)
            == chanur_series__multi_book_series_mp3._inbox_item
        )

    def test_get_item_from_hash(
        self,
        chanur_series__multi_book_series_mp3: Audiobook,
        clean_inbox_state: InboxState,
    ):

        _hash = hash_path_audio_files(chanur_series__multi_book_series_mp3.inbox_dir)

        assert (
            clean_inbox_state.get(_hash)
            == chanur_series__multi_book_series_mp3._inbox_item
        )

        assert (
            clean_inbox_state.get_from_hash(_hash)
            == chanur_series__multi_book_series_mp3._inbox_item
        )

    def test_get_series_parent(
        self,
        Chanur_Series: list[Audiobook],
        clean_inbox_state: InboxState,
    ):

        series = Chanur_Series[0]
        # books = Chanur_Series[1:]
        key1 = "Chanur Series/01 - Pride Of Chanur"
        assert clean_inbox_state.get(key1).series_parent == series._inbox_item
