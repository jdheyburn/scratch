from musiclib.state import find_albums


def album(root, name, flacs=2):
    d = root / name
    d.mkdir(parents=True)
    for i in range(1, flacs + 1):
        (d / f"{i}.flac").write_bytes(b"")
    return d


def test_finds_directories_containing_flacs(tmp_path):
    album(tmp_path, "daphni")
    album(tmp_path, "mammo")
    assert [d.name for d in find_albums(tmp_path)] == ["daphni", "mammo"]


def test_ignores_a_directory_with_no_audio_in_it(tmp_path):
    album(tmp_path, "daphni")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "todo.txt").write_text("x")
    assert [d.name for d in find_albums(tmp_path)] == ["daphni"]


def test_ignores_the_archive_of_finished_albums(tmp_path):
    album(tmp_path, "daphni")
    album(tmp_path, "done/khruangbin")
    assert [d.name for d in find_albums(tmp_path)] == ["daphni"]


def test_ignores_the_state_directory(tmp_path):
    album(tmp_path, "daphni")
    album(tmp_path, ".state")
    assert [d.name for d in find_albums(tmp_path)] == ["daphni"]


def test_handles_a_slug_containing_a_space(tmp_path):
    album(tmp_path, "jump source")
    assert [d.name for d in find_albums(tmp_path)] == ["jump source"]


def test_returns_them_in_a_stable_order(tmp_path):
    for name in ["wax", "daphni", "mammo"]:
        album(tmp_path, name)
    assert [d.name for d in find_albums(tmp_path)] == ["daphni", "mammo", "wax"]
