from musiclib.state import read_state, update_state


def test_an_unknown_album_has_empty_state(tmp_path):
    assert read_state(tmp_path, "daphni") == {}


def test_state_round_trips(tmp_path):
    update_state(tmp_path, "daphni", dest="Daphni - Cherry (26241443)", flac_count=16)
    assert read_state(tmp_path, "daphni") == {
        "dest": "Daphni - Cherry (26241443)",
        "flac_count": 16,
    }


def test_updating_merges_rather_than_replacing(tmp_path):
    update_state(tmp_path, "daphni", dest="d", synced_at="t1")
    update_state(tmp_path, "daphni", imported_at="t2")

    state = read_state(tmp_path, "daphni")
    assert state["dest"] == "d"
    assert state["synced_at"] == "t1"
    assert state["imported_at"] == "t2"


def test_state_lives_out_of_the_way_of_the_albums(tmp_path):
    update_state(tmp_path, "daphni", dest="d")
    assert (tmp_path / ".state" / "daphni.yaml").is_file()
    assert not (tmp_path / "daphni").exists()
