from src.lib.audiobook import Audiobook
from src.lib.fs_utils import hash_path_audio_files
from src.lib.inbox_state import InboxState


class TestInboxState:

    def test_get_item_by_key(
        self,
        Chanur_Series: list[Audiobook],
        clean_inbox_state: InboxState,
    ):

        assert clean_inbox_state.get("Chanur Series") == Chanur_Series[0]._inbox_item

    def test_get_item_from_audiobook(
        self,
        Chanur_Series: list[Audiobook],
        clean_inbox_state: InboxState,
    ):

        assert clean_inbox_state.get(Chanur_Series[0]) == Chanur_Series[0]._inbox_item

    def test_get_item_from_hash(
        self,
        Chanur_Series: list[Audiobook],
        clean_inbox_state: InboxState,
    ):

        _hash = hash_path_audio_files(Chanur_Series[0].inbox_dir)

        assert clean_inbox_state.get(_hash) == Chanur_Series[0]._inbox_item

    def test_get_series_parent(
        self,
        Chanur_Series: list[Audiobook],
        clean_inbox_state: InboxState,
    ):

        series = Chanur_Series[0]
        # books = Chanur_Series[1:]
        key1 = "Chanur Series/01 - Pride Of Chanur"
        assert clean_inbox_state.get(key1).series_parent == series._inbox_item
