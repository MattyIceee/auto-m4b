from src.auto_m4b import app


def test_flat_mp3_1(tower_treasure__flat_mp3):

    app(max_loops=1, no_fix=True, test=True)
    assert True


def test_flat_mp3_2(house_on_the_cliff__flat_mp3):

    app(max_loops=1, no_fix=True, test=True)
    assert True


def test_all_flat_mp3s(tower_treasure__flat_mp3, house_on_the_cliff__flat_mp3):

    app(max_loops=1, no_fix=True, test=True)
    assert True
