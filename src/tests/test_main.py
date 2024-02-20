import pytest

from src.auto_m4b import app


@pytest.mark.usefixtures("use_arcade_catastrophe__multipart_mp3s")
def test_multipart_mp3s():

    app(max_loops=1)
    assert True
