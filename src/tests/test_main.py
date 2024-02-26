import pytest

from src.auto_m4b import app


@pytest.mark.usefixtures("tower_treasure__flat_mp3")
def test_flat_mp3():

    app(max_loops=1, no_fix=True, test=True)
    assert True
